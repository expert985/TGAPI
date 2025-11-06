"""
Bot Pool - 多机器人负载均衡系统

提供:
- 多Bot实例管理
- 智能负载均衡
- 自动健康检查
- 会话保持
- 故障自动恢复
"""
from .bot_instance import BotInstance
from .load_balancer import LoadBalancer, LoadBalanceStrategy
from .health_checker import HealthChecker
from .redis_cache import BotPoolRedisCache
from .bot_pool_manager import BotPoolManager

__all__ = [
    'BotInstance',
    'LoadBalancer',
    'LoadBalanceStrategy',
    'HealthChecker',
    'BotPoolRedisCache',
    'BotPoolManager',
]
