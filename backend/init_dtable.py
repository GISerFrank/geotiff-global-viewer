import psycopg2

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

def init_db():
    """初始化数据库，创建 PostGIS 扩展和数据表"""
    print("Initializing PostgreSQL database with PostGIS...")
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 步骤 1: 确保 PostGIS 扩展已启用
        print("Enabling PostGIS extension...")
        cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

        # 步骤 2: 创建 datasets 表，使用 GEOMETRY 类型存储地理边界
        print("Creating datasets table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS datasets (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                image_url TEXT NOT NULL,
                geom GEOMETRY(Polygon, 4326), -- 存储地理边界，SRID 4326 代表 WGS84
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        conn.commit()
        cursor.close()
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Database initialization failed: {e}")
    finally:
        if conn is not None:
            conn.close()

# (可选) 如果是第一次运行，可以取消下面这行代码的注释来创建数据库文件和表
# init_db()