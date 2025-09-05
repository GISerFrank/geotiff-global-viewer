# -*- coding: utf-8 -*-
import os
import tempfile
import boto3
from collections import defaultdict

# --- 导入我们重构后的核心处理模块 ---
from processing import (
    get_db_connection, 
    process_geotiff_and_upload, 
    insert_dataset_to_db
)

# --- 配置 ---
# 从环境变量获取配置
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')
AWS_DEFAULT_REGION = os.environ.get('AWS_DEFAULT_REGION')
S3_SOURCE_PREFIX = 'geotiffs/'  # 存放原始 GeoTIFF 的“文件夹”

# 初始化 boto3 客户端
s3_client = boto3.client('s3', region_name=AWS_DEFAULT_REGION)

# --- 数据库交互函数 ---
def get_processed_files(conn):
    """从数据库获取所有已处理文件的源路径(S3 Key)列表"""
    cursor = conn.cursor()
    cursor.execute("SELECT source_path FROM datasets WHERE source_path IS NOT NULL")
    processed_files = {item[0] for item in cursor.fetchall()}
    cursor.close()
    return processed_files

def get_categories(conn):
    """从数据库获取所有分类，并返回一个 name->id 的字典"""
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM categories")
    categories = {name: cat_id for cat_id, name in cursor.fetchall()}
    cursor.close()
    return categories

# --- 业务逻辑 ---
def assign_category_by_s3_key(s3_key, categories):
    """根据 S3 对象键名中的路径分配分类ID"""
    key_lower = s3_key.lower()
    # 假设您的S3文件夹结构是 geotiffs/dem/file.tif, geotiffs/slope/file.tif 等
    if 'dem/' in key_lower:
        return categories.get('数字高程模型 (DEM)')
    elif 'slope/' in key_lower:
        return categories.get('坡度分析')
    elif 'satellite_imagery/' in key_lower:
        return categories.get('遥感影像')
    else:
        return categories.get('其他')

def main():
    print("--- 开始扫描 S3 存储桶 ---")
    db_conn = None
    try:
        db_conn = get_db_connection()
        processed_files = get_processed_files(db_conn)
        categories = get_categories(db_conn)

        print(f"数据库中已有 {len(processed_files)} 个已处理文件。")
        print(f"已加载分类: {list(categories.keys())}")

        new_files_count = 0
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix=S3_SOURCE_PREFIX)

        for page in pages:
            if 'Contents' not in page:
                continue
            for obj in page['Contents']:
                s3_key = obj['Key']
                
                if s3_key.endswith('/') or not s3_key.lower().endswith(('.tif', '.tiff')):
                    continue
                
                if s3_key in processed_files:
                    continue

                new_files_count += 1
                category_id = assign_category_by_s3_key(s3_key, categories)
                
                if category_id is None:
                    print(f"警告: 未能为文件 {s3_key} 找到匹配的分类，已跳过。")
                    continue
                
                # 使用临时目录安全地处理下载的文件
                with tempfile.TemporaryDirectory() as temp_dir:
                    local_geotiff_path = os.path.join(temp_dir, os.path.basename(s3_key))
                    print(f"正在下载并处理: {s3_key}")
                    s3_client.download_file(S3_BUCKET_NAME, s3_key, local_geotiff_path)
                    
                    # 调用 processing 模块的核心函数
                    processed_data = process_geotiff_and_upload(local_geotiff_path)
                    
                    dataset_name = os.path.splitext(os.path.basename(s3_key))[0]
                    
                    # 调用 processing 模块的数据库插入函数
                    insert_dataset_to_db(
                        db_conn,
                        name=dataset_name,
                        image_url=processed_data['preview_url'],
                        geom_wkt=processed_data['wkt_polygon'],
                        source_path=s3_key,
                        source_type='S3',
                        category_id=category_id
                    )

    except Exception as e:
        print(f"处理过程中发生严重错误: {e}")
    finally:
        if db_conn:
            db_conn.close()

    print("--- 扫描完成 ---")

if __name__ == '__main__':
    main()
