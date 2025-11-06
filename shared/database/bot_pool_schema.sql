-- ==========================================
-- Bot Pool 数据库架构 (MySQL 8.0+)
-- 用于支持多机器人负载均衡系统
-- ==========================================

-- Bot配置表（存储所有可用的机器人）
CREATE TABLE IF NOT EXISTS `bot_configs` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `bot_token` VARCHAR(200) NOT NULL UNIQUE,
  `bot_username` VARCHAR(100),
  `bot_name` VARCHAR(200),
  `bot_id` BIGINT,  -- Telegram bot ID
  `status` VARCHAR(20) DEFAULT 'active',  -- active/inactive/error/maintenance
  `max_load` INT DEFAULT 100,  -- 最大同时活跃用户数
  `priority` INT DEFAULT 1,  -- 优先级（1-10，数字越大优先级越高）
  `description` TEXT,  -- 备注说明
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX `idx_status` (`status`),
  INDEX `idx_priority` (`priority`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Bot实时统计表
CREATE TABLE IF NOT EXISTS `bot_stats` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `bot_id` INT NOT NULL,
  `active_users` INT DEFAULT 0,  -- 当前活跃用户数
  `total_messages` BIGINT DEFAULT 0,  -- 总处理消息数
  `messages_per_min` INT DEFAULT 0,  -- 每分钟消息处理数
  `last_heartbeat` DATETIME,  -- 最后心跳时间
  `error_count` INT DEFAULT 0,  -- 错误计数
  `uptime_seconds` BIGINT DEFAULT 0,  -- 运行时长（秒）
  `cpu_usage` FLOAT DEFAULT 0.0,  -- CPU使用率
  `memory_mb` INT DEFAULT 0,  -- 内存使用（MB）
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (`bot_id`) REFERENCES `bot_configs`(`id`) ON DELETE CASCADE,
  UNIQUE KEY `unique_bot_stats` (`bot_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 用户-Bot会话映射表（会话保持）
CREATE TABLE IF NOT EXISTS `user_bot_sessions` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `telegram_id` BIGINT NOT NULL UNIQUE,
  `assigned_bot_id` INT NOT NULL,
  `session_started` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `last_interaction` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `message_count` INT DEFAULT 0,  -- 该用户在此bot的消息数
  FOREIGN KEY (`assigned_bot_id`) REFERENCES `bot_configs`(`id`) ON DELETE CASCADE,
  INDEX `idx_telegram_id` (`telegram_id`),
  INDEX `idx_bot_id` (`assigned_bot_id`),
  INDEX `idx_last_interaction` (`last_interaction`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Bot事件日志表（用于监控和审计）
CREATE TABLE IF NOT EXISTS `bot_events` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `bot_id` INT,
  `event_type` VARCHAR(50) NOT NULL,  -- started/stopped/error/health_check/user_assigned
  `event_level` VARCHAR(20) DEFAULT 'info',  -- info/warning/error/critical
  `message` TEXT,
  `details` JSON,  -- MySQL 8.0+ 原生JSON支持
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (`bot_id`) REFERENCES `bot_configs`(`id`) ON DELETE SET NULL,
  INDEX `idx_bot_event` (`bot_id`, `event_type`),
  INDEX `idx_created_at` (`created_at`),
  INDEX `idx_event_level` (`event_level`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Bot负载历史记录表（用于统计分析和趋势图）
CREATE TABLE IF NOT EXISTS `bot_load_history` (
  `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
  `bot_id` INT NOT NULL,
  `active_users` INT,
  `messages_per_min` INT,
  `cpu_usage` FLOAT,
  `memory_mb` INT,
  `timestamp` DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (`bot_id`) REFERENCES `bot_configs`(`id`) ON DELETE CASCADE,
  INDEX `idx_bot_timestamp` (`bot_id`, `timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 初始化示例数据（首次部署时取消注释并填入真实token）
-- INSERT INTO bot_configs (bot_token, bot_username, bot_name, priority, description) VALUES
-- ('YOUR_PRIMARY_BOT_TOKEN', 'primary_bot', 'Primary Bot', 10, '主要机器人 - 高优先级'),
-- ('YOUR_BACKUP_BOT_TOKEN_1', 'backup_bot_1', 'Backup Bot 1', 5, '备用机器人1 - 中优先级'),
-- ('YOUR_BACKUP_BOT_TOKEN_2', 'backup_bot_2', 'Backup Bot 2', 5, '备用机器人2 - 中优先级');

-- 创建定期清理会话的存储过程（清理30天未活动的会话）
DELIMITER //
CREATE PROCEDURE IF NOT EXISTS cleanup_old_sessions()
BEGIN
  DELETE FROM user_bot_sessions
  WHERE last_interaction < DATE_SUB(NOW(), INTERVAL 30 DAY);

  -- 记录清理事件
  INSERT INTO bot_events (bot_id, event_type, event_level, message)
  VALUES (NULL, 'cleanup', 'info', CONCAT('清理了过期会话，清理时间: ', NOW()));
END //
DELIMITER ;

-- 创建定期记录负载历史的存储过程
DELIMITER //
CREATE PROCEDURE IF NOT EXISTS record_load_history()
BEGIN
  INSERT INTO bot_load_history (bot_id, active_users, messages_per_min, cpu_usage, memory_mb)
  SELECT
    bot_id,
    active_users,
    messages_per_min,
    cpu_usage,
    memory_mb
  FROM bot_stats;
END //
DELIMITER ;

-- 可选：创建定时任务（需要EVENT scheduler开启）
-- SET GLOBAL event_scheduler = ON;
--
-- -- 每小时清理一次过期会话
-- CREATE EVENT IF NOT EXISTS cleanup_sessions_hourly
-- ON SCHEDULE EVERY 1 HOUR
-- DO CALL cleanup_old_sessions();
--
-- -- 每5分钟记录一次负载历史
-- CREATE EVENT IF NOT EXISTS record_load_every_5min
-- ON SCHEDULE EVERY 5 MINUTE
-- DO CALL record_load_history();
