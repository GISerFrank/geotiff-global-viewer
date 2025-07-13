import os
import psycopg2
from processing import process_and_insert_geotiff # 导入我们的核心处理函数
from app import get_db_connection # 复用连接函数

# --- 配置 ---
# 将此路径修改为你要监控的本地文件夹
GEO_DATA_FOLDER = r"E:\Diffusion+Landslide\GVLM-CD\Slope\tiff"

def get_processed_files(conn):
    """从数据库获取所有已处理文件的源路径列表"""
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

# vvv --- 这里是主要的修改部分 --- vvv

def assign_category_by_filepath(filepath, categories):
    """
    根据文件路径中的关键字分配分类ID。
    :param filepath: 文件的完整路径。
    :param categories: 包含所有分类名称和ID的字典。
    :return: 匹配到的分类ID，如果没有匹配则返回“其他”分类的ID。
    """
    # 将完整路径转换为小写以进行不区分大小写的匹配
    filepath_lower = filepath.lower()

    # 规则1: 检查路径中是否包含 "dem"
    if 'dem' in filepath_lower:
        return categories.get('数字高程模型 (DEM)')

    # 规则2: 检查路径中是否包含 "slope"
    elif 'slope' in filepath_lower:
        return categories.get('坡度分析')

    # 规则3: 检查路径中是否包含 "satellite imagery" (新的关键字)
    elif 'satellite imagery' in filepath_lower:
        return categories.get('遥感影像')

    # 规则4: 如果以上规则都未匹配，则归入“其他”分类
    else:
        return categories.get('其他')

# ^^^ --- 修改结束 --- ^^^

def main():
    print("--- 开始扫描本地文件夹 ---")
    if not os.path.isdir(GEO_DATA_FOLDER):
        print(f"错误: 文件夹不存在 -> {GEO_DATA_FOLDER}")
        return

    db_conn = get_db_connection()
    processed_files = get_processed_files(db_conn)
    categories = get_categories(db_conn)
    db_conn.close()

    print(f"数据库中已有 {len(processed_files)} 个已处理文件。")
    print(f"已加载分类: {list(categories.keys())}")

    new_files_count = 0
    for root, _, files in os.walk(GEO_DATA_FOLDER):
        for filename in files:
            if filename.lower().endswith(('.tif', '.tiff')):
                file_path = os.path.join(root, filename)

                if file_path in processed_files:
                    continue

                new_files_count += 1

                # --- 修改这里的函数调用 ---
                category_id = assign_category_by_filepath(file_path, categories) # 使用新的函数名和参数

                if category_id is None:
                    print(f"警告: 未能为文件 {filename} 找到匹配的分类，已跳过。")
                    continue

                # --- 修改这里的函数调用 ---
                # 对于本地文件，处理路径和记录路径是同一个
                process_and_insert_geotiff(file_path, file_path, category_id, 'LOCAL')

    print("--- 扫描完成 ---")
    print(f"本次共处理了 {new_files_count} 个新文件。")

if __name__ == '__main__':
    main()