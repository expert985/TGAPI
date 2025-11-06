-- =====================================================
-- MySQL 8.0+ 初始化脚本
-- TG Bot Manager Database Schema
-- =====================================================

-- 设置字符集
SET NAMES utf8mb4;
SET character_set_client = utf8mb4;
SET character_set_connection = utf8mb4;
SET character_set_results = utf8mb4;

-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS `tgbot`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE `tgbot`;

-- =====================================================
-- 租户表（核心表）
-- =====================================================
CREATE TABLE IF NOT EXISTS `tenants` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `tenant_code` VARCHAR(50) NOT NULL COMMENT '租户代码',
  `tenant_name` VARCHAR(100) NOT NULL COMMENT '租户名称',
  `contact_info` VARCHAR(200) DEFAULT NULL COMMENT '联系信息',
  `license_key` VARCHAR(100) NOT NULL COMMENT '许可证密钥',
  `license_type` ENUM('trial', 'monthly', 'yearly', 'lifetime') NOT NULL COMMENT '许可证类型',
  `expire_at` DATETIME DEFAULT NULL COMMENT '过期时间',
  `max_accounts` INT DEFAULT 10 COMMENT '最大账号数',
  `max_tgapi_sessions` INT DEFAULT 5 COMMENT '最大TGAPI会话数',
  `features` JSON COMMENT '功能列表（JSON）',
  `status` ENUM('active', 'suspended', 'expired') DEFAULT 'active' COMMENT '状态',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_tenant_code` (`tenant_code`),
  UNIQUE KEY `uk_license_key` (`license_key`),
  KEY `idx_status` (`status`),
  KEY `idx_expire` (`expire_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='租户表';

