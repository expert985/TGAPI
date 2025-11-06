"""
数据库初始化模块
"""
import sqlite3
import os
from pathlib import Path
from typing import Optional
from datetime import datetime

class Database:
    def __init__(self, db_path: str = "data/bot.db"):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._ensure_data_dir()

    def _ensure_data_dir(self):
        """确保数据目录存在"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def connect(self):
        """连接到数据库"""
        if not self.conn:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
        return self.conn

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None

    def initialize(self):
        """初始化数据库结构"""
        schema_path = Path(__file__).parent / "schema.sql"
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()

        conn = self.connect()
        conn.executescript(schema_sql)
        conn.commit()
        print(f"✅ 数据库初始化完成: {self.db_path}")

    def execute(self, query: str, params: tuple = ()):
        """执行SQL查询"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor

    def fetchone(self, query: str, params: tuple = ()):
        """查询单条记录"""
        cursor = self.execute(query, params)
        return cursor.fetchone()

    def fetchall(self, query: str, params: tuple = ()):
        """查询多条记录"""
        cursor = self.execute(query, params)
        return cursor.fetchall()

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


# 全局数据库实例
db = Database()

if __name__ == "__main__":
    # 初始化数据库
    db.initialize()
    print("数据库初始化完成！")

    # 显示统计信息
    stats = db.get_stats()
    print(f"\n📊 统计信息:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
