-- =====================================================
-- 租户和许可证管理表
-- =====================================================

-- 租户表
CREATE TABLE IF NOT EXISTS tenants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_code TEXT UNIQUE NOT NULL, -- 租户代码（唯一标识）
    tenant_name TEXT NOT NULL,
    contact_info TEXT,
    license_key TEXT UNIQUE NOT NULL, -- 许可证密钥
    license_type TEXT NOT NULL, -- 'trial', 'monthly', 'yearly', 'lifetime'
    expire_at DATETIME, -- 过期时间（lifetime为NULL）
    max_accounts INTEGER DEFAULT 10, -- 最大账号数
    max_tgapi_sessions INTEGER DEFAULT 5, -- 最大TGAPI会话数
    features TEXT, -- JSON格式的功能列表
    status TEXT DEFAULT 'active', -- 'active', 'suspended', 'expired'
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 许可证验证记录表
CREATE TABLE IF NOT EXISTS license_validations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    machine_id TEXT NOT NULL, -- 机器指纹/硬件ID
    ip_address TEXT,
    validation_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT, -- 'success', 'failed', 'expired', 'invalid'
    error_message TEXT,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

-- 许可证绑定设备表（反盗版）
CREATE TABLE IF NOT EXISTS license_devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    machine_id TEXT NOT NULL,
    device_info TEXT, -- JSON格式的设备信息
    first_bind_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_active_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    bind_count INTEGER DEFAULT 1,
    status TEXT DEFAULT 'active', -- 'active', 'revoked'
    UNIQUE(tenant_id, machine_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

-- 租户功能使用统计表
CREATE TABLE IF NOT EXISTS tenant_usage_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    stat_date DATE NOT NULL,
    accounts_count INTEGER DEFAULT 0,
    tgapi_sessions_count INTEGER DEFAULT 0,
    api_calls_count INTEGER DEFAULT 0,
    conversions_count INTEGER DEFAULT 0,
    autogen_count INTEGER DEFAULT 0,
    UNIQUE(tenant_id, stat_date),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

-- 租户关联的Telegram用户表
CREATE TABLE IF NOT EXISTS tenant_telegram_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    telegram_user_id INTEGER NOT NULL,
    username TEXT,
    role TEXT DEFAULT 'user', -- 'admin', 'user'
    joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, telegram_user_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

-- 更新accounts表添加tenant_id
ALTER TABLE accounts ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE;

-- 更新tgapi_sessions表添加tenant_id
ALTER TABLE tgapi_sessions ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE;

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_tenants_license ON tenants(license_key);
CREATE INDEX IF NOT EXISTS idx_tenants_status ON tenants(status);
CREATE INDEX IF NOT EXISTS idx_license_validations_tenant ON license_validations(tenant_id);
CREATE INDEX IF NOT EXISTS idx_license_devices_tenant ON license_devices(tenant_id);
CREATE INDEX IF NOT EXISTS idx_license_devices_machine ON license_devices(machine_id);
CREATE INDEX IF NOT EXISTS idx_tenant_users_tenant ON tenant_telegram_users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_users_telegram ON tenant_telegram_users(telegram_user_id);
CREATE INDEX IF NOT EXISTS idx_accounts_tenant ON accounts(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tgapi_sessions_tenant ON tgapi_sessions(tenant_id);
