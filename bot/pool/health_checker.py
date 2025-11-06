"""
Health Checker - Bot健康检查器
定期检查Bot健康状态，自动隔离故障Bot
"""
import asyncio
from typing import List, Dict
from datetime import datetime, timedelta
from shared.utils.logger import logger
from shared.database.init import db
from .bot_instance import BotInstance
from .redis_cache import BotPoolRedisCache


class HealthChecker:
    """
    Bot健康检查器

    功能:
    - 定期心跳检查
    - 自动检测故障Bot
    - 自动隔离和恢复
    - 健康状态报告
    """

    def __init__(
        self,
        redis_cache: BotPoolRedisCache,
        check_interval: int = 30,  # 检查间隔（秒）
        heartbeat_timeout: int = 60  # 心跳超时（秒）
    ):
        """
        初始化健康检查器

        Args:
            redis_cache: Redis缓存管理器
            check_interval: 健康检查间隔（秒）
            heartbeat_timeout: 心跳超时时间（秒）
        """
        self.redis_cache = redis_cache
        self.check_interval = check_interval
        self.heartbeat_timeout = heartbeat_timeout
        self.is_running = False
        self.task: asyncio.Task = None

        logger.info(
            f"🏥 HealthChecker初始化: "
            f"interval={check_interval}s, timeout={heartbeat_timeout}s"
        )

    async def start(self, bot_instances: List[BotInstance]):
        """
        启动健康检查任务

        Args:
            bot_instances: Bot实例列表
        """
        if self.is_running:
            logger.warning("⚠️ HealthChecker已经在运行")
            return

        self.is_running = True
        self.task = asyncio.create_task(self._check_loop(bot_instances))
        logger.info("✅ HealthChecker启动成功")

    async def stop(self):
        """停止健康检查任务"""
        if not self.is_running:
            return

        self.is_running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        logger.info("✅ HealthChecker已停止")

    async def _check_loop(self, bot_instances: List[BotInstance]):
        """健康检查主循环"""
        while self.is_running:
            try:
                await self._perform_health_check(bot_instances)
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"健康检查失败: {e}")
                await asyncio.sleep(self.check_interval)

    async def _perform_health_check(self, bot_instances: List[BotInstance]):
        """
        执行健康检查

        Args:
            bot_instances: Bot实例列表
        """
        logger.debug(f"🔍 执行健康检查: {len(bot_instances)}个Bot")

        for bot in bot_instances:
            await self._check_bot_health(bot)

    async def _check_bot_health(self, bot: BotInstance) -> bool:
        """
        检查单个Bot的健康状态

        Args:
            bot: BotInstance实例

        Returns:
            True表示健康，False表示不健康
        """
        bot_id = bot.bot_id
        is_healthy = True
        health_issues = []

        try:
            # 1. 检查运行状态
            if not bot.is_running:
                is_healthy = False
                health_issues.append("未运行")

            # 2. 检查心跳超时
            if not self.redis_cache.check_heartbeat(bot_id):
                is_healthy = False
                health_issues.append("心跳超时")

            # 3. 检查错误率
            if bot.error_count > 100:  # 错误数超过100
                is_healthy = False
                health_issues.append(f"错误过多({bot.error_count})")

            # 4. 检查负载异常
            if len(bot.active_users) > bot.max_load:
                is_healthy = False
                health_issues.append(f"超载({len(bot.active_users)}/{bot.max_load})")

            # 5. 更新健康状态
            if is_healthy:
                await self._mark_healthy(bot)
            else:
                await self._mark_unhealthy(bot, health_issues)

            # 6. 更新统计信息
            await self._update_bot_stats(bot)

            return is_healthy

        except Exception as e:
            logger.error(f"检查Bot健康失败 bot_id={bot_id}: {e}")
            await self._mark_unhealthy(bot, [f"检查异常: {e}"])
            return False

    async def _mark_healthy(self, bot: BotInstance):
        """
        标记Bot为健康状态

        Args:
            bot: BotInstance实例
        """
        bot_id = bot.bot_id

        # 更新Redis缓存
        self.redis_cache.set_bot_status(bot_id, 'active')

        # 更新数据库
        try:
            db.execute(
                """UPDATE bot_configs
                   SET status = 'active', updated_at = ?
                   WHERE id = ?""",
                (datetime.now(), bot_id)
            )

            logger.debug(f"✅ Bot健康: {bot.bot_username}")

        except Exception as e:
            logger.error(f"更新Bot健康状态失败: {e}")

    async def _mark_unhealthy(self, bot: BotInstance, issues: List[str]):
        """
        标记Bot为不健康状态

        Args:
            bot: BotInstance实例
            issues: 健康问题列表
        """
        bot_id = bot.bot_id
        issue_text = ", ".join(issues)

        # 更新Redis缓存
        self.redis_cache.set_bot_status(bot_id, 'error')

        # 从可用池中移除
        self.redis_cache.remove_bot_from_pool(bot_id)

        # 更新数据库
        try:
            db.execute(
                """UPDATE bot_configs
                   SET status = 'error', updated_at = ?
                   WHERE id = ?""",
                (datetime.now(), bot_id)
            )

            # 记录健康检查事件
            db.execute(
                """INSERT INTO bot_events
                   (bot_id, event_type, event_level, message, details)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    bot_id,
                    'health_check',
                    'warning',
                    f'Bot不健康: {issue_text}',
                    f'{{"issues": {issues}}}'
                )
            )

            logger.warning(f"⚠️ Bot不健康: {bot.bot_username} - {issue_text}")

        except Exception as e:
            logger.error(f"更新Bot不健康状态失败: {e}")

    async def _update_bot_stats(self, bot: BotInstance):
        """
        更新Bot统计信息到数据库和Redis

        Args:
            bot: BotInstance实例
        """
        try:
            stats = bot.get_stats()

            # 更新数据库
            db.execute(
                """INSERT INTO bot_stats
                   (bot_id, active_users, total_messages, messages_per_min,
                    last_heartbeat, error_count, uptime_seconds, cpu_usage, memory_mb)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON DUPLICATE KEY UPDATE
                   active_users = VALUES(active_users),
                   total_messages = VALUES(total_messages),
                   messages_per_min = VALUES(messages_per_min),
                   last_heartbeat = VALUES(last_heartbeat),
                   error_count = VALUES(error_count),
                   uptime_seconds = VALUES(uptime_seconds),
                   cpu_usage = VALUES(cpu_usage),
                   memory_mb = VALUES(memory_mb),
                   updated_at = ?""",
                (
                    bot.bot_id,
                    stats['active_users'],
                    stats['total_messages'],
                    stats['messages_per_min'],
                    datetime.now(),
                    stats['error_count'],
                    stats['uptime_seconds'],
                    stats['cpu_usage'],
                    stats['memory_mb'],
                    datetime.now()
                )
            )

            # 更新Redis缓存
            self.redis_cache.set_bot_load(
                bot.bot_id,
                stats['active_users']
            )

            # 更新心跳
            self.redis_cache.update_heartbeat(bot.bot_id)

        except Exception as e:
            logger.error(f"更新Bot统计失败: {e}")

    def get_health_report(self, bot_instances: List[BotInstance]) -> Dict:
        """
        获取健康报告

        Args:
            bot_instances: Bot实例列表

        Returns:
            健康报告字典
        """
        total = len(bot_instances)
        healthy = sum(1 for bot in bot_instances if bot.is_running)
        unhealthy = total - healthy

        total_load = sum(len(bot.active_users) for bot in bot_instances)
        total_capacity = sum(bot.max_load for bot in bot_instances)
        avg_load_percentage = (total_load / total_capacity * 100) if total_capacity > 0 else 0

        return {
            'total_bots': total,
            'healthy_bots': healthy,
            'unhealthy_bots': unhealthy,
            'total_active_users': total_load,
            'total_capacity': total_capacity,
            'avg_load_percentage': round(avg_load_percentage, 2),
            'check_interval': self.check_interval,
            'heartbeat_timeout': self.heartbeat_timeout,
            'last_check': datetime.now().isoformat()
        }

    async def force_check(self, bot_instances: List[BotInstance]):
        """
        强制执行一次健康检查

        Args:
            bot_instances: Bot实例列表
        """
        logger.info("🔍 执行强制健康检查")
        await self._perform_health_check(bot_instances)
