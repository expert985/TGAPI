# 🚀 百万级账号扩展性方案

## 📊 当前架构能力评估

### SQLite性能限制
- ✅ **理论容量**：支持2^64行，数据库最大281TB
- ✅ **100万账号**：约200-500MB（取决于session数据大小）
- ⚠️ **写入并发**：单进程写入，多进程读取
- ⚠️ **查询性能**：100万行全表扫描 ~1-5秒

### 实际测试估算

| 账号数量 | 数据库大小 | 查询性能 | 写入性能 | 建议 |
|---------|-----------|---------|---------|------|
| 1K      | 2-5MB     | <10ms   | 快速    | ✅ SQLite |
| 10K     | 20-50MB   | <100ms  | 正常    | ✅ SQLite |
| 100K    | 200-500MB | <1s     | 较慢    | ✅ SQLite + 优化 |
| 1M      | 2-5GB     | 1-5s    | 慢      | ⚠️ SQLite + 重度优化 或 PostgreSQL |
| 10M+    | 20-50GB   | >10s    | 很慢    | ❌ 必须PostgreSQL/MySQL |

## 🔧 百万级优化方案

### 方案1：SQLite优化（适用于100K-1M账号）

#### 1.1 数据库索引优化

```sql
-- 已有索引（在schema.sql中）
CREATE INDEX idx_accounts_phone ON accounts(phone);
CREATE INDEX idx_accounts_status ON accounts(status);

-- 新增复合索引（需要添加）
CREATE INDEX idx_accounts_status_updated ON accounts(status, updated_at);
CREATE INDEX idx_accounts_tenant_status ON accounts(tenant_id, status);
CREATE INDEX idx_tgapi_sessions_status_expire ON tgapi_sessions(status, expire_at);

-- 全文搜索索引（如果需要按用户名搜索）
CREATE VIRTUAL TABLE accounts_fts USING fts5(phone, username, content=accounts);
```

#### 1.2 查询优化

```python
# 使用分页查询
def list_accounts_paginated(page: int = 1, page_size: int = 100, status: str = None):
    """分页查询账号列表"""
    offset = (page - 1) * page_size

    if status:
        query = """
            SELECT * FROM accounts
            WHERE status = ?
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
        """
        return db.fetchall(query, (status, page_size, offset))
    else:
        query = """
            SELECT * FROM accounts
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
        """
        return db.fetchall(query, (page_size, offset))

# 使用COUNT优化
def get_total_accounts(status: str = None):
    """获取总数（带缓存）"""
    if status:
        query = "SELECT COUNT(*) as count FROM accounts WHERE status = ?"
        result = db.fetchone(query, (status,))
    else:
        query = "SELECT COUNT(*) as count FROM accounts"
        result = db.fetchone(query)

    return result['count'] if result else 0
```

#### 1.3 批量操作优化

```python
def batch_update_status(account_ids: list, status: str, batch_size: int = 1000):
    """批量更新状态（分批处理）"""
    for i in range(0, len(account_ids), batch_size):
        batch = account_ids[i:i + batch_size]
        placeholders = ','.join('?' * len(batch))
        query = f"""
            UPDATE accounts
            SET status = ?, updated_at = ?
            WHERE id IN ({placeholders})
        """
        db.execute(query, (status, datetime.now(), *batch))
        db.conn.commit()
```

#### 1.4 WAL模式优化

```python
# 在数据库初始化时启用WAL模式
def initialize():
    """初始化数据库（启用WAL模式）"""
    db.connect()

    # 启用WAL模式（提高并发性能）
    db.conn.execute("PRAGMA journal_mode=WAL")
    db.conn.execute("PRAGMA synchronous=NORMAL")
    db.conn.execute("PRAGMA cache_size=-64000")  # 64MB缓存
    db.conn.execute("PRAGMA temp_store=MEMORY")

    # 执行schema
    # ...
```

### 方案2：PostgreSQL迁移（适用于1M+账号）

#### 2.1 迁移准备

```bash
# 安装PostgreSQL
sudo apt-get install postgresql postgresql-contrib

# 安装Python驱动
pip install psycopg2-binary sqlalchemy
```

#### 2.2 配置文件修改

