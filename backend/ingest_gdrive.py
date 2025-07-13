import os
import io
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from processing import process_and_insert_geotiff
from app import get_db_connection
from ingest_local import get_categories, assign_category_by_filepath # 复用本地脚本的函数

# --- 配置 (保持不变) ---
SERVICE_ACCOUNT_FILE = 'gdrive-credentials.json'
GDRIVE_FOLDER_ID = 'YOUR_GOOGLE_DRIVE_FOLDER_ID'
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
DOWNLOAD_DIR = 'temp_downloads'
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# vvv --- 这里是新增的部分 --- vvv

def get_gdrive_path(service, file_id, path_cache):
    """
    递归获取 Google Drive 中文件或文件夹的完整路径字符串。
    使用一个缓存来提高性能，避免重复查询。
    """
    # 如果路径已在缓存中，直接返回
    if file_id in path_cache:
        return path_cache[file_id]

    try:
        # 获取当前文件/文件夹的名称及其父文件夹的ID
        file_metadata = service.files().get(fileId=file_id, fields='name, parents').execute()
        parents = file_metadata.get('parents')

        # 如果有父文件夹，则递归调用以获取父路径
        if parents:
            # Google Drive 文件可以有多个父级，我们只取第一个
            parent_path = get_gdrive_path(service, parents[0], path_cache)
            # 拼接路径
            full_path = os.path.join(parent_path, file_metadata['name'])
        else:
            # 如果没有父文件夹，说明它在“我的云端硬盘”的根目录
            full_path = file_metadata['name']

        # 将结果存入缓存
        path_cache[file_id] = full_path
        return full_path

    except Exception as e:
        print(f"警告：无法解析 ID '{file_id}' 的路径. 错误: {e}")
        # 返回一个特殊值表示路径未知
        return f"UnknownPath/{file_id}"


def get_processed_gdrive_source_paths(conn):
    """从数据库获取所有已处理的 Google Drive 文件来源路径"""
    cursor = conn.cursor()
    cursor.execute("SELECT source_path FROM datasets WHERE source_path IS NOT NULL")
    processed_paths = {item[0] for item in cursor.fetchall()}
    cursor.close()
    return processed_paths

# ^^^ --- 新增部分结束 --- ^^^


def main():
    print("--- 开始扫描 Google Drive 文件夹 ---")
    service = get_gdrive_service()

    db_conn = get_db_connection()
    # 修改：现在我们检查完整的来源路径，而不仅仅是ID
    processed_paths = get_processed_gdrive_source_paths(db_conn)
    categories = get_categories(db_conn)
    db_conn.close()

    print(f"数据库中已有 {len(processed_paths)} 个已处理文件。")

    # 创建一个在本次运行中持续有效的路径缓存
    path_cache = {}

    query = f"'{GDRIVE_FOLDER_ID}' in parents and (mimeType='image/tiff' or name contains '.tif')"
    results = service.files().list(q=query, fields="nextPageToken, files(id, name, parents)").execute()
    items = results.get('files', [])

    if not items:
        print("在 Google Drive 文件夹中未找到任何 .tif/.tiff 文件。")
        return

    new_files_count = 0
    for item in items:
        file_id, file_name = item['id'], item['name']

        # --- 核心逻辑修改 ---
        # 1. 获取文件的完整 GDrive 路径
        # 我们获取的是父文件夹的路径，然后手动拼接上文件名，这样更准确
        parent_id = item.get('parents')[0] if item.get('parents') else None
        folder_path = get_gdrive_path(service, parent_id, path_cache) if parent_id else "/"
        full_gdrive_path = os.path.join(folder_path, file_name)

        # 2. 检查这个完整路径是否已经被处理过
        if full_gdrive_path in processed_paths:
            continue

        print(f"发现新文件: {full_gdrive_path}")
        new_files_count += 1

        # 3. 根据拼接出的完整路径分配分类
        category_id = assign_category_by_filepath(full_gdrive_path, categories)
        if category_id is None:
            print(f"警告: 未能为文件 {file_name} 找到匹配的分类，已跳过。")
            continue

        # 4. 下载文件
        request = service.files().get_media(fileId=file_id)
        local_filepath = os.path.join(DOWNLOAD_DIR, file_name)
        with io.FileIO(local_filepath, 'wb') as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                print(f"下载 {file_name}: {int(status.progress() * 100)}%")

        # 5. 调用处理函数，传入要记录的完整 GDrive 路径
        process_and_insert_geotiff(local_filepath, full_gdrive_path, category_id, 'GOOGLE_DRIVE')

        os.remove(local_filepath)

    print("--- Google Drive 扫描完成 ---")
    print(f"本次共处理了 {new_files_count} 个新文件。")


if __name__ == '__main__':
    main()