-- =====================================================
-- 授权用户表（MySQL 8.0+）- 管理有权使用机器人的TG用户
-- =====================================================

CREATE TABLE IF NOT EXISTS `authorized_users` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `telegram_id` BIGINT NOT NULL UNIQUE COMMENT 'TG用户ID',
  `username` VARCHAR(100) DEFAULT NULL COMMENT 'TG用户名',
  `full_name` VARCHAR(200) DEFAULT NULL COMMENT '用户全名',
  `authorization_level` VARCHAR(20) NOT NULL DEFAULT 'basic' COMMENT '授权等级: basic, premium, vip',
  `authorized_by` VARCHAR(100) DEFAULT NULL COMMENT '授权管理员',
  `authorization_date` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '授权时间',
  `expire_date` DATETIME DEFAULT NULL COMMENT '过期时间（NULL为永久）',
  `duration_type` VARCHAR(20) DEFAULT NULL COMMENT '时长类型: 1month, 3months, 6months, 1year, permanent',
  `max_accounts` INT DEFAULT 10 COMMENT '最大账号数',
  `max_tgapi_sessions` INT DEFAULT 5 COMMENT '最大TGAPI会话数',
  `status` VARCHAR(20) DEFAULT 'active' COMMENT '状态: active, expired, suspended',
  `payment_info` TEXT COMMENT '付款信息',
  `notes` TEXT COMMENT '备注',
  `last_active` DATETIME DEFAULT NULL COMMENT '最后活跃时间',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_telegram_id` (`telegram_id`),
  KEY `idx_status` (`status`),
  KEY `idx_expire_date` (`expire_date`),
  KEY `idx_authorization_level` (`authorization_level`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='授权用户表';

-- =====================================================
-- 授权日志表 - 记录所有授权操作
-- =====================================================

CREATE TABLE IF NOT EXISTS `authorization_logs` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `telegram_id` BIGINT NOT NULL COMMENT 'TG用户ID',
  `action` VARCHAR(50) NOT NULL COMMENT '操作: authorize, renew, suspend, expire',
  `duration_type` VARCHAR(20) DEFAULT NULL COMMENT '时长类型',
  `expire_date` DATETIME DEFAULT NULL COMMENT '过期时间',
  `operated_by` VARCHAR(100) DEFAULT NULL COMMENT '操作管理员',
  `payment_amount` DECIMAL(10,2) DEFAULT NULL COMMENT '付款金额',
  `notes` TEXT COMMENT '备注',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_telegram_id` (`telegram_id`),
  KEY `idx_action` (`action`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='授权日志表';

-- =====================================================
-- 未授权访问日志表 - 记录未授权用户的访问尝试
-- =====================================================

CREATE TABLE IF NOT EXISTS `unauthorized_access_logs` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `telegram_id` BIGINT NOT NULL COMMENT 'TG用户ID',
  `username` VARCHAR(100) DEFAULT NULL COMMENT 'TG用户名',
  `full_name` VARCHAR(200) DEFAULT NULL COMMENT '用户全名',
  `command` VARCHAR(100) DEFAULT NULL COMMENT '尝试的命令',
  `message` TEXT COMMENT '消息内容',
  `access_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '访问时间',
  PRIMARY KEY (`id`),
  KEY `idx_telegram_id` (`telegram_id`),
  KEY `idx_access_time` (`access_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='未授权访问日志表';