```python
# shared/config/settings.py

@dataclass
class DatabaseConfig:
    """数据库配置"""
    type: str = "sqlite"  # sqlite 或 postgresql

    # SQLite配置
    sqlite_path: str = "data/bot.db"

    # PostgreSQL配置
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_database: str = "tgbot"
    pg_user: str = "tgbot_user"
    pg_password: str = ""

    @property
    def connection_string(self):
        if self.type == "postgresql":
            return f"postgresql://{self.pg_user}:{self.pg_password}@{self.pg_host}:{self.pg_port}/{self.pg_database}"
        else:
            return f"sqlite:///{self.sqlite_path}"
```

#### 2.3 数据迁移脚本

```python
# tools/migrate_to_postgresql.py

import sqlite3
import psycopg2
from tqdm import tqdm

def migrate_sqlite_to_postgresql():
    """将SQLite数据迁移到PostgreSQL"""

    # 连接SQLite
    sqlite_conn = sqlite3.connect('data/bot.db')
    sqlite_conn.row_factory = sqlite3.Row

    # 连接PostgreSQL
    pg_conn = psycopg2.connect(
        host="localhost",
        database="tgbot",
        user="tgbot_user",
        password="your_password"
    )
    pg_cursor = pg_conn.cursor()

    # 迁移accounts表
    print("迁移accounts表...")
    sqlite_cursor = sqlite_conn.execute("SELECT * FROM accounts")
    accounts = sqlite_cursor.fetchall()

    for account in tqdm(accounts):
        pg_cursor.execute("""
            INSERT INTO accounts (id, phone, session_type, session_data, ...)
            VALUES (%s, %s, %s, %s, ...)
        """, tuple(account))

    pg_conn.commit()
    print("✅ 迁移完成")
```

### 方案3：分库分表（适用于10M+账号）

#### 3.1 按租户分库

```python
# 每个租户使用独立数据库
def get_tenant_db(tenant_id: int):
    """获取租户专属数据库连接"""
    db_path = f"data/tenant_{tenant_id}.db"
    return Database(db_path)
```

#### 3.2 按状态分表

```sql
-- 活跃账号表
CREATE TABLE accounts_active AS SELECT * FROM accounts WHERE status = 'active';

-- 封禁账号表
CREATE TABLE accounts_banned AS SELECT * FROM accounts WHERE status = 'banned';

-- 过期账号表
CREATE TABLE accounts_expired AS SELECT * FROM accounts WHERE status = 'expired';
```

## 🗑️ 失效账号自动清理

### 自动清理策略

#### 策略1：软删除（推荐）

```python
# modules/account-manager/cleanup.py

class AccountCleanup:
    """账号自动清理管理器"""

    async def mark_expired_accounts(self):
        """标记失效账号（软删除）"""
        query = """
            UPDATE accounts
            SET status = 'expired', updated_at = ?
            WHERE status = 'active'
            AND last_check < datetime('now', '-30 days')
        """
        cursor = db.execute(query, (datetime.now(),))
        count = cursor.rowcount
        logger.info(f"✅ 标记了 {count} 个失效账号")
        return count

    async def archive_old_accounts(self):
        """归档旧账号到历史表"""
        # 1. 复制到归档表
        db.execute("""
            INSERT INTO accounts_archive
            SELECT * FROM accounts
            WHERE status IN ('expired', 'banned')
            AND updated_at < datetime('now', '-90 days')
        """)

        # 2. 从主表删除
        cursor = db.execute("""
            DELETE FROM accounts
            WHERE status IN ('expired', 'banned')
            AND updated_at < datetime('now', '-90 days')
        """)

        count = cursor.rowcount
        logger.info(f"✅ 归档了 {count} 个旧账号")
        return count
```

#### 策略2：物理删除（可选）

