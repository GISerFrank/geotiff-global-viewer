import os
import uuid
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS # 引入CORS
import rasterio
from rasterio.warp import transform_bounds
import numpy as np
from PIL import Image
import psycopg2
import psycopg2.extras # 我们需要这个来获取字典形式的结果
from processing import get_db_connection
from init_dtable import init_db
from collections import defaultdict # 导入 defaultdict


# 初始化 Flask 应用
app = Flask(__name__)
CORS(app) # 关键：为整个应用启用CORS

# 配置文件夹路径
# os.path.dirname(__file__) 获取当前文件所在目录的绝对路径
BASE_DIR = os.path.dirname(__file__)
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
STATIC_FOLDER = os.path.join(BASE_DIR, 'static')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.join(STATIC_FOLDER, 'processed'), exist_ok=True)

# (可选) 如果是第一次运行，可以取消下面这行代码的注释来创建数据库文件和表
# init_db()

@app.route('/upload-geotiff', methods=['POST'])
def upload_geotiff():
    # ... (这里是之前我们写好的所有处理逻辑，无需改动)
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    temp_filepath = ""
    conn = None
    try:
        dataset_name = os.path.splitext(file.filename)[0]
        temp_filepath = os.path.join(UPLOAD_FOLDER, str(uuid.uuid4()) + "_" + file.filename)
        file.save(temp_filepath)

        with rasterio.open(temp_filepath) as dataset:
            bounds = dataset.bounds
            src_crs = dataset.crs

            wgs84_bounds = transform_bounds(src_crs, {'init': 'epsg:4326'}, *bounds)

            band1 = dataset.read(1)

            min_val = np.min(band1)
            max_val = np.max(band1)

            if max_val == min_val:
                normalized_band = np.zeros(band1.shape, dtype=np.uint8)
            else:
                normalized_band = ((band1 - min_val) / (max_val - min_val) * 255).astype(np.uint8)

            img = Image.fromarray(normalized_band, 'L')
            unique_filename = f"{uuid.uuid4()}.png"
            # 注意保存路径
            output_filepath = os.path.join(STATIC_FOLDER, 'processed', unique_filename)
            img.save(output_filepath)

            # --- PostGIS 修改开始 ---
            # 将边界框 (west, south, east, north) 转换为 WKT (Well-Known Text) 格式的 Polygon
            wkt_polygon = (
                f'POLYGON(('
                f'{wgs84_bounds[0]} {wgs84_bounds[1]}, '
                f'{wgs84_bounds[2]} {wgs84_bounds[1]}, '
                f'{wgs84_bounds[2]} {wgs84_bounds[3]}, '
                f'{wgs84_bounds[0]} {wgs84_bounds[3]}, '
                f'{wgs84_bounds[0]} {wgs84_bounds[1]}'
                f'))'
            )

            conn = get_db_connection()
            cursor = conn.cursor()

            # 使用 PostGIS 函数 ST_GeomFromText 将 WKT 字符串转换为 GEOMETRY 对象
            # 注意占位符从 '?' 变成了 '%s'
            cursor.execute(
                "INSERT INTO datasets (name, image_url, geom) VALUES (%s, %s, ST_GeomFromText(%s, 4326))",
                (dataset_name, 'static/processed/' + unique_filename, wkt_polygon)
            )

            conn.commit()
            cursor.close()
            # --- PostGIS 修改结束 ---

        return jsonify({"success": True, "message": f"Dataset '{dataset_name}' added successfully."})

    except Exception as e:
        # 如果有数据库连接，回滚事务
        if conn:
            conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)

@app.route('/api/datasets', methods=['GET'])
def get_datasets():
    """获取按分类分组后的数据集列表"""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # 使用 JOIN 查询，并按分类名和数据集名排序
    sql = """
        SELECT 
            c.name as category_name,
            c.description as category_description,
            d.id, 
            d.name, 
            d.image_url, 
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
    cursor.close()
    conn.close()

    # --- 将扁平的查询结果转换为层级结构 ---
    grouped_data = defaultdict(lambda: {'category_description': '', 'datasets': []})
    for row in rows:
        category_name = row['category_name']
        # 更新描述信息（因为每个同类别的行都包含它，所以会被重复赋值，但结果正确）
        grouped_data[category_name]['category_description'] = row['category_description']

        # 将数据集信息添加到对应的分类列表中
        dataset_info = dict(row)
        # 移除字典中不再需要的分类信息，避免冗余
        dataset_info['category'] = dataset_info.pop('category_name') # 重命名为 'category'
        del dataset_info['category_description']

        # 拼接完整的 image_url
        dataset_info['image_url'] = request.host_url + dataset_info['image_url']

        grouped_data[category_name]['datasets'].append(dataset_info)

    # 转换为最终的 JSON 格式: [{ "category": "...", "datasets": [...] }, ...]
    final_result = [
        {"category": name, "description": data['category_description'], "datasets": data['datasets']}
        for name, data in grouped_data.items()
    ]

    return jsonify(final_result)

# 添加一个“全匹配”路由来处理前端页面
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(app.static_folder + '/' + path):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)