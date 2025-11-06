"""
Bot Instance - 单个机器人实例封装
支持负载追踪、健康监控、自动故障恢复
"""
import asyncio
import time
import psutil
from typing import Optional, Dict
from datetime import datetime
from telegram import Update, Bot
from telegram.ext import Application, ContextTypes
from shared.utils.logger import logger
from shared.database.init import db


class BotInstance:
    """
    单个Telegram Bot实例封装

    负责:
    - Bot生命周期管理
    - 负载追踪
    - 健康监控
    - 性能统计
    """

    def __init__(
        self,
        bot_id: int,
        bot_token: str,
        bot_username: str,
        bot_name: str,
        max_load: int = 100,
        priority: int = 1
    ):
        """
        初始化Bot实例

        Args:
            bot_id: 数据库中的bot配置ID
            bot_token: Telegram Bot Token
            bot_username: Bot用户名
            bot_name: Bot显示名称
            max_load: 最大负载（同时活跃用户数）
            priority: 优先级（1-10）
        """
        self.bot_id = bot_id
        self.bot_token = bot_token
        self.bot_username = bot_username
        self.bot_name = bot_name
        self.max_load = max_load
        self.priority = priority

        # 运行状态
        self.is_running = False
        self.start_time: Optional[float] = None
        self.application: Optional[Application] = None

        # 负载追踪
        self.active_users: set = set()  # 当前活跃用户telegram_id集合
        self.total_messages = 0  # 总消息数
        self.messages_this_minute = 0  # 当前分钟消息数
        self.last_minute_reset = time.time()

        # 错误追踪
        self.error_count = 0
        self.last_error: Optional[str] = None
        self.last_error_time: Optional[datetime] = None

        logger.info(f"📦 BotInstance初始化: {self.bot_username} (ID: {self.bot_id})")

    def get_load_percentage(self) -> float:
        """
        获取负载百分比

        Returns:
            0-100的浮点数
        """
        if self.max_load <= 0:
            return 0.0
        return (len(self.active_users) / self.max_load) * 100

    def can_accept_new_user(self) -> bool:
        """
        检查是否可以接受新用户

        Returns:
            True表示可以接受新用户
        """
        return len(self.active_users) < self.max_load

    def add_user(self, telegram_id: int) -> bool:
        """
        添加活跃用户

        Args:
            telegram_id: Telegram用户ID

        Returns:
            True表示成功添加
        """
        if not self.can_accept_new_user():
            logger.warning(
                f"⚠️ Bot {self.bot_username} 负载已满 "
                f"({len(self.active_users)}/{self.max_load})"
            )
            return False

        self.active_users.add(telegram_id)
        logger.debug(
            f"➕ 用户 {telegram_id} 添加到Bot {self.bot_username}, "
            f"当前负载: {len(self.active_users)}/{self.max_load}"
        )
        return True

    def remove_user(self, telegram_id: int):
        """移除活跃用户"""
        self.active_users.discard(telegram_id)
        logger.debug(
            f"➖ 用户 {telegram_id} 从Bot {self.bot_username}移除, "
            f"当前负载: {len(self.active_users)}/{self.max_load}"
        )

    def track_message(self):
        """追踪消息（用于统计messages_per_min）"""
        self.total_messages += 1

        # 检查是否需要重置分钟计数
        now = time.time()
        if now - self.last_minute_reset >= 60:
            self.messages_this_minute = 0
            self.last_minute_reset = now

        self.messages_this_minute += 1

    def get_messages_per_minute(self) -> int:
        """获取每分钟消息数"""
        # 如果超过1分钟没有消息，返回0
        if time.time() - self.last_minute_reset > 60:
            return 0
        return self.messages_this_minute

    def record_error(self, error: str):
        """
        记录错误

        Args:
            error: 错误信息
        """
        self.error_count += 1
        self.last_error = error
        self.last_error_time = datetime.now()
        logger.error(f"❌ Bot {self.bot_username} 错误 #{self.error_count}: {error}")

    def get_uptime_seconds(self) -> int:
        """
        获取运行时长（秒）

        Returns:
            运行时长，如果未运行则返回0
        """
        if not self.start_time:
            return 0
        return int(time.time() - self.start_time)

    def get_system_stats(self) -> Dict[str, float]:
        """
        获取系统资源使用情况

        Returns:
            {'cpu_usage': float, 'memory_mb': float}
        """
        try:
            process = psutil.Process()
            cpu_usage = process.cpu_percent(interval=0.1)
            memory_mb = process.memory_info().rss / 1024 / 1024
            return {
                'cpu_usage': round(cpu_usage, 2),
                'memory_mb': round(memory_mb, 2)
            }
        except Exception as e:
            logger.error(f"获取系统统计失败: {e}")
            return {'cpu_usage': 0.0, 'memory_mb': 0.0}

    def get_stats(self) -> Dict:
        """
        获取完整统计数据

        Returns:
            统计数据字典
        """
        sys_stats = self.get_system_stats()

        return {
            'bot_id': self.bot_id,
            'bot_username': self.bot_username,
            'active_users': len(self.active_users),
            'total_messages': self.total_messages,
            'messages_per_min': self.get_messages_per_minute(),
            'error_count': self.error_count,
            'uptime_seconds': self.get_uptime_seconds(),
            'cpu_usage': sys_stats['cpu_usage'],
            'memory_mb': sys_stats['memory_mb'],
            'load_percentage': round(self.get_load_percentage(), 2),
            'is_running': self.is_running,
            'last_error': self.last_error,
            'last_error_time': self.last_error_time.isoformat() if self.last_error_time else None
        }

    async def create_application(self, handlers_setup_func) -> Application:
        """
        创建Telegram Application实例

        Args:
            handlers_setup_func: 设置handlers的函数

        Returns:
            Application实例
        """
        try:
            # 创建Application
            application = Application.builder().token(self.bot_token).build()

            # 设置handlers
            await handlers_setup_func(application)

            self.application = application
            logger.info(f"✅ Application创建成功: {self.bot_username}")
            return application

        except Exception as e:
            error_msg = f"创建Application失败: {e}"
            self.record_error(error_msg)
            raise

    async def start(self):
        """启动Bot实例"""
        try:
            if self.is_running:
                logger.warning(f"⚠️ Bot {self.bot_username} 已经在运行")
                return

            if not self.application:
                raise RuntimeError("Application未创建，请先调用create_application")

            logger.info(f"🚀 启动Bot: {self.bot_username}")

            # 初始化并启动
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()

            self.is_running = True
            self.start_time = time.time()

            logger.info(f"✅ Bot启动成功: {self.bot_username}")

            # 记录启动事件到数据库
            db.execute(
                """INSERT INTO bot_events
                   (bot_id, event_type, event_level, message)
                   VALUES (?, ?, ?, ?)""",
                (self.bot_id, 'started', 'info', f'Bot {self.bot_username} 启动成功')
            )

        except Exception as e:
            error_msg = f"启动失败: {e}"
            self.record_error(error_msg)
            self.is_running = False
            raise

    async def stop(self):
        """停止Bot实例"""
        try:
            if not self.is_running:
                logger.warning(f"⚠️ Bot {self.bot_username} 未运行")
                return

            logger.info(f"🛑 停止Bot: {self.bot_username}")

            if self.application:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()

            self.is_running = False

            logger.info(f"✅ Bot停止成功: {self.bot_username}")

            # 记录停止事件到数据库
            db.execute(
                """INSERT INTO bot_events
                   (bot_id, event_type, event_level, message)
                   VALUES (?, ?, ?, ?)""",
                (self.bot_id, 'stopped', 'info', f'Bot {self.bot_username} 已停止')
            )

        except Exception as e:
            error_msg = f"停止失败: {e}"
            self.record_error(error_msg)
            raise

    async def restart(self):
        """重启Bot实例"""
        logger.info(f"🔄 重启Bot: {self.bot_username}")
        await self.stop()
        await asyncio.sleep(2)  # 等待2秒
        await self.start()

    def __repr__(self) -> str:
        return (
            f"BotInstance(id={self.bot_id}, username={self.bot_username}, "
            f"load={len(self.active_users)}/{self.max_load}, "
            f"running={self.is_running})"
        )