```python
class AccountCleanup:
    """账号自动清理管理器"""

    async def cleanup_expired_accounts(
        self,
        delete_files: bool = True,
        delete_database: bool = False,
        days_threshold: int = 90
    ):
        """
        清理失效账号

        Args:
            delete_files: 是否删除物理文件（session文件）
            delete_database: 是否从数据库删除记录
            days_threshold: 失效天数阈值
        """
        # 查询失效账号
        query = """
            SELECT id, phone, session_type, status
            FROM accounts
            WHERE status IN ('expired', 'banned')
            AND updated_at < datetime('now', ?)
        """

        expired_accounts = db.fetchall(query, (f"-{days_threshold} days",))

        cleanup_stats = {
            "total": len(expired_accounts),
            "files_deleted": 0,
            "db_records_deleted": 0
        }

        for account in expired_accounts:
            account_id = account['id']
            phone = account['phone']

            # 1. 删除物理文件
            if delete_files:
                deleted = await self._delete_account_files(phone)
                if deleted:
                    cleanup_stats["files_deleted"] += 1

            # 2. 删除数据库记录
            if delete_database:
                db.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
                cleanup_stats["db_records_deleted"] += 1

        logger.info(f"🗑️ 清理完成: {cleanup_stats}")
        return cleanup_stats

    async def _delete_account_files(self, phone: str) -> bool:
        """删除账号相关的所有物理文件"""
        import os
        from pathlib import Path

        deleted = False

        # 删除session文件
        session_patterns = [
            f"sessions/{phone}.session",
            f"sessions/{phone}.json",
            f"sessions/{phone}_tdata/*",
        ]

        for pattern in session_patterns:
            files = Path(".").glob(pattern)
            for file_path in files:
                try:
                    if file_path.is_file():
                        os.remove(file_path)
                        deleted = True
                    elif file_path.is_dir():
                        import shutil
                        shutil.rmtree(file_path)
                        deleted = True
                    logger.info(f"   删除文件: {file_path}")
                except Exception as e:
                    logger.error(f"   删除失败 {file_path}: {str(e)}")

        return deleted


# 全局实例
account_cleanup = AccountCleanup()
```

#### 策略3：定时任务

```python
# 在bot/main.py中添加定时清理任务

from apscheduler.schedulers.asyncio import AsyncIOScheduler

async def scheduled_cleanup():
    """定时清理任务"""
    logger.info("🕐 开始定时清理...")

    # 1. 标记失效账号
    await account_cleanup.mark_expired_accounts()

    # 2. 清理90天前的失效账号
    stats = await account_cleanup.cleanup_expired_accounts(
        delete_files=True,   # 删除物理文件
        delete_database=False,  # 保留数据库记录（归档）
        days_threshold=90
    )

    logger.info(f"✅ 定时清理完成: {stats}")

# 在main函数中启动定时任务
async def main():
    # ... 其他初始化代码

    # 创建调度器
    scheduler = AsyncIOScheduler()

    # 每天凌晨3点执行清理
    scheduler.add_job(
        scheduled_cleanup,
        'cron',
        hour=3,
        minute=0
    )

    scheduler.start()
    logger.info("✅ 定时清理任务已启动（每天3:00执行）")

    # 启动Bot
    # ...
```

## 📋 配置选项

在 `.env` 文件中添加：

```bash
# 清理配置
AUTO_CLEANUP_ENABLED=true
AUTO_CLEANUP_DELETE_FILES=true
AUTO_CLEANUP_DELETE_DATABASE=false
AUTO_CLEANUP_DAYS_THRESHOLD=90
AUTO_CLEANUP_SCHEDULE="0 3 * * *"  # Cron表达式：每天3:00
```

## 🎯 建议方案

### 如果账号数 < 100K
- ✅ 使用当前SQLite架构
- ✅ 添加索引优化
- ✅ 启用WAL模式
- ✅ 实施软删除策略

### 如果账号数 100K - 1M
- ✅ SQLite + 重度优化
- ✅ 分页查询
- ✅ 批量处理
- ✅ 定时清理 + 归档

### 如果账号数 > 1M
- ⚠️ 考虑迁移到PostgreSQL
- ⚠️ 实施分库分表
- ⚠️ 使用Redis缓存
- ⚠️ 读写分离

## 📊 性能监控

```python
# 添加性能监控

import time
from functools import wraps

def monitor_performance(func):
    """性能监控装饰器"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        result = await func(*args, **kwargs)
        elapsed = time.time() - start_time

        if elapsed > 1.0:  # 超过1秒记录警告
            logger.warning(f"⚠️ 慢查询: {func.__name__} 耗时 {elapsed:.2f}秒")

        return result
    return wrapper
```

---

**总结**：当前架构在合理优化后可以支持**100K-1M**账号，超过百万建议迁移PostgreSQL。失效账号建议采用**软删除+定时清理**策略。
