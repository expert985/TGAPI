-- =====================================================
-- Telegram Bot Manager Database Schema
-- =====================================================

-- 账号管理表
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT UNIQUE,
    session_type TEXT NOT NULL, -- 'tdata', 'session', 'json', 'authkey'
    session_data TEXT NOT NULL,
    api_id TEXT,
    api_hash TEXT,
    password TEXT,
    email TEXT,
    two_fa_secret TEXT,
    status TEXT DEFAULT 'active', -- 'active', 'banned', 'expired', 'unknown'
    last_check DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- TGAPI接码链接表
CREATE TABLE IF NOT EXISTS tgapi_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER,
    session_data TEXT NOT NULL,
    api_token TEXT UNIQUE NOT NULL,
    api_url TEXT NOT NULL,
    expire_at DATETIME,
    max_login INTEGER DEFAULT -1, -- -1表示无限制
    login_count INTEGER DEFAULT 0,
    custom_copyright TEXT,
    show_2fa BOOLEAN DEFAULT 1,
    status TEXT DEFAULT 'active', -- 'active', 'expired', 'disabled'
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
);

-- 验证码推送记录表
CREATE TABLE IF NOT EXISTS code_push_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    api_token TEXT NOT NULL,
    code TEXT NOT NULL,
    push_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    ip_address TEXT,
    user_agent TEXT,
    FOREIGN KEY (api_token) REFERENCES tgapi_sessions(api_token)
);

-- 操作日志表
CREATE TABLE IF NOT EXISTS operation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER,
    operation TEXT NOT NULL, -- 'protect', 'clean', 'check', 'convert', 'maintain'
    details TEXT,
    result TEXT, -- 'success', 'failed', 'partial'
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE SET NULL
);

-- 格式转换记录表
CREATE TABLE IF NOT EXISTS conversion_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    input_format TEXT NOT NULL,
    output_format TEXT NOT NULL,
    input_file TEXT,
    output_file TEXT,
    status TEXT DEFAULT 'success',
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 自动做号记录表
CREATE TABLE IF NOT EXISTS autogen_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    api_id TEXT NOT NULL,
    api_hash TEXT NOT NULL,
    output_format TEXT NOT NULL, -- 'tdata', 'session', 'json', 'authkey'
    output_path TEXT,
    phone TEXT,
    status TEXT DEFAULT 'pending', -- 'pending', 'success', 'failed'
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 账号维护任务表
CREATE TABLE IF NOT EXISTS maintenance_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    task_type TEXT NOT NULL, -- 'keepalive', 'auto_reply', 'status_update'
    interval_hours INTEGER DEFAULT 24,
    last_run DATETIME,
    next_run DATETIME,
    enabled BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
);

-- 用户配置表
CREATE TABLE IF NOT EXISTS user_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id INTEGER UNIQUE NOT NULL,
    username TEXT,
    is_admin BOOLEAN DEFAULT 0,
    max_accounts INTEGER DEFAULT 10,
    api_rate_limit INTEGER DEFAULT 100,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_accounts_phone ON accounts(phone);
CREATE INDEX IF NOT EXISTS idx_accounts_status ON accounts(status);
CREATE INDEX IF NOT EXISTS idx_tgapi_token ON tgapi_sessions(api_token);
CREATE INDEX IF NOT EXISTS idx_tgapi_status ON tgapi_sessions(status);
CREATE INDEX IF NOT EXISTS idx_operation_logs_account ON operation_logs(account_id);
CREATE INDEX IF NOT EXISTS idx_maintenance_next_run ON maintenance_tasks(next_run);
CREATE INDEX IF NOT EXISTS idx_user_configs_telegram_id ON user_configs(telegram_user_id);
