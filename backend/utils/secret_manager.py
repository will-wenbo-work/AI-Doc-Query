import boto3
import json
import psycopg2
import os

# --- 新增：从环境变量获取 Secret Name ---
# 最佳实践：将 Secret Name 放在环境变量中
RDS_SECRET_NAME = os.environ.get("RDS_SECRET_NAME", "rds-db-credentials/cluster-XYZ/username") 
# ----------------------------------------

# 初始化 Secrets Manager 客户端
# boto3 会自动查找您的凭证（例如通过 IAM Role 或本地配置）
class SecretsManager:
    """A small wrapper around boto3 Secrets Manager operations.

    Example:
        sm = SecretsManager(region_name='us-west-2')
        creds = sm.get_rds_credentials('my-secret-name')
    """

    def __init__(self, region_name: str = None):
        self.region_name = region_name
        self.client = boto3.client('secretsmanager', region_name=region_name)

    def get_secret(self, secret_name: str) -> dict:
        try:
            resp = self.client.get_secret_value(SecretId=secret_name)
        except Exception as e:
            raise RuntimeError(f"Error retrieving secret {secret_name}: {e}")

        secret_string = resp.get('SecretString')
        if not secret_string:
            raise ValueError('Secret is not in SecretString format or is empty')
        return json.loads(secret_string)

    def get_rds_credentials(self, secret_name: str) -> dict:
        data = self.get_secret(secret_name)
        username = data.get('username') or data.get('user')
        password = data.get('password')
        host = data.get('host') or data.get('hostname')
        port = str(data.get('port') or data.get('db_port') or 5432)
        dbname = data.get('dbname') or data.get('database') or data.get('db')

        if not all([username, password, host, dbname]):
            raise ValueError('Secret missing required DB fields (username,password,host,dbname)')

        return {
            'username': username,
            'password': password,
            'host': host,
            'port': port,
            'dbname': dbname,
        }


def get_rds_credentials(secret_name: str) -> dict:
    """Backward-compatible function: create a client and return credentials."""
    sm = SecretsManager()
    return sm.get_rds_credentials(secret_name)


def establish_db_connection():
    """获取凭证并建立 PostgreSQL 连接"""
    
    # 1. 从 Secrets Manager 获取配置
    db_config = get_secret(RDS_SECRET_NAME)
    
    # 2. 从配置中提取连接参数
    DB_HOST = db_config.get("host")
    DB_PORT = db_config.get("port")
    DB_NAME = db_config.get("dbname", "postgres") # 假设默认数据库名为 postgres
    DB_USER = db_config.get("username")
    DB_PASSWORD = db_config.get("password")
    
    if not all([DB_HOST, DB_USER, DB_PASSWORD]):
        raise ValueError("Missing essential database credentials in the secret.")

    # 3. 建立连接
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        return conn

    except Exception as e:
        print(f"Database connection failed: {e}")
        raise e


def get_rds_credentials(secret_name: str) -> dict:
    """Return DB credentials dict from Secrets Manager (username,password,host,port,dbname).

    This is a convenience wrapper around `get_secret`.
    """
    data = get_secret(secret_name)
    username = data.get('username') or data.get('user')
    password = data.get('password')
    host = data.get('host') or data.get('hostname')
    port = str(data.get('port') or data.get('db_port') or 5432)
    dbname = data.get('dbname') or data.get('database') or data.get('db')

    if not all([username, password, host, dbname]):
        raise ValueError('Secret missing required DB fields (username,password,host,dbname)')

    return {
        'username': username,
        'password': password,
        'host': host,
        'port': port,
        'dbname': dbname,
    }

# --- 示例：在您的 Flask 路由中使用 ---
# @app.route('/test-db-connection', methods=['GET'])
# def test_db():
#     try:
#         conn = establish_db_connection()
#         # ... 执行数据库操作
#         conn.close()
#         return jsonify({"status": "ok", "message": "DB connection successful via Secrets Manager"}), 200
#     except Exception as e:
#         return jsonify({"status": "error", "message": str(e)}), 500