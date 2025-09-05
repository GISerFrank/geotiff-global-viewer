# -*- coding: utf-8 -*-
import os
import uuid
import tempfile
import boto3
import rasterio
from rasterio.warp import transform_bounds
import numpy as np
from PIL import Image
import psycopg2
import psycopg2.extras

# --- 配置 ---
# 从环境变量中获取配置，这是部署的最佳实践
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')
AWS_DEFAULT_REGION = os.environ.get('AWS_DEFAULT_REGION')
S3_PREVIEW_PREFIX = 'previews/'

# 初始化 boto3 客户端
s3_client = boto3.client('s3', region_name=AWS_DEFAULT_REGION)

# --- 数据库连接 ---
def get_db_connection():
    """建立与 PostgreSQL 数据库的连接 (凭证来自环境变量)"""
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD')
    )
    return conn

# --- S3 辅助函数 ---
def upload_file_to_s3(file_path, object_key):
    """将本地文件上传到 S3 并设置为公开可读"""
    try:
        s3_client.upload_file(
            file_path,
            S3_BUCKET_NAME,
            object_key,
            ExtraArgs={'ContentType': 'image/png', 'ACL': 'public-read'}
        )
        print(f"成功上传文件到 s3://{S3_BUCKET_NAME}/{object_key}")
    except Exception as e:
        print(f"S3 上传失败: {e}")
        raise

def get_s3_public_url(object_key):
    """根据 S3 区域和存储桶名称构建公开 URL"""
    return f"https://{S3_BUCKET_NAME}.s3.{AWS_DEFAULT_REGION}.amazonaws.com/{object_key}"

# --- 核心处理函数 ---
def process_geotiff_and_upload(local_geotiff_path):
    """
    处理本地 GeoTIFF 文件，生成预览图，上传至 S3，并返回所需元数据。
    :param local_geotiff_path: 服务器上临时 GeoTIFF 文件的路径。
    :return: 包含 wkt_polygon 和 preview_url 的字典。
    """
    try:
        with rasterio.open(local_geotiff_path) as dataset:
            # 1. 坐标和范围转换
            wgs84_bounds = transform_bounds(dataset.crs, {'init': 'epsg:4326'}, *dataset.bounds)
            wkt_polygon = f'POLYGON(({wgs84_bounds[0]} {wgs84_bounds[1]}, {wgs84_bounds[2]} {wgs84_bounds[1]}, {wgs84_bounds[2]} {wgs84_bounds[3]}, {wgs84_bounds[0]} {wgs84_bounds[3]}, {wgs84_bounds[0]} {wgs84_bounds[1]}))'

            # 2. 图像处理，生成预览图
            band1 = dataset.read(1)
            min_val, max_val = np.min(band1), np.max(band1)
            if max_val > min_val:
                normalized_band = ((band1 - min_val) / (max_val - min_val) * 255).astype(np.uint8)
            else:
                normalized_band = np.zeros(band1.shape, dtype=np.uint8)

            img = Image.fromarray(normalized_band, 'L')
            
            # 3. 将预览图保存到临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_preview:
                img.save(temp_preview.name, format='PNG')
                temp_preview_path = temp_preview.name

        # 4. 上传预览图到 S3
        s3_preview_key = f"{S3_PREVIEW_PREFIX}{uuid.uuid4()}.png"
        upload_file_to_s3(temp_preview_path, s3_preview_key)
        preview_url = get_s3_public_url(s3_preview_key)

        return {
            "wkt_polygon": wkt_polygon,
            "preview_url": preview_url
        }

    finally:
        # 5. 清理临时预览图文件
        if 'temp_preview_path' in locals() and os.path.exists(temp_preview_path):
            os.remove(temp_preview_path)


def insert_dataset_to_db(conn, name, image_url, geom_wkt, source_path, source_type, category_id):
    """
    将数据集的元数据插入到数据库中。
    """
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO datasets (name, image_url, geom, source_path, source_type, category_id) 
            VALUES (%s, %s, ST_GeomFromText(%s, 4326), %s, %s, %s)
            """,
            (name, image_url, geom_wkt, source_path, source_type, category_id)
        )
        conn.commit()
        print(f"✅ 成功入库: {name} (来源: {source_type})")
    except Exception as e:
        conn.rollback()
        print(f"❌ 数据库插入失败: {name}. 错误: {e}")
        raise
    finally:
        cursor.close()
