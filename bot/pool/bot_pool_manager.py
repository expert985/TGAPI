"""
Bot Pool Manager - Bot池管理器
统筹管理所有Bot实例，提供负载均衡和高可用能力
"""
import asyncio
import redis
from typing import List, Optional, Dict, Callable
from shared.utils.logger import logger
from shared.database.init import db
from .bot_instance import BotInstance
from .load_balancer import LoadBalancer, LoadBalanceStrategy
from .health_checker import HealthChecker
from .redis_cache import BotPoolRedisCache


class BotPoolManager:
    """
    Bot池管理器

    核心功能:
    - 管理多个Bot实例
    - 智能负载均衡
    - 自动健康检查
    - 动态添加/删除Bot
    - 故障自动恢复
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        handlers_setup_func: Callable,
        lb_strategy: LoadBalanceStrategy = LoadBalanceStrategy.LEAST_CONNECTIONS
    ):
        """
        初始化Bot池管理器

        Args:
            redis_client: Redis客户端
            handlers_setup_func: Bot handlers设置函数
            lb_strategy: 负载均衡策略
        """
        self.redis_cache = BotPoolRedisCache(redis_client)
        self.load_balancer = LoadBalancer(self.redis_cache, lb_strategy)
        self.health_checker = HealthChecker(self.redis_cache)
        self.handlers_setup_func = handlers_setup_func

        self.bot_instances: List[BotInstance] = []
        self.is_running = False

        logger.info("🚀 BotPoolManager初始化完成")

    async def initialize(self):
        """
        初始化Bot池

        从数据库加载所有激活的Bot配置并启动
        """
        logger.info("🔧 开始初始化Bot池...")

        try:
            # 从数据库加载Bot配置
            bot_configs = db.fetchall(
                """SELECT * FROM bot_configs
                   WHERE status IN ('active', 'inactive')
                   ORDER BY priority DESC"""
            )

            if not bot_configs:
                logger.warning("⚠️ 数据库中没有Bot配置，Bot池为空")
                return

            logger.info(f"📦 从数据库加载了 {len(bot_configs)} 个Bot配置")

            # 创建BotInstance
            for config in bot_configs:
                try:
                    bot_instance = BotInstance(
                        bot_id=config['id'],
                        bot_token=config['bot_token'],
                        bot_username=config['bot_username'] or f"bot_{config['id']}",
                        bot_name=config['bot_name'] or f"Bot {config['id']}",
                        max_load=config['max_load'],
                        priority=config['priority']
                    )

                    # 创建Application
                    await bot_instance.create_application(self.handlers_setup_func)

                    # 只启动status为active的bot
                    if config['status'] == 'active':
                        await bot_instance.start()

                    self.bot_instances.append(bot_instance)

                    logger.info(
                        f"✅ Bot实例创建成功: {bot_instance.bot_username} "
                        f"(优先级: {bot_instance.priority})"
                    )

                except Exception as e:
                    logger.error(
                        f"❌ 创建Bot实例失败 (ID: {config['id']}): {e}"
                    )
                    continue

            logger.info(f"✅ Bot池初始化完成，共 {len(self.bot_instances)} 个实例")

        except Exception as e:
            logger.error(f"❌ 初始化Bot池失败: {e}")
            raise

    async def start(self):
        """
        启动Bot池

        启动所有Bot实例和健康检查器
        """
        if self.is_running:
            logger.warning("⚠️ Bot池已经在运行")
            return

        logger.info("🚀 启动Bot池...")

        # 启动健康检查器
        await self.health_checker.start(self.bot_instances)

        self.is_running = True
        logger.info("✅ Bot池启动成功！")

        # 打印状态
        self._print_pool_status()

    async def stop(self):
        """停止Bot池"""
        if not self.is_running:
            return

        logger.info("🛑 停止Bot池...")

        # 停止健康检查器
        await self.health_checker.stop()

        # 停止所有Bot实例
        for bot in self.bot_instances:
            try:
                await bot.stop()
            except Exception as e:
                logger.error(f"停止Bot失败 {bot.bot_username}: {e}")

        self.is_running = False
        logger.info("✅ Bot池已停止")

    async def add_bot(
        self,
        bot_token: str,
        bot_username: str,
        bot_name: str,
        max_load: int = 100,
        priority: int = 1,
        description: str = None
    ) -> Optional[int]:
        """
        动态添加新Bot到池中

        Args:
            bot_token: Bot Token
            bot_username: Bot用户名
            bot_name: Bot显示名称
            max_load: 最大负载
            priority: 优先级
            description: 描述

        Returns:
            新Bot的ID，失败返回None
        """
        try:
            logger.info(f"➕ 添加新Bot: {bot_username}")

            # 1. 插入数据库
            db.execute(
                """INSERT INTO bot_configs
                   (bot_token, bot_username, bot_name, max_load, priority, description, status)
                   VALUES (?, ?, ?, ?, ?, ?, 'active')""",
                (bot_token, bot_username, bot_name, max_load, priority, description)
            )

            # 获取新插入的ID
            bot_id = db.fetchone("SELECT LAST_INSERT_ID() as id")['id']

            # 2. 创建BotInstance
            bot_instance = BotInstance(
                bot_id=bot_id,
                bot_token=bot_token,
                bot_username=bot_username,
                bot_name=bot_name,
                max_load=max_load,
                priority=priority
            )

            # 3. 创建Application
            await bot_instance.create_application(self.handlers_setup_func)

            # 4. 启动Bot
            await bot_instance.start()

            # 5. 添加到池中
            self.bot_instances.append(bot_instance)

            logger.info(f"✅ 新Bot添加成功: {bot_username} (ID: {bot_id})")
            return bot_id

        except Exception as e:
            logger.error(f"❌ 添加Bot失败: {e}")
            return None

    async def remove_bot(self, bot_id: int) -> bool:
        """
        从池中移除Bot

        Args:
            bot_id: Bot ID

        Returns:
            True表示成功
        """
        try:
            logger.info(f"➖ 移除Bot: bot_id={bot_id}")

            # 1. 找到Bot实例
            bot = self.get_bot_by_id(bot_id)
            if not bot:
                logger.warning(f"⚠️ Bot不存在: bot_id={bot_id}")
                return False

            # 2. 停止Bot
            await bot.stop()

            # 3. 从列表中移除
            self.bot_instances.remove(bot)

            # 4. 更新数据库状态
            db.execute(
                """UPDATE bot_configs
                   SET status = 'inactive', updated_at = ?
                   WHERE id = ?""",
                (datetime.now(), bot_id)
            )

            # 5. 清除缓存
            self.redis_cache.clear_bot_cache(bot_id)

            logger.info(f"✅ Bot移除成功: {bot.bot_username}")
            return True

        except Exception as e:
            logger.error(f"❌ 移除Bot失败: {e}")
            return False

    def get_bot_for_user(self, telegram_id: int) -> Optional[BotInstance]:
        """
        为用户获取Bot实例

        Args:
            telegram_id: Telegram用户ID

        Returns:
            分配的BotInstance，如果失败返回None
        """
        # 获取可用的bot实例
        available_bots = [
            bot for bot in self.bot_instances
            if bot.is_running
        ]

        if not available_bots:
            logger.error("❌ 没有可用的Bot实例")
            return None

        # 通过负载均衡器分配bot
        bot_id = self.load_balancer.assign_bot(telegram_id, available_bots)

        if not bot_id:
            logger.error(f"❌ 负载均衡器未能为用户 {telegram_id} 分配Bot")
            return None

        # 返回bot实例
        bot = self.get_bot_by_id(bot_id)

        if bot:
            # 添加用户到bot的活跃用户列表
            bot.add_user(telegram_id)

        return bot

    def get_bot_by_id(self, bot_id: int) -> Optional[BotInstance]:
        """根据ID获取Bot实例"""
        return next((bot for bot in self.bot_instances if bot.bot_id == bot_id), None)

    def get_pool_stats(self) -> Dict:
        """
        获取Bot池统计信息

        Returns:
            统计数据字典
        """
        total_bots = len(self.bot_instances)
        running_bots = sum(1 for bot in self.bot_instances if bot.is_running)
        total_users = sum(len(bot.active_users) for bot in self.bot_instances)
        total_capacity = sum(bot.max_load for bot in self.bot_instances)

        bot_stats = [bot.get_stats() for bot in self.bot_instances]
        health_report = self.health_checker.get_health_report(self.bot_instances)
        lb_stats = self.load_balancer.get_stats()

        return {
            'pool_status': {
                'is_running': self.is_running,
                'total_bots': total_bots,
                'running_bots': running_bots,
                'total_active_users': total_users,
                'total_capacity': total_capacity,
                'utilization_rate': round((total_users / total_capacity * 100), 2) if total_capacity > 0 else 0
            },
            'bots': bot_stats,
            'health': health_report,
            'load_balancer': lb_stats
        }

    def _print_pool_status(self):
        """打印Bot池状态"""
        logger.info("=" * 60)
        logger.info("Bot池状态:")
        logger.info(f"  总Bot数: {len(self.bot_instances)}")
        for bot in self.bot_instances:
            status = "🟢 运行中" if bot.is_running else "🔴 已停止"
            logger.info(
                f"  - {bot.bot_username}: {status} "
                f"(负载: {len(bot.active_users)}/{bot.max_load}, "
                f"优先级: {bot.priority})"
            )
        logger.info("=" * 60)
