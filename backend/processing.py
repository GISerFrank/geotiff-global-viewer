import os
import uuid
import rasterio
from rasterio.warp import transform_bounds
import numpy as np
from PIL import Image
import psycopg2

# 项目的根目录
BASE_DIR = os.path.dirname(__file__)
STATIC_FOLDER = os.path.join(BASE_DIR, 'static')
os.makedirs(os.path.join(STATIC_FOLDER, 'processed'), exist_ok=True)

# 新的 PostgreSQL 连接配置
DB_CONFIG = {
    "host": "localhost",
    "database": "geotiff_backend",        # 你创建的数据库名
    "user": "postgres",              # 你创建的用户名
    "password": "Liaobw020809!" # 你设置的密码
}

def get_db_connection():
    """创建 PostgreSQL 数据库连接"""
    conn = psycopg2.connect(**DB_CONFIG)
    return conn

def process_and_insert_geotiff(local_file_path, source_to_record, category_id, source_type):
    """
    处理单个 GeoTIFF 文件并将其元数据插入数据库。
    这个新版本区分了要处理的本地文件路径和要记录的来源路径。

    :param local_file_path: 本地 GeoTIFF 文件的完整路径，用于被 Rasterio 打开。
    :param source_to_record: 要记录到数据库 source_path 字段的唯一标识符。
    :param category_id: 该文件所属分类的 ID。
    :return: 成功则返回 True，否则返回 False。
    """
    conn = None
    try:
        print(f"开始处理: {local_file_path}")
        # 数据集名称仍然从本地文件名中获取
        dataset_name = os.path.splitext(os.path.basename(local_file_path))[0]

        # 使用 local_file_path 来打开和处理文件
        with rasterio.open(local_file_path) as dataset:
            # ... (这部分图像处理和坐标转换的代码完全不变) ...
            wgs84_bounds = transform_bounds(dataset.crs, {'init': 'epsg:4326'}, *dataset.bounds)
            band1 = dataset.read(1)
            min_val, max_val = np.min(band1), np.max(band1)
            normalized_band = ((band1 - min_val) / (max_val - min_val) * 255).astype(np.uint8) if max_val > min_val else np.zeros(band1.shape, dtype=np.uint8)
            img = Image.fromarray(normalized_band, 'L')
            unique_filename = f"{dataset_name}_{uuid.uuid4().hex[:8]}.png"
            output_filepath = os.path.join(STATIC_FOLDER, 'processed', unique_filename)
            img.save(output_filepath)
            wkt_polygon = f'POLYGON(({wgs84_bounds[0]} {wgs84_bounds[1]}, {wgs84_bounds[2]} {wgs84_bounds[1]}, {wgs84_bounds[2]} {wgs84_bounds[3]}, {wgs84_bounds[0]} {wgs84_bounds[3]}, {wgs84_bounds[0]} {wgs84_bounds[1]}))'

            conn = get_db_connection()
            cursor = conn.cursor()

            # --- 关键修改 ---
            # 在 INSERT 语句中，使用 source_to_record 参数来填充 source_path 字段
            cursor.execute(
                "INSERT INTO datasets (name, image_url, geom, source_path, category_id, source_type) VALUES (%s, %s, ST_GeomFromText(%s, 4326), %s, %s, %s)",
                (dataset_name, 'static/processed/' + unique_filename, wkt_polygon, source_to_record, category_id, source_type)
            )
            conn.commit()
            cursor.close()
            print(f"✅ 成功入库: {dataset_name} (来源: {source_type})")
            return True

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ 处理失败: {local_file_path}. 错误: {e}")
        return False
    finally:
        if conn:
            conn.close()
