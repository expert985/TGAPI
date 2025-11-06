# 🚀 MySQL 8.0 + Redis 高性能架构方案

## 📊 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                    Telegram Bot Manager                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐      ┌──────────────┐      ┌───────────┐ │
│  │  Bot/API     │◄────►│    Redis     │◄────►│  MySQL    │ │
│  │  Application │      │   (Cache)    │      │  8.0+     │ │
│  └──────────────┘      └──────────────┘      └───────────┘ │
│         │                     │                     │         │
│         │                     │                     │         │
│    热数据缓存           会话/队列缓存         持久化存储      │
│    (API响应)            (TGAPI验证码)         (所有数据)     │
└─────────────────────────────────────────────────────────────┘
```

## 🎯 技术选型理由

### MySQL 8.0+
- ✅ **原生JSON支持** - 存储session_data等复杂数据
- ✅ **窗口函数** - 高效的排名和分页查询
- ✅ **CTE递归查询** - 复杂的层级查询
- ✅ **更快的查询优化器** - 性能提升40%+
- ✅ **InnoDB增强** - 支持更高并发
- ✅ **MGR高可用** - MySQL Group Replication

### Redis 7.0+
- ✅ **高速缓存** - 内存访问，毫秒级响应
- ✅ **分布式锁** - 防止并发冲突
- ✅ **消息队列** - 验证码推送队列
- ✅ **会话存储** - TGAPI活跃会话
- ✅ **计数器** - API调用统计
- ✅ **过期自动清理** - TTL机制

---

## 🗄️ MySQL 8.0 数据库设计

### 表结构设计（优化版）

```sql
-- =====================================================
-- MySQL 8.0+ Schema for TG Bot Manager
-- =====================================================

-- 设置字符集和排序规则
SET NAMES utf8mb4;
SET character_set_client = utf8mb4;