-- =====================================================
-- 账号管理表（核心表）
-- =====================================================
CREATE TABLE IF NOT EXISTS `accounts` (
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
  KEY `idx_last_check` (`last_check`),
  CONSTRAINT `fk_accounts_tenant` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='账号管理表';

-- JSON索引（MySQL 8.0特性）
ALTER TABLE `accounts` ADD INDEX `idx_session_api_id` ((CAST(session_data->>'$.api_id' AS CHAR(50))));

-- =====================================================
-- TGAPI会话表
-- =====================================================
CREATE TABLE IF NOT EXISTS `tgapi_sessions` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `tenant_id` BIGINT UNSIGNED DEFAULT NULL,
  `account_id` BIGINT UNSIGNED DEFAULT NULL,
  `session_data` TEXT NOT NULL COMMENT 'Session字符串',
  `api_token` VARCHAR(100) NOT NULL COMMENT 'API Token',
  `api_url` VARCHAR(500) NOT NULL COMMENT 'API URL',
  `expire_at` DATETIME DEFAULT NULL COMMENT '过期时间',
  `max_login` INT DEFAULT -1 COMMENT '最大登录次数（-1无限制）',
  `login_count` INT DEFAULT 0 COMMENT '已登录次数',
  `custom_copyright` VARCHAR(200) DEFAULT NULL COMMENT '自定义版权',
  `show_2fa` TINYINT(1) DEFAULT 1 COMMENT '是否显示2FA',
  `status` ENUM('active', 'expired', 'disabled') DEFAULT 'active' COMMENT '状态',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_api_token` (`api_token`),
  KEY `idx_tenant_status` (`tenant_id`, `status`),
  KEY `idx_status_expire` (`status`, `expire_at`),
  KEY `idx_account` (`account_id`),
  CONSTRAINT `fk_tgapi_tenant` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_tgapi_account` FOREIGN KEY (`account_id`) REFERENCES `accounts` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='TGAPI会话表';

-- =====================================================
-- 验证码推送日志表（分区表）
-- =====================================================
CREATE TABLE IF NOT EXISTS `code_push_logs` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `api_token` VARCHAR(100) NOT NULL COMMENT 'API Token',
  `code` VARCHAR(20) NOT NULL COMMENT '验证码',
  `push_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '推送时间',
  `ip_address` VARCHAR(50) DEFAULT NULL COMMENT 'IP地址',
  `user_agent` VARCHAR(500) DEFAULT NULL COMMENT 'User Agent',
  PRIMARY KEY (`id`, `push_time`),
  KEY `idx_api_token` (`api_token`),
  KEY `idx_push_time` (`push_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='验证码推送日志表（分区表）'
PARTITION BY RANGE (TO_DAYS(`push_time`)) (
  PARTITION p_history VALUES LESS THAN (TO_DAYS('2024-01-01')),
  PARTITION p_2024_q1 VALUES LESS THAN (TO_DAYS('2024-04-01')),
  PARTITION p_2024_q2 VALUES LESS THAN (TO_DAYS('2024-07-01')),
  PARTITION p_2024_q3 VALUES LESS THAN (TO_DAYS('2024-10-01')),
  PARTITION p_2024_q4 VALUES LESS THAN (TO_DAYS('2025-01-01')),
  PARTITION p_2025_q1 VALUES LESS THAN (TO_DAYS('2025-04-01')),
  PARTITION p_future VALUES LESS THAN MAXVALUE
);

-- =====================================================
-- 操作日志表
-- =====================================================
CREATE TABLE IF NOT EXISTS `operation_logs` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `account_id` BIGINT UNSIGNED DEFAULT NULL,
  `tenant_id` BIGINT UNSIGNED DEFAULT NULL,
  `operation` VARCHAR(50) NOT NULL COMMENT '操作类型',
  `details` TEXT COMMENT '详细信息',
  `result` ENUM('success', 'failed', 'partial') DEFAULT 'success' COMMENT '结果',
  `error_message` TEXT COMMENT '错误信息',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_account` (`account_id`),
  KEY `idx_tenant_operation` (`tenant_id`, `operation`),
  KEY `idx_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='操作日志表';

-- =====================================================
-- 格式转换记录表
-- =====================================================
CREATE TABLE IF NOT EXISTS `conversion_logs` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `input_format` VARCHAR(20) NOT NULL,
  `output_format` VARCHAR(20) NOT NULL,
  `input_file` VARCHAR(500) DEFAULT NULL,
  `output_file` VARCHAR(500) DEFAULT NULL,
  `status` ENUM('success', 'failed') DEFAULT 'success',
  `error_message` TEXT,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_formats` (`input_format`, `output_format`),
  KEY `idx_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='格式转换记录表';

-- =====================================================
-- 自动做号记录表
-- =====================================================
CREATE TABLE IF NOT EXISTS `autogen_logs` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `api_id` VARCHAR(50) NOT NULL,
  `api_hash` VARCHAR(100) NOT NULL,
  `output_format` VARCHAR(20) NOT NULL,
  `output_path` VARCHAR(500) DEFAULT NULL,
  `phone` VARCHAR(20) DEFAULT NULL,
  `status` ENUM('pending', 'success', 'failed') DEFAULT 'pending',
  `error_message` TEXT,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_phone` (`phone`),
  KEY `idx_status` (`status`),
  KEY `idx_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='自动做号记录表';

-- =====================================================
-- 账号维护任务表
-- =====================================================
CREATE TABLE IF NOT EXISTS `maintenance_tasks` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `account_id` BIGINT UNSIGNED NOT NULL,
  `task_type` VARCHAR(50) NOT NULL COMMENT '任务类型',
  `interval_hours` INT DEFAULT 24 COMMENT '间隔小时数',
  `last_run` DATETIME DEFAULT NULL COMMENT '最后执行时间',
  `next_run` DATETIME DEFAULT NULL COMMENT '下次执行时间',
  `enabled` TINYINT(1) DEFAULT 1 COMMENT '是否启用',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_account` (`account_id`),
  KEY `idx_next_run` (`next_run`, `enabled`),
  CONSTRAINT `fk_maintenance_account` FOREIGN KEY (`account_id`) REFERENCES `accounts` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='账号维护任务表';

-- =====================================================
-- 许可证验证记录表
-- =====================================================
CREATE TABLE IF NOT EXISTS `license_validations` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `tenant_id` BIGINT UNSIGNED NOT NULL,
  `machine_id` VARCHAR(100) NOT NULL COMMENT '机器ID',
  `ip_address` VARCHAR(50) DEFAULT NULL,
  `validation_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `status` ENUM('success', 'failed', 'expired', 'invalid') NOT NULL,
  `error_message` VARCHAR(500) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_tenant` (`tenant_id`),
  KEY `idx_validation_time` (`validation_time`),
  CONSTRAINT `fk_validation_tenant` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='许可证验证记录';

-- =====================================================
-- 许可证绑定设备表
-- =====================================================
CREATE TABLE IF NOT EXISTS `license_devices` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `tenant_id` BIGINT UNSIGNED NOT NULL,
  `machine_id` VARCHAR(100) NOT NULL,
  `device_info` JSON COMMENT '设备信息（JSON）',
  `first_bind_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `last_active_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `bind_count` INT DEFAULT 1,
  `status` ENUM('active', 'revoked') DEFAULT 'active',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_tenant_machine` (`tenant_id`, `machine_id`),
  KEY `idx_machine` (`machine_id`),
  CONSTRAINT `fk_device_tenant` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='设备绑定表';

-- =====================================================
-- 租户统计视图（MySQL 8.0窗口函数）
-- =====================================================
CREATE OR REPLACE VIEW `v_tenant_stats` AS
SELECT
  t.id AS tenant_id,
  t.tenant_name,
  t.tenant_code,
  t.status AS tenant_status,
  t.license_type,
  t.expire_at,
  t.max_accounts,
  t.max_tgapi_sessions,
  COUNT(DISTINCT a.id) AS accounts_count,
  COUNT(DISTINCT CASE WHEN a.status = 'active' THEN a.id END) AS active_accounts,
  COUNT(DISTINCT ts.id) AS tgapi_sessions_count,
  COUNT(DISTINCT ld.id) AS devices_count,
  ROUND(COUNT(DISTINCT a.id) * 100.0 / NULLIF(t.max_accounts, 0), 2) AS accounts_usage_percent,
  ROUND(COUNT(DISTINCT ts.id) * 100.0 / NULLIF(t.max_tgapi_sessions, 0), 2) AS sessions_usage_percent
FROM tenants t
LEFT JOIN accounts a ON t.id = a.tenant_id
LEFT JOIN tgapi_sessions ts ON t.id = ts.tenant_id AND ts.status = 'active'
LEFT JOIN license_devices ld ON t.id = ld.tenant_id AND ld.status = 'active'
GROUP BY t.id;

-- =====================================================
-- 创建初始管理员租户
-- =====================================================
INSERT INTO `tenants` (
  `tenant_code`,
  `tenant_name`,
  `license_key`,
  `license_type`,
  `max_accounts`,
  `max_tgapi_sessions`,
  `features`,
  `status`
) VALUES (
  'ADMIN',
  'System Administrator',
  'ADMIN-0000-0000-0000',
  'lifetime',
  999999,
  999999,
  '["tgapi", "account_manager", "converter", "autogen", "admin"]',
  'active'
) ON DUPLICATE KEY UPDATE tenant_name = tenant_name;

-- =====================================================
-- 完成提示
-- =====================================================
SELECT '✅ MySQL 8.0 数据库初始化完成！' AS Status;
SELECT CONCAT('数据库: ', DATABASE()) AS Current_Database;
SELECT COUNT(*) AS Total_Tables FROM information_schema.tables WHERE table_schema = DATABASE();
