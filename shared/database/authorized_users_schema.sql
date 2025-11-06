-- =====================================================
-- 授权用户表 - 管理有权使用机器人的TG用户
-- =====================================================

CREATE TABLE IF NOT EXISTS `authorized_users` (
  `id` INTEGER PRIMARY KEY AUTOINCREMENT,
  `telegram_id` BIGINT NOT NULL UNIQUE,  -- TG用户ID
  `username` VARCHAR(100),               -- TG用户名（可选）
  `full_name` VARCHAR(200),              -- 用户全名（可选）
  `authorization_level` VARCHAR(20) NOT NULL DEFAULT 'basic',  -- 授权等级: basic, premium, vip
  `authorized_by` VARCHAR(100),          -- 授权管理员
  `authorization_date` DATETIME DEFAULT CURRENT_TIMESTAMP,  -- 授权时间
  `expire_date` DATETIME,                -- 过期时间（NULL为永久）
  `duration_type` VARCHAR(20),           -- 时长类型: 1month, 3months, 6months, 1year, permanent
  `max_accounts` INTEGER DEFAULT 10,     -- 最大账号数
  `max_tgapi_sessions` INTEGER DEFAULT 5,  -- 最大TGAPI会话数
  `status` VARCHAR(20) DEFAULT 'active',  -- 状态: active, expired, suspended
  `payment_info` TEXT,                   -- 付款信息（备注）
  `notes` TEXT,                          -- 备注
  `last_active` DATETIME,                -- 最后活跃时间
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_telegram_id ON authorized_users(telegram_id);
CREATE INDEX IF NOT EXISTS idx_status ON authorized_users(status);
CREATE INDEX IF NOT EXISTS idx_expire_date ON authorized_users(expire_date);

-- =====================================================
-- 授权日志表 - 记录所有授权操作
-- =====================================================

CREATE TABLE IF NOT EXISTS `authorization_logs` (
  `id` INTEGER PRIMARY KEY AUTOINCREMENT,
  `telegram_id` BIGINT NOT NULL,         -- TG用户ID
  `action` VARCHAR(50) NOT NULL,         -- 操作: authorize, renew, suspend, expire
  `duration_type` VARCHAR(20),           -- 时长类型
  `expire_date` DATETIME,                -- 过期时间
  `operated_by` VARCHAR(100),            -- 操作管理员
  `payment_amount` DECIMAL(10,2),        -- 付款金额（可选）
  `notes` TEXT,                          -- 备注
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_auth_telegram_id ON authorization_logs(telegram_id);
CREATE INDEX IF NOT EXISTS idx_auth_action ON authorization_logs(action);

-- =====================================================
-- 未授权访问日志表 - 记录未授权用户的访问尝试
-- =====================================================

CREATE TABLE IF NOT EXISTS `unauthorized_access_logs` (
  `id` INTEGER PRIMARY KEY AUTOINCREMENT,
  `telegram_id` BIGINT NOT NULL,         -- TG用户ID
  `username` VARCHAR(100),               -- TG用户名
  `full_name` VARCHAR(200),              -- 用户全名
  `command` VARCHAR(100),                -- 尝试的命令
  `message` TEXT,                        -- 消息内容
  `access_time` DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_unauth_telegram_id ON unauthorized_access_logs(telegram_id);
CREATE INDEX IF NOT EXISTS idx_unauth_time ON unauthorized_access_logs(access_time);