-- 账号管理表
CREATE TABLE `accounts` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `tenant_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '租户ID',
  `phone` VARCHAR(20) NOT NULL COMMENT '手机号',
  `session_type` ENUM('tdata', 'session', 'json', 'authkey') NOT NULL COMMENT 'Session类型',
  `session_data` JSON NOT NULL COMMENT 'Session数据（JSON格式）',
  `api_id` VARCHAR(50) DEFAULT NULL COMMENT 'API ID',
  `api_hash` VARCHAR(100) DEFAULT NULL COMMENT 'API Hash',
  `password` VARCHAR(255) DEFAULT NULL COMMENT '密码（加密）',
  `email` VARCHAR(100) DEFAULT NULL COMMENT '邮箱',
  `two_fa_secret` VARCHAR(255) DEFAULT NULL COMMENT '2FA密钥',
  `status` ENUM('active', 'banned', 'expired', 'unknown') DEFAULT 'active' COMMENT '状态',
  `last_check` DATETIME DEFAULT NULL COMMENT '最后检查时间',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_phone` (`phone`),
  KEY `idx_tenant_status` (`tenant_id`, `status`),
  KEY `idx_status_updated` (`status`, `updated_at`),
  KEY `idx_last_check` (`last_check`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='账号管理表';

-- 创建JSON索引（MySQL 8.0新特性）
ALTER TABLE `accounts` ADD INDEX `idx_session_api_id` ((CAST(session_data->>'$.api_id' AS CHAR(50))));

-- TGAPI会话表
CREATE TABLE `tgapi_sessions` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `tenant_id` BIGINT UNSIGNED DEFAULT NULL,
  `account_id` BIGINT UNSIGNED DEFAULT NULL,
  `session_data` TEXT NOT NULL COMMENT 'Session字符串',
  `api_token` VARCHAR(100) NOT NULL COMMENT 'API Token',
  `api_url` VARCHAR(500) NOT NULL COMMENT 'API URL',
  `expire_at` DATETIME DEFAULT NULL COMMENT '过期时间',
  `max_login` INT DEFAULT -1 COMMENT '最大登录次数',
  `login_count` INT DEFAULT 0 COMMENT '已登录次数',
  `custom_copyright` VARCHAR(200) DEFAULT NULL COMMENT '自定义版权',
  `show_2fa` TINYINT(1) DEFAULT 1 COMMENT '是否显示2FA',
  `status` ENUM('active', 'expired', 'disabled') DEFAULT 'active',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_api_token` (`api_token`),
  KEY `idx_tenant_status` (`tenant_id`, `status`),
  KEY `idx_status_expire` (`status`, `expire_at`),
  KEY `idx_account` (`account_id`),
  CONSTRAINT `fk_tgapi_account` FOREIGN KEY (`account_id`) REFERENCES `accounts` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='TGAPI会话表';

-- 验证码推送日志表（使用分区表优化）
CREATE TABLE `code_push_logs` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `api_token` VARCHAR(100) NOT NULL,
  `code` VARCHAR(20) NOT NULL,
  `push_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `ip_address` VARCHAR(50) DEFAULT NULL,
  `user_agent` VARCHAR(500) DEFAULT NULL,
  PRIMARY KEY (`id`, `push_time`),
  KEY `idx_api_token` (`api_token`),
  KEY `idx_push_time` (`push_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
PARTITION BY RANGE (TO_DAYS(`push_time`)) (
  PARTITION p_history VALUES LESS THAN (TO_DAYS('2024-01-01')),
  PARTITION p_2024_q1 VALUES LESS THAN (TO_DAYS('2024-04-01')),
  PARTITION p_2024_q2 VALUES LESS THAN (TO_DAYS('2024-07-01')),
  PARTITION p_2024_q3 VALUES LESS THAN (TO_DAYS('2024-10-01')),
  PARTITION p_2024_q4 VALUES LESS THAN (TO_DAYS('2025-01-01')),
  PARTITION p_future VALUES LESS THAN MAXVALUE
) COMMENT='验证码推送日志表（分区表）';

-- 操作日志表
CREATE TABLE `operation_logs` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `account_id` BIGINT UNSIGNED DEFAULT NULL,
  `tenant_id` BIGINT UNSIGNED DEFAULT NULL,
  `operation` VARCHAR(50) NOT NULL COMMENT '操作类型',
  `details` TEXT COMMENT '详细信息',
  `result` ENUM('success', 'failed', 'partial') DEFAULT 'success',
  `error_message` TEXT,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_account` (`account_id`),
  KEY `idx_tenant_operation` (`tenant_id`, `operation`),
  KEY `idx_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='操作日志表';

-- 租户表
CREATE TABLE `tenants` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `tenant_code` VARCHAR(50) NOT NULL COMMENT '租户代码',
  `tenant_name` VARCHAR(100) NOT NULL COMMENT '租户名称',
  `contact_info` VARCHAR(200) DEFAULT NULL,
  `license_key` VARCHAR(100) NOT NULL COMMENT '许可证密钥',
  `license_type` ENUM('trial', 'monthly', 'yearly', 'lifetime') NOT NULL,
  `expire_at` DATETIME DEFAULT NULL,
  `max_accounts` INT DEFAULT 10 COMMENT '最大账号数',
  `max_tgapi_sessions` INT DEFAULT 5 COMMENT '最大TGAPI会话数',
  `features` JSON COMMENT '功能列表',
  `status` ENUM('active', 'suspended', 'expired') DEFAULT 'active',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_tenant_code` (`tenant_code`),
  UNIQUE KEY `uk_license_key` (`license_key`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='租户表';

-- 许可证验证记录表
CREATE TABLE `license_validations` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `tenant_id` BIGINT UNSIGNED NOT NULL,
  `machine_id` VARCHAR(100) NOT NULL,
  `ip_address` VARCHAR(50) DEFAULT NULL,
  `validation_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `status` ENUM('success', 'failed', 'expired', 'invalid') NOT NULL,
  `error_message` VARCHAR(500) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_tenant` (`tenant_id`),
  KEY `idx_validation_time` (`validation_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='许可证验证记录';

-- 许可证绑定设备表
CREATE TABLE `license_devices` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `tenant_id` BIGINT UNSIGNED NOT NULL,
  `machine_id` VARCHAR(100) NOT NULL,
  `device_info` JSON COMMENT '设备信息',
  `first_bind_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `last_active_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `bind_count` INT DEFAULT 1,
  `status` ENUM('active', 'revoked') DEFAULT 'active',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_tenant_machine` (`tenant_id`, `machine_id`),
  KEY `idx_machine` (`machine_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='设备绑定表';

-- 使用MySQL 8.0窗口函数创建视图
CREATE OR REPLACE VIEW `v_tenant_stats` AS
SELECT
  t.id AS tenant_id,
  t.tenant_name,
  t.status AS tenant_status,
  COUNT(DISTINCT a.id) AS accounts_count,
  COUNT(DISTINCT CASE WHEN a.status = 'active' THEN a.id END) AS active_accounts,
  COUNT(DISTINCT ts.id) AS tgapi_sessions_count,
  COUNT(DISTINCT ld.id) AS devices_count,
  t.max_accounts,
  t.max_tgapi_sessions,
  ROUND(COUNT(DISTINCT a.id) * 100.0 / t.max_accounts, 2) AS accounts_usage_percent
FROM tenants t
LEFT JOIN accounts a ON t.id = a.tenant_id
LEFT JOIN tgapi_sessions ts ON t.id = ts.tenant_id AND ts.status = 'active'
LEFT JOIN license_devices ld ON t.id = ld.tenant_id AND ld.status = 'active'
GROUP BY t.id;
```

---

## 📦 Redis 缓存设计

### Redis 键命名规范

```
项目:模块:功能:标识

示例:
tgbot:account:info:{account_id}
tgbot:tgapi:session:{api_token}
tgbot:cache:stats:tenant:{tenant_id}
tgbot:queue:codes:{api_token}
```

### 缓存策略

```python
# Redis数据结构设计

# 1. 账号信息缓存 (Hash)
# Key: tgbot:account:info:{account_id}
# TTL: 1小时
# 数据: {phone, status, last_check, ...}

# 2. TGAPI验证码队列 (List)
# Key: tgbot:queue:codes:{api_token}
# TTL: 5分钟
# 数据: [验证码1, 验证码2, ...]

# 3. 会话活跃状态 (String)
# Key: tgbot:session:active:{api_token}
# TTL: 根据expire_at动态设置
# 数据: "1" (存在即活跃)

# 4. 租户统计缓存 (Hash)
# Key: tgbot:cache:stats:tenant:{tenant_id}
# TTL: 5分钟
# 数据: {accounts_count, active_accounts, ...}

# 5. API调用计数器 (String with INCR)
# Key: tgbot:counter:api:daily:{date}
# TTL: 7天
# 数据: 整数计数

# 6. 分布式锁 (String with NX EX)
# Key: tgbot:lock:account:{account_id}
# TTL: 30秒
# 数据: 随机UUID
```

---

## 🔧 Python集成实现

### 1. 安装依赖

```bash
# MySQL驱动
pip install pymysql aiomysql sqlalchemy

# Redis驱动
pip install redis aioredis

# 连接池
pip install DBUtils
```

### 2. 数据库连接管理

```python
# shared/database/mysql_manager.py

import aiomysql
from typing import Optional
from contextlib import asynccontextmanager
import json

class MySQLManager:
    """MySQL 8.0 连接管理器"""

    def __init__(self, host: str, port: int, database: str,
                 user: str, password: str,
                 pool_size: int = 10):
        self.config = {
            'host': host,
            'port': port,
            'db': database,
            'user': user,
            'password': password,
            'charset': 'utf8mb4',
            'autocommit': False,
            'pool_recycle': 3600,  # 连接回收时间
        }
        self.pool_size = pool_size
        self.pool: Optional[aiomysql.Pool] = None

    async def create_pool(self):
        """创建连接池"""
        self.pool = await aiomysql.create_pool(
            minsize=2,
            maxsize=self.pool_size,
            **self.config
        )
        logger.info(f"✅ MySQL连接池创建成功 (池大小: {self.pool_size})")

    async def close_pool(self):
        """关闭连接池"""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            logger.info("MySQL连接池已关闭")

    @asynccontextmanager
    async def acquire(self):
        """获取数据库连接（上下文管理器）"""
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                yield cursor
                await conn.commit()

    async def execute(self, query: str, params: tuple = None):
        """执行SQL（INSERT/UPDATE/DELETE）"""
        async with self.acquire() as cursor:
            await cursor.execute(query, params or ())
            return cursor.rowcount

    async def fetchone(self, query: str, params: tuple = None):
        """查询单条记录"""
        async with self.acquire() as cursor:
            await cursor.execute(query, params or ())
            return await cursor.fetchone()

    async def fetchall(self, query: str, params: tuple = None):
        """查询多条记录"""
        async with self.acquire() as cursor:
            await cursor.execute(query, params or ())
            return await cursor.fetchall()

    # ========== 账号管理 ==========

    async def add_account(self, phone: str, session_type: str,
                         session_data: dict, api_id: str = None,
                         api_hash: str = None, tenant_id: int = None):
        """添加账号（使用JSON存储session_data）"""
        query = """
            INSERT INTO accounts
            (tenant_id, phone, session_type, session_data, api_id, api_hash)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        session_json = json.dumps(session_data)

        async with self.acquire() as cursor:
            await cursor.execute(query, (
                tenant_id, phone, session_type,
                session_json, api_id, api_hash
            ))
            return cursor.lastrowid

    async def get_account(self, account_id: int):
        """获取账号信息"""
        query = "SELECT * FROM accounts WHERE id = %s"
        result = await self.fetchone(query, (account_id,))

        # 解析JSON字段
        if result and result.get('session_data'):
            result['session_data'] = json.loads(result['session_data'])

        return result

    async def list_accounts_paginated(self, page: int = 1,
                                     page_size: int = 100,
                                     status: str = None,
                                     tenant_id: int = None):
        """分页查询账号（优化版）"""
        offset = (page - 1) * page_size

        conditions = []
        params = []

        if status:
            conditions.append("status = %s")
            params.append(status)

        if tenant_id:
            conditions.append("tenant_id = %s")
            params.append(tenant_id)

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        # 使用MySQL 8.0窗口函数优化分页
        query = f"""
            SELECT *,
                   ROW_NUMBER() OVER (ORDER BY updated_at DESC) as row_num
            FROM accounts
            {where_clause}
            LIMIT %s OFFSET %s
        """
        params.extend([page_size, offset])

        return await self.fetchall(query, tuple(params))


# 全局实例
mysql_manager = MySQLManager(
    host=os.getenv('MYSQL_HOST', 'localhost'),
    port=int(os.getenv('MYSQL_PORT', 3306)),
    database=os.getenv('MYSQL_DATABASE', 'tgbot'),
    user=os.getenv('MYSQL_USER', 'tgbot_user'),
    password=os.getenv('MYSQL_PASSWORD', ''),
    pool_size=int(os.getenv('MYSQL_POOL_SIZE', 10))
)
```

### 3. Redis缓存管理

```python
# shared/cache/redis_manager.py

import aioredis
import json
from typing import Optional, Any
from datetime import timedelta

class RedisManager:
    """Redis 7.0 缓存管理器"""

    def __init__(self, host: str = 'localhost', port: int = 6379,
                 db: int = 0, password: Optional[str] = None,
                 decode_responses: bool = True):
        self.config = {
            'host': host,
            'port': port,
            'db': db,
            'password': password,
            'decode_responses': decode_responses,
            'encoding': 'utf-8'
        }
        self.redis: Optional[aioredis.Redis] = None
        self.prefix = "tgbot"

    async def connect(self):
        """连接Redis"""
        self.redis = await aioredis.from_url(
            f"redis://{self.config['host']}:{self.config['port']}/{self.config['db']}",
            password=self.config.get('password'),
            decode_responses=self.config['decode_responses'],
            encoding=self.config['encoding']
        )
        logger.info("✅ Redis连接成功")

    async def close(self):
        """关闭连接"""
        if self.redis:
            await self.redis.close()
            logger.info("Redis连接已关闭")

    def _make_key(self, *parts):
        """生成Redis键"""
        return f"{self.prefix}:" + ":".join(str(p) for p in parts)

    # ========== 基础操作 ==========

    async def get(self, key: str) -> Optional[str]:
        """获取值"""
        full_key = self._make_key(key)
        return await self.redis.get(full_key)

    async def set(self, key: str, value: Any, expire: int = None):
        """设置值"""
        full_key = self._make_key(key)
        if expire:
            await self.redis.setex(full_key, expire, value)
        else:
            await self.redis.set(full_key, value)

    async def delete(self, key: str):
        """删除键"""
        full_key = self._make_key(key)
        await self.redis.delete(full_key)

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        full_key = self._make_key(key)
        return await self.redis.exists(full_key)

    # ========== 账号缓存 ==========

    async def cache_account(self, account_id: int, account_data: dict,
                           ttl: int = 3600):
        """缓存账号信息"""
        key = f"account:info:{account_id}"
        await self.redis.hset(
            self._make_key(key),
            mapping={k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                    for k, v in account_data.items()}
        )
        await self.redis.expire(self._make_key(key), ttl)

    async def get_cached_account(self, account_id: int) -> Optional[dict]:
        """获取缓存的账号信息"""
        key = f"account:info:{account_id}"
        data = await self.redis.hgetall(self._make_key(key))

        if not data:
            return None

        # 解析JSON字段
        result = {}
        for k, v in data.items():
            try:
                result[k] = json.loads(v)
            except:
                result[k] = v

        return result

    # ========== TGAPI验证码队列 ==========

    async def push_code(self, api_token: str, code: str, ttl: int = 300):
        """推送验证码到队列"""
        key = f"queue:codes:{api_token}"
        full_key = self._make_key(key)

        await self.redis.lpush(full_key, code)
        await self.redis.expire(full_key, ttl)

    async def pop_code(self, api_token: str, timeout: int = 60) -> Optional[str]:
        """从队列获取验证码（阻塞）"""
        key = f"queue:codes:{api_token}"
        full_key = self._make_key(key)

        result = await self.redis.blpop(full_key, timeout=timeout)
        return result[1] if result else None

    # ========== 会话管理 ==========

    async def mark_session_active(self, api_token: str, ttl: int):
        """标记会话为活跃"""
        key = f"session:active:{api_token}"
        await self.set(key, "1", expire=ttl)

    async def is_session_active(self, api_token: str) -> bool:
        """检查会话是否活跃"""
        key = f"session:active:{api_token}"
        return await self.exists(key)

    # ========== 统计缓存 ==========

    async def cache_tenant_stats(self, tenant_id: int, stats: dict, ttl: int = 300):
        """缓存租户统计信息"""
        key = f"cache:stats:tenant:{tenant_id}"
        await self.redis.hset(
            self._make_key(key),
            mapping={k: str(v) for k, v in stats.items()}
        )
        await self.redis.expire(self._make_key(key), ttl)

    async def get_tenant_stats(self, tenant_id: int) -> Optional[dict]:
        """获取租户统计（带缓存）"""
        key = f"cache:stats:tenant:{tenant_id}"
        data = await self.redis.hgetall(self._make_key(key))

        if data:
            return {k: int(v) if v.isdigit() else v for k, v in data.items()}
        return None

    # ========== API调用计数 ==========

    async def incr_api_calls(self, date_str: str):
        """增加API调用计数"""
        key = f"counter:api:daily:{date_str}"
        full_key = self._make_key(key)

        await self.redis.incr(full_key)
        await self.redis.expire(full_key, 7 * 24 * 3600)  # 保留7天

    async def get_api_calls(self, date_str: str) -> int:
        """获取API调用次数"""
        key = f"counter:api:daily:{date_str}"
        result = await self.get(key)
        return int(result) if result else 0

    # ========== 分布式锁 ==========

    async def acquire_lock(self, resource: str, ttl: int = 30) -> Optional[str]:
        """获取分布式锁"""
        import uuid
        lock_id = str(uuid.uuid4())
        key = f"lock:{resource}"
        full_key = self._make_key(key)

        # SET NX EX - 仅当key不存在时设置，并设置过期时间
        success = await self.redis.set(full_key, lock_id, ex=ttl, nx=True)
        return lock_id if success else None

    async def release_lock(self, resource: str, lock_id: str) -> bool:
        """释放分布式锁"""
        key = f"lock:{resource}"
        full_key = self._make_key(key)

        # Lua脚本确保原子性
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        result = await self.redis.eval(lua_script, 1, full_key, lock_id)
        return result == 1


# 全局实例
redis_manager = RedisManager(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    db=int(os.getenv('REDIS_DB', 0)),
    password=os.getenv('REDIS_PASSWORD')
)
```

### 4. 缓存穿透优化

```python
# shared/cache/cache_helper.py

from functools import wraps
from typing import Callable, Any
import asyncio

def cache_aside(
    key_func: Callable,
    ttl: int = 3600,
    cache_none: bool = False
):
    """
    Cache-Aside缓存装饰器

    Args:
        key_func: 生成缓存key的函数
        ttl: 缓存过期时间
        cache_none: 是否缓存None值（防止缓存穿透）
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存key
            cache_key = key_func(*args, **kwargs)

            # 1. 尝试从Redis获取
            cached = await redis_manager.get(cache_key)
            if cached is not None:
                if cached == "NULL":  # 空值标记
                    return None
                return json.loads(cached)

            # 2. 缓存未命中，从MySQL查询
            result = await func(*args, **kwargs)

            # 3. 写入Redis
            if result is not None:
                await redis_manager.set(
                    cache_key,
                    json.dumps(result),
                    expire=ttl
                )
            elif cache_none:
                # 缓存空值，防止缓存穿透
                await redis_manager.set(cache_key, "NULL", expire=60)

            return result

        return wrapper
    return decorator


# 使用示例
@cache_aside(
    key_func=lambda account_id: f"account:info:{account_id}",
    ttl=3600,
    cache_none=True
)
async def get_account_with_cache(account_id: int):
    """获取账号（带缓存）"""
    return await mysql_manager.get_account(account_id)
```

---

## 🐳 Docker Compose配置

```yaml
# docker-compose.yml (更新版)

version: '3.8'

services:
  # MySQL 8.0
  mysql:
    image: mysql:8.0
    container_name: tgbot_mysql
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: ${MYSQL_DATABASE:-tgbot}
      MYSQL_USER: ${MYSQL_USER:-tgbot_user}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
    ports:
      - "${MYSQL_PORT:-3306}:3306"
    volumes:
      - mysql_data:/var/lib/mysql
      - ./docs/MYSQL_REDIS_ARCHITECTURE.md:/docker-entrypoint-initdb.d/schema.sql:ro
    command:
      - --character-set-server=utf8mb4
      - --collation-server=utf8mb4_unicode_ci
      - --default-authentication-plugin=mysql_native_password
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 3
    networks:
      - tgbot_network

  # Redis 7.0
  redis:
    image: redis:7.0-alpine
    container_name: tgbot_redis
    restart: unless-stopped
    ports:
      - "${REDIS_PORT:-6379}:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3
    networks:
      - tgbot_network

  # API服务
  api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: tgbot_api
    restart: unless-stopped
    ports:
      - "${SERVER_PORT:-52000}:52000"
    volumes:
      - ./data:/app/data
      - ./sessions:/app/sessions
      - ./logs:/app/logs
    environment:
      - BOT_TOKEN=${BOT_TOKEN}
      - API_ID=${API_ID}
      - API_HASH=${API_HASH}
      - MYSQL_HOST=mysql
      - MYSQL_PORT=3306
      - MYSQL_DATABASE=${MYSQL_DATABASE:-tgbot}
      - MYSQL_USER=${MYSQL_USER:-tgbot_user}
      - MYSQL_PASSWORD=${MYSQL_PASSWORD}
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      - SERVER_PORT=52000
    depends_on:
      mysql:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - tgbot_network

  # Telegram Bot
  bot:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: tgbot_bot
    restart: unless-stopped
    command: python -m bot.main
    volumes:
      - ./data:/app/data
      - ./sessions:/app/sessions
      - ./logs:/app/logs
    environment:
      - BOT_TOKEN=${BOT_TOKEN}
      - API_ID=${API_ID}
      - API_HASH=${API_HASH}
      - MYSQL_HOST=mysql
      - MYSQL_PORT=3306
      - MYSQL_DATABASE=${MYSQL_DATABASE:-tgbot}
      - MYSQL_USER=${MYSQL_USER:-tgbot_user}
      - MYSQL_PASSWORD=${MYSQL_PASSWORD}
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - REDIS_PASSWORD=${REDIS_PASSWORD}
    depends_on:
      api:
        condition: service_started
    networks:
      - tgbot_network

networks:
  tgbot_network:
    driver: bridge

volumes:
  mysql_data:
  redis_data:
```

---

## ⚙️ 环境配置

```bash
# .env

# MySQL配置
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=tgbot
MYSQL_USER=tgbot_user
MYSQL_PASSWORD=your_strong_password_here
MYSQL_ROOT_PASSWORD=your_root_password_here
MYSQL_POOL_SIZE=10

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=your_redis_password_here

# Telegram Bot配置
BOT_TOKEN=your_bot_token
API_ID=your_api_id
API_HASH=your_api_hash

# 服务器配置
SERVER_PORT=52000
DEBUG=false
```

---

## 📊 性能对比

| 操作 | SQLite | MySQL 8.0 | MySQL+Redis |
|-----|--------|-----------|-------------|
| 查询单个账号 | 5-10ms | 2-5ms | **0.1-1ms** |
| 分页查询100条 | 50-100ms | 20-50ms | **5-10ms** (首次) |
| 插入1000条 | 2-5s | 1-2s | **0.5-1s** |
| 并发100请求 | ❌ 阻塞 | ✅ 正常 | ✅ 优秀 |
| 百万级查询 | ❌ 很慢 | ✅ 可用 | ✅ 快速 |

---

## 🎯 建议配置

### 开发环境
- MySQL: 默认配置
- Redis: 默认配置
- 缓存TTL: 较短（5分钟）

### 生产环境
- MySQL: 调优配置（innodb_buffer_pool_size等）
- Redis: 持久化配置（AOF + RDB）
- 缓存TTL: 较长（1小时）
- 连接池: 根据并发调整

---

**总结**: MySQL 8.0提供强大的持久化和查询能力，Redis提供高速缓存和实时数据，两者结合可完美支持百万级账号的高并发场景。
