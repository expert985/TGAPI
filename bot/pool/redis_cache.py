"""
Bot Pool Redis缓存管理器
用于优化负载均衡性能，减少数据库查询
"""
import json
import redis
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from shared.utils.logger import logger


class BotPoolRedisCache:
    """Bot Pool Redis缓存管理器"""

    def __init__(self, redis_client: redis.Redis):
        """
        初始化缓存管理器

        Args:
            redis_client: Redis客户端实例
        """
        self.redis = redis_client
        self.prefix = "bot_pool:"

        # TTL配置（秒）
        self.TTL_BOT_STATUS = 60  # Bot状态缓存
        self.TTL_BOT_LOAD = 30  # Bot负载缓存
        self.TTL_USER_SESSION = 1800  # 用户会话缓存（30分钟）
        self.TTL_BOT_HEARTBEAT = 10  # Bot心跳缓存
        self.TTL_AVAILABLE_BOTS = 30  # 可用Bot列表缓存

    def _key(self, *parts) -> str:
        """生成Redis key"""
        return self.prefix + ":".join(map(str, parts))

    # ==================== Bot状态缓存 ====================

    def set_bot_status(self, bot_id: int, status: str, ttl: int = None) -> bool:
        """
        设置Bot状态

        Args:
            bot_id: Bot ID
            status: 状态（active/inactive/error/maintenance）
            ttl: 过期时间（秒），默认使用TTL_BOT_STATUS
        """
        try:
            key = self._key("bot", "status", bot_id)
            ttl = ttl or self.TTL_BOT_STATUS
            self.redis.setex(key, ttl, status)
            return True
        except Exception as e:
            logger.error(f"设置Bot状态缓存失败 bot_id={bot_id}: {e}")
            return False

    def get_bot_status(self, bot_id: int) -> Optional[str]:
        """获取Bot状态"""
        try:
            key = self._key("bot", "status", bot_id)
            status = self.redis.get(key)
            return status.decode() if status else None
        except Exception as e:
            logger.error(f"获取Bot状态缓存失败 bot_id={bot_id}: {e}")
            return None

    # ==================== Bot负载缓存 ====================

    def set_bot_load(self, bot_id: int, active_users: int, ttl: int = None) -> bool:
        """
        设置Bot当前负载

        Args:
            bot_id: Bot ID
            active_users: 当前活跃用户数
            ttl: 过期时间（秒）
        """
        try:
            key = self._key("bot", "load", bot_id)
            ttl = ttl or self.TTL_BOT_LOAD
            self.redis.setex(key, ttl, active_users)

            # 同时更新sorted set（按负载排序）
            self.redis.zadd(
                self._key("available_bots"),
                {str(bot_id): active_users},
                nx=False  # 更新已存在的
            )
            self.redis.expire(self._key("available_bots"), self.TTL_AVAILABLE_BOTS)

            return True
        except Exception as e:
            logger.error(f"设置Bot负载缓存失败 bot_id={bot_id}: {e}")
            return False

    def get_bot_load(self, bot_id: int) -> Optional[int]:
        """获取Bot当前负载"""
        try:
            key = self._key("bot", "load", bot_id)
            load = self.redis.get(key)
            return int(load) if load else None
        except Exception as e:
            logger.error(f"获取Bot负载缓存失败 bot_id={bot_id}: {e}")
            return None

    def get_least_loaded_bot(self) -> Optional[int]:
        """
        获取负载最低的Bot

        Returns:
            Bot ID，如果没有可用bot则返回None
        """
        try:
            # 从sorted set获取负载最低的bot
            result = self.redis.zrange(self._key("available_bots"), 0, 0)
            if result:
                return int(result[0])
            return None
        except Exception as e:
            logger.error(f"获取最低负载Bot失败: {e}")
            return None

    def remove_bot_from_pool(self, bot_id: int) -> bool:
        """从可用Bot池中移除Bot"""
        try:
            self.redis.zrem(self._key("available_bots"), str(bot_id))
            return True
        except Exception as e:
            logger.error(f"从Bot池移除失败 bot_id={bot_id}: {e}")
            return False

    # ==================== 用户会话缓存 ====================

    def set_user_session(self, telegram_id: int, bot_id: int, ttl: int = None) -> bool:
        """
        设置用户-Bot会话映射

        Args:
            telegram_id: Telegram用户ID
            bot_id: 分配的Bot ID
            ttl: 过期时间（秒），默认30分钟
        """
        try:
            key = self._key("user", "session", telegram_id)
            ttl = ttl or self.TTL_USER_SESSION

            session_data = {
                "bot_id": bot_id,
                "assigned_at": datetime.now().isoformat(),
                "last_access": datetime.now().isoformat()
            }

            self.redis.setex(key, ttl, json.dumps(session_data))
            return True
        except Exception as e:
            logger.error(f"设置用户会话缓存失败 telegram_id={telegram_id}: {e}")
            return False

    def get_user_session(self, telegram_id: int) -> Optional[int]:
        """
        获取用户分配的Bot ID

        Returns:
            Bot ID，如果没有会话则返回None
        """
        try:
            key = self._key("user", "session", telegram_id)
            data = self.redis.get(key)

            if data:
                session = json.loads(data)
                # 更新最后访问时间
                session["last_access"] = datetime.now().isoformat()
                self.redis.setex(key, self.TTL_USER_SESSION, json.dumps(session))
                return session["bot_id"]

            return None
        except Exception as e:
            logger.error(f"获取用户会话缓存失败 telegram_id={telegram_id}: {e}")
            return None

    def delete_user_session(self, telegram_id: int) -> bool:
        """删除用户会话（用于强制重新分配）"""
        try:
            key = self._key("user", "session", telegram_id)
            self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"删除用户会话缓存失败 telegram_id={telegram_id}: {e}")
            return False

    # ==================== Bot心跳缓存 ====================

    def update_heartbeat(self, bot_id: int, ttl: int = None) -> bool:
        """
        更新Bot心跳

        Args:
            bot_id: Bot ID
            ttl: 过期时间（秒），默认10秒
        """
        try:
            key = self._key("bot", "heartbeat", bot_id)
            ttl = ttl or self.TTL_BOT_HEARTBEAT
            self.redis.setex(key, ttl, datetime.now().isoformat())
            return True
        except Exception as e:
            logger.error(f"更新Bot心跳失败 bot_id={bot_id}: {e}")
            return False

    def check_heartbeat(self, bot_id: int) -> bool:
        """
        检查Bot心跳是否正常

        Returns:
            True表示心跳正常，False表示已超时
        """
        try:
            key = self._key("bot", "heartbeat", bot_id)
            return self.redis.exists(key) > 0
        except Exception as e:
            logger.error(f"检查Bot心跳失败 bot_id={bot_id}: {e}")
            return False

    # ==================== Bot统计缓存 ====================

    def increment_message_count(self, bot_id: int, count: int = 1) -> int:
        """
        增加Bot消息计数（用于计算messages_per_min）

        Returns:
            当前计数
        """
        try:
            key = self._key("bot", "messages", bot_id)
            count = self.redis.incrby(key, count)
            # 设置1分钟过期
            self.redis.expire(key, 60)
            return count
        except Exception as e:
            logger.error(f"增加Bot消息计数失败 bot_id={bot_id}: {e}")
            return 0

    def get_message_count(self, bot_id: int) -> int:
        """获取Bot当前分钟消息数"""
        try:
            key = self._key("bot", "messages", bot_id)
            count = self.redis.get(key)
            return int(count) if count else 0
        except Exception as e:
            logger.error(f"获取Bot消息计数失败 bot_id={bot_id}: {e}")
            return 0

    # ==================== 批量操作 ====================

    def get_all_bot_loads(self) -> Dict[int, int]:
        """
        获取所有Bot的负载

        Returns:
            {bot_id: active_users}
        """
        try:
            result = self.redis.zrange(
                self._key("available_bots"),
                0,
                -1,
                withscores=True
            )
            return {int(bot_id): int(score) for bot_id, score in result}
        except Exception as e:
            logger.error(f"获取所有Bot负载失败: {e}")
            return {}

    def clear_bot_cache(self, bot_id: int) -> bool:
        """
        清除指定Bot的所有缓存

        Args:
            bot_id: Bot ID
        """
        try:
            keys = [
                self._key("bot", "status", bot_id),
                self._key("bot", "load", bot_id),
                self._key("bot", "heartbeat", bot_id),
                self._key("bot", "messages", bot_id)
            ]
            self.redis.delete(*keys)
            self.redis.zrem(self._key("available_bots"), str(bot_id))
            logger.info(f"✅ 清除Bot缓存: bot_id={bot_id}")
            return True
        except Exception as e:
            logger.error(f"清除Bot缓存失败 bot_id={bot_id}: {e}")
            return False

    def clear_all_cache(self) -> bool:
        """清除所有Bot Pool相关缓存"""
        try:
            keys = self.redis.keys(f"{self.prefix}*")
            if keys:
                self.redis.delete(*keys)
            logger.info(f"✅ 清除所有Bot Pool缓存: {len(keys)}个key")
            return True
        except Exception as e:
            logger.error(f"清除所有缓存失败: {e}")
            return False
