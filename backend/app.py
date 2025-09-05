# -*- coding: utf-8 -*-
import os
import uuid
import tempfile
import boto3
from flask import Flask, request, jsonify
from flask_cors import CORS
import rasterio
from rasterio.warp import transform_bounds
import numpy as np
from PIL import Image
import psycopg2
import psycopg2.extras
from collections import defaultdict

# --- 应用初始化 ---
app = Flask(__name__)
CORS(app)  # 为整个应用启用CORS

# --- AWS S3 配置 ---
# 强烈建议将这些值设置为您 Render 服务中的环境变量
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
AWS_DEFAULT_REGION = os.environ.get('AWS_DEFAULT_REGION')

# S3 存储桶内的“文件夹”（前缀）
S3_PREVIEW_PREFIX = 'previews/'  # 用于存放处理后的预览图
S3_SOURCE_PREFIX = 'geotiffs/'  # 用于存放用户上传的原始GeoTIFF文件

# 初始化 S3 客户端
# boto3 会自动从环境变量中读取凭证
s3_client = boto3.client('s3', region_name=AWS_DEFAULT_REGION)

# --- 数据库连接 ---
def get_db_connection():
    """建立与 PostgreSQL 数据库的连接。"""
    # 将您的数据库凭证也设置为环境变量
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD')
    )
    return conn

# --- 文件上传接口 (已为S3重构) ---
@app.route('/upload-geotiff', methods=['POST'])
def upload_geotiff():
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "请求中不包含文件部分"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "未选择任何文件"}), 400

    conn = None
    temp_geotiff_path = None
    temp_preview_path = None

    try:
        # 步骤 1: 将上传的文件保存到服务器的临时路径中
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
            file.save(temp_file.name)
            temp_geotiff_path = temp_file.name

        # 步骤 2: 将原始 GeoTIFF 文件上传到 S3 进行备份和存档
        dataset_name = os.path.splitext(file.filename)[0]
        s3_source_key = f"{S3_SOURCE_PREFIX}{uuid.uuid4()}_{file.filename}"
        s3_client.upload_file(temp_geotiff_path, S3_BUCKET_NAME, s3_source_key)
        print(f"原始文件已上传至: s3://{S3_BUCKET_NAME}/{s3_source_key}")

        # 步骤 3: 处理本地的临时 GeoTIFF 文件以创建预览图
        with rasterio.open(temp_geotiff_path) as dataset:
            bounds = dataset.bounds
            src_crs = dataset.crs
            wgs84_bounds = transform_bounds(src_crs, {'init': 'epsg:4326'}, *bounds)
            band1 = dataset.read(1)
            min_val, max_val = np.min(band1), np.max(band1)

            if max_val == min_val:
                normalized_band = np.zeros(band1.shape, dtype=np.uint8)
            else:
                normalized_band = ((band1 - min_val) / (max_val - min_val) * 255).astype(np.uint8)

            img = Image.fromarray(normalized_band, 'L')
            
            # 将预览图保存到另一个临时文件中
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_preview:
                img.save(temp_preview.name, format='PNG')
                temp_preview_path = temp_preview.name
        
        # 步骤 4: 将生成的预览图上传到 S3，并设置为公开可读
        s3_preview_key = f"{S3_PREVIEW_PREFIX}{uuid.uuid4()}.png"
        s3_client.upload_file(
            temp_preview_path,
            S3_BUCKET_NAME,
            s3_preview_key,
            ExtraArgs={'ContentType': 'image/png', 'ACL': 'public-read'}
        )
        # 构建预览图的公开访问 URL
        preview_url = f"https://{S3_BUCKET_NAME}.s3.{AWS_DEFAULT_REGION}.amazonaws.com/{s3_preview_key}"
        print(f"预览图已上传至: {preview_url}")

        # 步骤 5: 将元数据和 S3 预览图 URL 存入数据库
        wkt_polygon = f'POLYGON(({wgs84_bounds[0]} {wgs84_bounds[1]}, {wgs84_bounds[2]} {wgs84_bounds[1]}, {wgs84_bounds[2]} {wgs84_bounds[3]}, {wgs84_bounds[0]} {wgs84_bounds[3]}, {wgs84_bounds[0]} {wgs84_bounds[1]}))'
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 默认归类为“其他”。更高级的实现可能允许用户在前端选择分类。
        # 请确保您的 categories 表中存在 ID 为 4 的记录，或者修改为正确的ID。
        default_category_id = 4
        cursor.execute(
            """
            INSERT INTO datasets (name, image_url, geom, source_path, source_type, category_id) 
            VALUES (%s, %s, ST_GeomFromText(%s, 4326), %s, %s, %s)
            """,
            (dataset_name, preview_url, wkt_polygon, s3_source_key, 'S3_UPLOAD', default_category_id)
        )
        conn.commit()
        cursor.close()

        return jsonify({"success": True, "message": f"数据集 '{dataset_name}' 已成功处理并保存。"})

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"文件上传和处理过程中发生错误: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        # 步骤 6: 无论成功与否，都清理服务器上的所有临时文件
        if temp_geotiff_path and os.path.exists(temp_geotiff_path):
            os.remove(temp_geotiff_path)
        if temp_preview_path and os.path.exists(temp_preview_path):
            os.remove(temp_preview_path)
        if conn:
            conn.close()

# --- 数据集 API 接口 (已适配 S3) ---
@app.route('/api/datasets', methods=['GET'])
def get_datasets():
    """从数据库获取按分类分组的数据集列表。"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        sql = """
            SELECT 
                c.name as category_name,
                c.description as category_description,
                d.id, 
                d.name, 
                d.image_url, -- 这已经是完整的 S3 URL
                d.source_type,
                ST_XMin(d.geom) as bbox_west,
                ST_YMin(d.geom) as bbox_south,
                ST_XMax(d.geom) as bbox_east,
                ST_YMax(d.geom) as bbox_north
            FROM datasets d
            JOIN categories c ON d.category_id = c.id
            ORDER BY c.name, d.name;
        """
        cursor.execute(sql)
        rows = cursor.fetchall()

        # 将扁平的查询结果按分类分组，转换为层级结构
        grouped_data = defaultdict(lambda: {'category_description': '', 'datasets': []})
        for row in rows:
            category_name = row['category_name']
            grouped_data[category_name]['category_description'] = row['category_description']
            
            dataset_info = dict(row)
            # !!! 关键改动: 不再需要拼接 request.host_url !!!
            # 因为数据库中存储的已经是完整的、可公开访问的 S3 URL。
            
            # 清理字典以获得更简洁的 API 响应
            dataset_info['category'] = dataset_info.pop('category_name')
            del dataset_info['category_description']
            
            grouped_data[category_name]['datasets'].append(dataset_info)

        # 将分组后的数据转换为最终的列表格式
        final_result = [
            {"category": name, "description": data['category_description'], "datasets": data['datasets']}
            for name, data in grouped_data.items()
        ]

        return jsonify(final_result)

    except Exception as e:
        print(f"获取数据集时出错: {e}")
        return jsonify({"success": False, "error": "无法从数据库检索数据集。"}), 500
    finally:
        if conn:
            conn.close()

# --- 主程序入口 ---
if __name__ == '__main__':
    # Render 会自动设置 PORT 环境变量
    port = int(os.environ.get('PORT', 5000))
    # 使用 0.0.0.0 使服务在容器/Render环境中可访问
    app.run(host='0.0.0.0', port=port)
