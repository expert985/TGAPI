"""
日志管理模块 - 支持日志切割和自动清理
"""
import logging
import sys
import os
import glob
from pathlib import Path
from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler


def cleanup_old_logs(log_dir: str, days: int = 30):
    """
    清理过期日志文件

    Args:
        log_dir: 日志目录
        days: 保留天数
    """
    try:
        log_path = Path(log_dir)
        if not log_path.exists():
            return

        cutoff_time = datetime.now() - timedelta(days=days)

        # 查找所有日志文件（包括切割后的）
        for log_file in log_path.glob("*.log*"):
            if log_file.is_file():
                file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if file_mtime < cutoff_time:
                    log_file.unlink()
                    print(f"🗑️  已删除过期日志: {log_file.name}")
    except Exception as e:
        print(f"⚠️  清理日志失败: {str(e)}")


def setup_logger(
    name: str = "tg_bot",
    log_file: str = None,
    level=logging.INFO,
    when: str = 'midnight',
    interval: int = 1,
    backup_count: int = 30,
    auto_cleanup: bool = True
):
    """
    设置日志记录器（支持自动日切和清理）

    Args:
        name: 日志记录器名称
        log_file: 日志文件路径
        level: 日志级别
        when: 切割时间单位 ('midnight', 'H', 'D')
        interval: 切割间隔
        backup_count: 保留备份数量（天数）
        auto_cleanup: 是否自动清理过期日志

    Returns:
        Logger对象
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加处理器
    if logger.handlers:
        return logger

    # 日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 控制台处理器（带颜色）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # 彩色日志格式（仅控制台）
    class ColoredFormatter(logging.Formatter):
        """彩色日志格式化器"""

        COLORS = {
            'DEBUG': '\033[0;36m',    # 青色
            'INFO': '\033[0;32m',     # 绿色
            'WARNING': '\033[0;33m',  # 黄色
            'ERROR': '\033[0;31m',    # 红色
            'CRITICAL': '\033[0;35m', # 紫色
        }
        RESET = '\033[0m'

        def format(self, record):
            log_color = self.COLORS.get(record.levelname, self.RESET)
            record.levelname = f"{log_color}{record.levelname}{self.RESET}"
            return super().format(record)

    console_formatter = ColoredFormatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 文件处理器（支持日切）
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # 使用TimedRotatingFileHandler实现日切
        file_handler = TimedRotatingFileHandler(
            filename=log_file,
            when=when,           # 'midnight' = 每天午夜切割
            interval=interval,   # 间隔1天
            backupCount=backup_count,  # 保留30天
            encoding='utf-8',
            delay=False,
            utc=False
        )

        # 设置日志文件命名格式（添加日期后缀）
        file_handler.suffix = "%Y-%m-%d.log"
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # 首次启动时清理过期日志
        if auto_cleanup:
            cleanup_old_logs(str(log_path.parent), days=backup_count)

    return logger


# 创建默认日志记录器（每天午夜切割，保留30天）
logger = setup_logger(
    name="tg_bot",
    log_file="logs/bot.log",
    level=logging.INFO,
    when='midnight',      # 每天午夜切割
    interval=1,           # 间隔1天
    backup_count=30,      # 保留30天
    auto_cleanup=True     # 自动清理过期日志
)


# API服务器日志（单独的日志文件）
api_logger = setup_logger(
    name="tg_api",
    log_file="logs/api.log",
    level=logging.INFO,
    when='midnight',
    interval=1,
    backup_count=30,
    auto_cleanup=True
)


# Bot Pool日志
pool_logger = setup_logger(
    name="bot_pool",
    log_file="logs/bot_pool.log",
    level=logging.INFO,
    when='midnight',
    interval=1,
    backup_count=30,
    auto_cleanup=True
)
