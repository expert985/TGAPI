"""
Load Balancer - 智能负载均衡器
负责用户到Bot的智能分配，支持会话保持和多种负载均衡策略
"""
from typing import Optional, List
from enum import Enum
from datetime import datetime
from shared.utils.logger import logger
from shared.database.init import db
from .redis_cache import BotPoolRedisCache


class LoadBalanceStrategy(Enum):
    """负载均衡策略"""
    LEAST_CONNECTIONS = "least_connections"  # 最少连接数
    WEIGHTED_RANDOM = "weighted_random"  # 加权随机
    PRIORITY_BASED = "priority_based"  # 基于优先级


class LoadBalancer:
    """
    智能负载均衡器

    特性:
    - 会话保持（同一用户总是使用同一个bot）
    - 多种负载均衡策略
    - 健康检查
    - 自动故障转移
    """

    def __init__(
        self,
        redis_cache: BotPoolRedisCache,
        strategy: LoadBalanceStrategy = LoadBalanceStrategy.LEAST_CONNECTIONS
    ):
        """
        初始化负载均衡器

        Args:
            redis_cache: Redis缓存管理器
            strategy: 负载均衡策略
        """
        self.redis_cache = redis_cache
        self.strategy = strategy
        logger.info(f"⚖️  LoadBalancer初始化: strategy={strategy.value}")

    def assign_bot(
        self,
        telegram_id: int,
        available_bot_instances: List
    ) -> Optional[int]:
        """
        为用户分配Bot

        Args:
            telegram_id: Telegram用户ID
            available_bot_instances: 可用的BotInstance列表

        Returns:
            分配的bot_id，如果分配失败则返回None
        """
        if not available_bot_instances:
            logger.error("❌ 没有可用的Bot实例")
            return None

        # 1. 检查会话保持 - 用户是否已经有分配的bot
        existing_bot_id = self._get_existing_session(telegram_id)
        if existing_bot_id:
            # 检查该bot是否仍然可用
            existing_bot = next(
                (b for b in available_bot_instances if b.bot_id == existing_bot_id),
                None
            )
            if existing_bot and existing_bot.can_accept_new_user():
                logger.debug(
                    f"🔄 会话保持: 用户 {telegram_id} 继续使用Bot {existing_bot.bot_username}"
                )
                return existing_bot_id

        # 2. 过滤健康且未满载的bot
        healthy_bots = [
            bot for bot in available_bot_instances
            if bot.is_running and bot.can_accept_new_user()
        ]

        if not healthy_bots:
            logger.error("❌ 没有健康且未满载的Bot")
            return None

        # 3. 根据策略选择bot
        selected_bot = None

        if self.strategy == LoadBalanceStrategy.LEAST_CONNECTIONS:
            selected_bot = self._select_least_connections(healthy_bots)

        elif self.strategy == LoadBalanceStrategy.WEIGHTED_RANDOM:
            selected_bot = self._select_weighted_random(healthy_bots)

        elif self.strategy == LoadBalanceStrategy.PRIORITY_BASED:
            selected_bot = self._select_priority_based(healthy_bots)

        if not selected_bot:
            logger.error("❌ 负载均衡策略未能选择Bot")
            return None

        # 4. 记录分配
        bot_id = selected_bot.bot_id
        self._record_assignment(telegram_id, bot_id)

        logger.info(
            f"✅ 用户分配: telegram_id={telegram_id} -> bot={selected_bot.bot_username} "
            f"(负载: {len(selected_bot.active_users)}/{selected_bot.max_load})"
        )

        return bot_id

    def _get_existing_session(self, telegram_id: int) -> Optional[int]:
        """
        获取用户现有会话

        Args:
            telegram_id: Telegram用户ID

        Returns:
            已分配的bot_id，如果没有则返回None
        """
        # 1. 先从Redis缓存查询
        cached_bot_id = self.redis_cache.get_user_session(telegram_id)
        if cached_bot_id:
            return cached_bot_id

        # 2. 从数据库查询
        try:
            session = db.fetchone(
                """SELECT assigned_bot_id FROM user_bot_sessions
                   WHERE telegram_id = ?
                   AND last_interaction > datetime('now', '-30 minutes')""",
                (telegram_id,)
            )

            if session:
                bot_id = session['assigned_bot_id']
                # 回写到Redis缓存
                self.redis_cache.set_user_session(telegram_id, bot_id)
                return bot_id

        except Exception as e:
            logger.error(f"查询用户会话失败: {e}")

        return None

    def _record_assignment(self, telegram_id: int, bot_id: int):
        """
        记录用户-Bot分配

        Args:
            telegram_id: Telegram用户ID
            bot_id: 分配的Bot ID
        """
        # 1. 写入Redis缓存
        self.redis_cache.set_user_session(telegram_id, bot_id)

        # 2. 写入数据库
        try:
            db.execute(
                """INSERT INTO user_bot_sessions
                   (telegram_id, assigned_bot_id, session_started, last_interaction)
                   VALUES (?, ?, ?, ?)
                   ON DUPLICATE KEY UPDATE
                   assigned_bot_id = VALUES(assigned_bot_id),
                   last_interaction = VALUES(last_interaction)""",
                (telegram_id, bot_id, datetime.now(), datetime.now())
            )

            # 记录分配事件
            db.execute(
                """INSERT INTO bot_events
                   (bot_id, event_type, event_level, message, details)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    bot_id,
                    'user_assigned',
                    'info',
                    f'用户 {telegram_id} 分配到此Bot',
                    f'{{"telegram_id": {telegram_id}, "strategy": "{self.strategy.value}"}}'
                )
            )

        except Exception as e:
            logger.error(f"记录用户分配失败: {e}")

    def _select_least_connections(self, bots: List) -> Optional:
        """
        最少连接策略 - 选择当前活跃用户数最少的bot

        Args:
            bots: BotInstance列表

        Returns:
            选中的BotInstance
        """
        if not bots:
            return None

        # 按活跃用户数排序，优先级作为次要排序
        sorted_bots = sorted(
            bots,
            key=lambda b: (len(b.active_users), -b.priority)
        )

        return sorted_bots[0]

    def _select_weighted_random(self, bots: List) -> Optional:
        """
        加权随机策略 - 根据剩余容量加权随机选择

        Args:
            bots: BotInstance列表

        Returns:
            选中的BotInstance
        """
        import random

        if not bots:
            return None

        # 计算每个bot的剩余容量作为权重
        weights = []
        for bot in bots:
            remaining_capacity = bot.max_load - len(bot.active_users)
            # 考虑优先级
            weight = remaining_capacity * bot.priority
            weights.append(weight)

        # 加权随机选择
        selected = random.choices(bots, weights=weights, k=1)[0]
        return selected

    def _select_priority_based(self, bots: List) -> Optional:
        """
        优先级策略 - 优先选择高优先级且负载不满的bot

        Args:
            bots: BotInstance列表

        Returns:
            选中的BotInstance
        """
        if not bots:
            return None

        # 按优先级降序，负载升序排序
        sorted_bots = sorted(
            bots,
            key=lambda b: (-b.priority, len(b.active_users))
        )

        return sorted_bots[0]

    def reassign_user(self, telegram_id: int, new_bot_id: int) -> bool:
        """
        强制重新分配用户到指定Bot

        Args:
            telegram_id: Telegram用户ID
            new_bot_id: 新的Bot ID

        Returns:
            True表示成功
        """
        try:
            # 删除旧会话
            self.redis_cache.delete_user_session(telegram_id)

            # 创建新会话
            self._record_assignment(telegram_id, new_bot_id)

            logger.info(f"✅ 用户 {telegram_id} 重新分配到Bot {new_bot_id}")
            return True

        except Exception as e:
            logger.error(f"重新分配用户失败: {e}")
            return False

    def get_user_assignment(self, telegram_id: int) -> Optional[int]:
        """
        查询用户当前分配的Bot

        Args:
            telegram_id: Telegram用户ID

        Returns:
            bot_id，如果没有分配则返回None
        """
        return self._get_existing_session(telegram_id)

    def clear_user_session(self, telegram_id: int) -> bool:
        """
        清除用户会话（强制下次重新分配）

        Args:
            telegram_id: Telegram用户ID

        Returns:
            True表示成功
        """
        try:
            # 从Redis删除
            self.redis_cache.delete_user_session(telegram_id)

            # 从数据库删除
            db.execute(
                "DELETE FROM user_bot_sessions WHERE telegram_id = ?",
                (telegram_id,)
            )

            logger.info(f"✅ 清除用户会话: telegram_id={telegram_id}")
            return True

        except Exception as e:
            logger.error(f"清除用户会话失败: {e}")
            return False

    def get_stats(self) -> dict:
        """
        获取负载均衡统计

        Returns:
            统计数据字典
        """
        try:
            total_sessions = db.fetchone(
                "SELECT COUNT(*) as count FROM user_bot_sessions"
            )['count']

            active_sessions = db.fetchone(
                """SELECT COUNT(*) as count FROM user_bot_sessions
                   WHERE last_interaction > datetime('now', '-30 minutes')"""
            )['count']

            return {
                'strategy': self.strategy.value,
                'total_sessions': total_sessions,
                'active_sessions': active_sessions,
                'cache_hit_rate': self._calculate_cache_hit_rate()
            }

        except Exception as e:
            logger.error(f"获取负载均衡统计失败: {e}")
            return {}

    def _calculate_cache_hit_rate(self) -> float:
        """计算缓存命中率（简化版）"""
        # 这里可以实现更复杂的缓存命中率统计
        return 0.0
