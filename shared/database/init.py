"""
数据库初始化模块 - 支持 MySQL 8.0+ 和 SQLite
"""
import os
import pymysql
import sqlite3
from pathlib import Path
from typing import Optional, Union, Any
from datetime import datetime
from contextlib import contextmanager

class Database:
    def __init__(self, db_type: str = "sqlite", **kwargs):
        """
        初始化数据库连接

        Args:
            db_type: 数据库类型 ('mysql' or 'sqlite')

            MySQL参数:
                host: MySQL主机
                port: MySQL端口
                user: 用户名
                password: 密码
                database: 数据库名
                charset: 字符集

            SQLite参数:
                db_path: 数据库文件路径
        """
        self.db_type = db_type.lower()
        self.conn: Optional[Union[pymysql.Connection, sqlite3.Connection]] = None

        if self.db_type == "mysql":
            self.config = {
                'host': kwargs.get('host', 'localhost'),
                'port': kwargs.get('port', 3306),
                'user': kwargs.get('user', 'root'),
                'password': kwargs.get('password', ''),
                'database': kwargs.get('database', 'tgbot'),
                'charset': kwargs.get('charset', 'utf8mb4'),
                'cursorclass': pymysql.cursors.DictCursor,
                'autocommit': False
            }
        elif self.db_type == "sqlite":
            self.db_path = kwargs.get('db_path', 'data/bot.db')
            self._ensure_data_dir()
        else:
            raise ValueError(f"Unsupported database type: {db_type}")

    def _ensure_data_dir(self):
        """确保SQLite数据目录存在"""
        if self.db_type == "sqlite":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def connect(self):
        """连接到数据库"""
        if not self.conn:
            if self.db_type == "mysql":
                self.conn = pymysql.connect(**self.config)
            else:  # sqlite
                self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
                self.conn.row_factory = sqlite3.Row
                # 启用WAL模式以支持并发
                self.conn.execute("PRAGMA journal_mode=WAL")
                self.conn.execute("PRAGMA synchronous=NORMAL")
        return self.conn

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None

    @contextmanager
    def get_cursor(self):
        """获取游标的上下文管理器"""
        conn = self.connect()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()

    def initialize(self):
        """初始化数据库结构"""
        if self.db_type == "mysql":
            self._initialize_mysql()
        else:
            self._initialize_sqlite()

    def _initialize_mysql(self):
        """初始化MySQL数据库"""
        schema_files = [
            "mysql_init.sql",
            "bot_pool_schema.sql",
            "authorized_users_schema_mysql.sql"  # MySQL版本
        ]

        print(f"🔧 正在初始化 MySQL 数据库: {self.config['database']}")

        with self.get_cursor() as cursor:
            for schema_file in schema_files:
                schema_path = Path(__file__).parent / schema_file
                if schema_path.exists():
                    print(f"   📄 执行: {schema_file}")
                    with open(schema_path, 'r', encoding='utf-8') as f:
                        # 分割SQL语句（MySQL不支持executescript）
                        sql_commands = f.read().split(';')
                        for command in sql_commands:
                            command = command.strip()
                            if command and not command.startswith('--'):
                                try:
                                    cursor.execute(command)
                                except Exception as e:
                                    # 忽略已存在的表等警告
                                    if "already exists" not in str(e).lower():
                                        print(f"      ⚠️  Warning: {e}")

        print(f"✅ MySQL 数据库初始化完成: {self.config['host']}:{self.config['port']}/{self.config['database']}")

    def _initialize_sqlite(self):
        """初始化SQLite数据库"""
        schema_files = [
            "schema.sql",
            "authorized_users_schema.sql",  # SQLite版本
        ]

        print(f"🔧 正在初始化 SQLite 数据库: {self.db_path}")

        conn = self.connect()
        for schema_file in schema_files:
            schema_path = Path(__file__).parent / schema_file
            if schema_path.exists():
                print(f"   📄 执行: {schema_file}")
                with open(schema_path, 'r', encoding='utf-8') as f:
                    schema_sql = f.read()
                    conn.executescript(schema_sql)

        conn.commit()
        print(f"✅ SQLite 数据库初始化完成: {self.db_path}")

    def _convert_placeholders(self, query: str) -> str:
        """转换占位符：SQLite用?, MySQL用%s"""
        if self.db_type == "mysql":
            return query.replace('?', '%s')
        return query

    def execute(self, query: str, params: tuple = ()):
        """执行SQL查询"""
        query = self._convert_placeholders(query)
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor

    def fetchone(self, query: str, params: tuple = ()):
        """查询单条记录"""
        query = self._convert_placeholders(query)
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(query, params)
        result = cursor.fetchone()
        cursor.close()
        return result

    def fetchall(self, query: str, params: tuple = ()):
        """查询多条记录"""
        query = self._convert_placeholders(query)
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(query, params)
        results = cursor.fetchall()
        cursor.close()
        return results

    # ========== 账号管理 ==========

    def add_account(self, phone: str, session_type: str, session_data: str,
                   api_id: str = None, api_hash: str = None):
        """添加账号"""
        query = """
            INSERT INTO accounts (phone, session_type, session_data, api_id, api_hash)
            VALUES (?, ?, ?, ?, ?)
        """
        return self.execute(query, (phone, session_type, session_data, api_id, api_hash))

    def get_account(self, account_id: int):
        """获取账号信息"""
        query = "SELECT * FROM accounts WHERE id = ?"
        return self.fetchone(query, (account_id,))

    def get_account_by_phone(self, phone: str):
        """通过手机号获取账号"""
        query = "SELECT * FROM accounts WHERE phone = ?"
        return self.fetchone(query, (phone,))

    def update_account_status(self, account_id: int, status: str):
        """更新账号状态"""
        query = """
            UPDATE accounts
            SET status = ?, last_check = ?, updated_at = ?
            WHERE id = ?
        """
        now = datetime.now()
        return self.execute(query, (status, now, now, account_id))

    def list_accounts(self, status: str = None):
        """列出所有账号"""
        if status:
            query = "SELECT * FROM accounts WHERE status = ? ORDER BY created_at DESC"
            return self.fetchall(query, (status,))
        else:
            query = "SELECT * FROM accounts ORDER BY created_at DESC"
            return self.fetchall(query)

    # ========== TGAPI管理 ==========

    def create_tgapi_session(self, account_id: int, session_data: str,
                            api_token: str, api_url: str, expire_at=None,
                            max_login: int = -1, custom_copyright: str = None):
        """创建TGAPI会话"""
        query = """
            INSERT INTO tgapi_sessions
            (account_id, session_data, api_token, api_url, expire_at, max_login, custom_copyright)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        return self.execute(query, (account_id, session_data, api_token, api_url,
                                   expire_at, max_login, custom_copyright))

    def get_tgapi_session(self, api_token: str):
        """获取TGAPI会话"""
        query = "SELECT * FROM tgapi_sessions WHERE api_token = ?"
        return self.fetchone(query, (api_token,))

    def increment_login_count(self, api_token: str):
        """增加登录次数"""
        query = """
            UPDATE tgapi_sessions
            SET login_count = login_count + 1
            WHERE api_token = ?
        """
        return self.execute(query, (api_token,))

    def add_code_push_log(self, api_token: str, code: str, ip_address: str = None):
        """添加验证码推送日志"""
        query = """
            INSERT INTO code_push_logs (api_token, code, ip_address)
            VALUES (?, ?, ?)
        """
        return self.execute(query, (api_token, code, ip_address))

    # ========== 操作日志 ==========

    def log_operation(self, account_id: int, operation: str, details: str,
                     result: str, error_message: str = None):
        """记录操作日志"""
        query = """
            INSERT INTO operation_logs (account_id, operation, details, result, error_message)
            VALUES (?, ?, ?, ?, ?)
        """
        return self.execute(query, (account_id, operation, details, result, error_message))

    # ========== 统计信息 ==========

    def get_stats(self):
        """获取统计信息"""
        stats = {}

        # 账号总数
        result = self.fetchone("SELECT COUNT(*) as count FROM accounts")
        stats['total_accounts'] = result['count'] if result else 0

        # 活跃账号数
        result = self.fetchone("SELECT COUNT(*) as count FROM accounts WHERE status = 'active'")
        stats['active_accounts'] = result['count'] if result else 0

        # TGAPI会话数
        result = self.fetchone("SELECT COUNT(*) as count FROM tgapi_sessions WHERE status = 'active'")
        stats['active_tgapi_sessions'] = result['count'] if result else 0

        # 今日验证码推送数
        result = self.fetchone("""
            SELECT COUNT(*) as count FROM code_push_logs
            WHERE DATE(push_time) = DATE('now')
        """)
        stats['today_code_pushes'] = result['count'] if result else 0

        return stats


# 全局数据库实例（从环境变量加载配置）
def create_database_from_env():
    """从环境变量创建数据库实例"""
    db_type = os.getenv('DATABASE_TYPE', 'sqlite').lower()

    if db_type == 'mysql':
        return Database(
            db_type='mysql',
            host=os.getenv('MYSQL_HOST', 'localhost'),
            port=int(os.getenv('MYSQL_PORT', 3306)),
            user=os.getenv('MYSQL_USER', 'root'),
            password=os.getenv('MYSQL_PASSWORD', ''),
            database=os.getenv('MYSQL_DATABASE', 'tgbot'),
            charset=os.getenv('MYSQL_CHARSET', 'utf8mb4')
        )
    else:  # sqlite
        return Database(
            db_type='sqlite',
            db_path=os.getenv('DATABASE_PATH', 'data/bot.db')
        )

# 全局数据库实例
db = create_database_from_env()

if __name__ == "__main__":
    # 初始化数据库
    db.initialize()
    print("数据库初始化完成！")

    # 显示统计信息
    stats = db.get_stats()
    print(f"\n📊 统计信息:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
