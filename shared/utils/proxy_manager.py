"""
代理管理模块 - 支持MTProxy、SOCKS5、HTTP代理
"""
import re
from typing import Optional, Dict, Union
from urllib.parse import urlparse, parse_qs
from telethon import connection

from shared.utils.logger import logger


class ProxyManager:
    """代理管理器"""

    PROXY_TYPES = {
        'mtproto': 'MTProto代理',
        'socks5': 'SOCKS5代理',
        'socks4': 'SOCKS4代理',
        'http': 'HTTP代理',
    }

    @staticmethod
    def parse_mtproxy_link(link: str) -> Optional[Dict]:
        """
        解析MTProxy代理链接

        Args:
            link: MTProxy链接
                 格式: https://t.me/proxy?server=IP&port=PORT&secret=SECRET

        Returns:
            代理配置字典
        """
        try:
            # 解析URL
            if not link.startswith('https://t.me/proxy'):
                logger.error("无效的MTProxy链接格式")
                return None

            parsed = urlparse(link)
            params = parse_qs(parsed.query)

            server = params.get('server', [None])[0]
            port = params.get('port', [None])[0]
            secret = params.get('secret', [None])[0]

            if not all([server, port, secret]):
                logger.error("MTProxy链接缺少必要参数")
                return None

            proxy_config = {
                'type': 'mtproto',
                'server': server,
                'port': int(port),
                'secret': secret
            }

            logger.info(f"✅ MTProxy解析成功: {server}:{port}")
            return proxy_config

        except Exception as e:
            logger.error(f"解析MTProxy链接失败: {str(e)}")
            return None

    @staticmethod
    def create_telethon_proxy(proxy_config: Dict) -> Optional[tuple]:
        """
        创建Telethon客户端使用的代理配置

        Args:
            proxy_config: 代理配置字典

        Returns:
            Telethon代理元组
        """
        try:
            proxy_type = proxy_config.get('type', '').lower()

            if proxy_type == 'mtproto':
                # MTProto代理配置
                return (
                    connection.ConnectionTcpMTProxyRandomizedIntermediate,
                    proxy_config['server'],
                    proxy_config['port'],
                    proxy_config['secret']
                )

            elif proxy_type == 'socks5':
                # SOCKS5代理配置
                import socks
                return (
                    socks.SOCKS5,
                    proxy_config['server'],
                    proxy_config['port'],
                    True,  # rdns
                    proxy_config.get('username'),
                    proxy_config.get('password')
                )

            elif proxy_type == 'socks4':
                # SOCKS4代理配置
                import socks
                return (
                    socks.SOCKS4,
                    proxy_config['server'],
                    proxy_config['port'],
                    True,  # rdns
                    proxy_config.get('username'),
                    proxy_config.get('password')
                )

            elif proxy_type == 'http':
                # HTTP代理配置
                import socks
                return (
                    socks.HTTP,
                    proxy_config['server'],
                    proxy_config['port'],
                    True,  # rdns
                    proxy_config.get('username'),
                    proxy_config.get('password')
                )

            else:
                logger.error(f"不支持的代理类型: {proxy_type}")
                return None

        except Exception as e:
            logger.error(f"创建Telethon代理失败: {str(e)}")
            return None

    @staticmethod
    def parse_socks5_string(proxy_str: str) -> Optional[Dict]:
        """
        解析SOCKS5代理字符串

        Args:
            proxy_str: 代理字符串
                      格式1: socks5://IP:PORT
                      格式2: socks5://USER:PASS@IP:PORT

        Returns:
            代理配置字典
        """
        try:
            # 正则匹配
            pattern = r'socks5://(?:([^:]+):([^@]+)@)?([^:]+):(\d+)'
            match = re.match(pattern, proxy_str)

            if not match:
                logger.error("无效的SOCKS5代理格式")
                return None

            username, password, server, port = match.groups()

            proxy_config = {
                'type': 'socks5',
                'server': server,
                'port': int(port)
            }

            if username and password:
                proxy_config['username'] = username
                proxy_config['password'] = password

            logger.info(f"✅ SOCKS5解析成功: {server}:{port}")
            return proxy_config

        except Exception as e:
            logger.error(f"解析SOCKS5代理失败: {str(e)}")
            return None

    @staticmethod
    def test_proxy(proxy_config: Dict, api_id: int, api_hash: str) -> bool:
        """
        测试代理连接

        Args:
            proxy_config: 代理配置
            api_id: Telegram API ID
            api_hash: Telegram API Hash

        Returns:
            是否连接成功
        """
        try:
            from telethon import TelegramClient
            from telethon.sessions import StringSession
            import asyncio

            async def test():
                proxy = ProxyManager.create_telethon_proxy(proxy_config)

                if not proxy:
                    return False

                # 创建临时客户端测试连接
                client = TelegramClient(
                    StringSession(),
                    api_id,
                    api_hash,
                    proxy=proxy
                )

                try:
                    await client.connect()
                    is_connected = await client.is_connected()
                    await client.disconnect()
                    return is_connected
                except Exception as e:
                    logger.error(f"代理测试失败: {str(e)}")
                    return False

            # 运行异步测试
            result = asyncio.run(test())

            if result:
                logger.info("✅ 代理连接测试成功")
            else:
                logger.error("❌ 代理连接测试失败")

            return result

        except Exception as e:
            logger.error(f"代理测试异常: {str(e)}")
            return False


class ProxyPool:
    """代理池管理"""

    def __init__(self):
        self.proxies = []
        self.current_index = 0

    def add_proxy(self, proxy_config: Dict):
        """添加代理到池"""
        self.proxies.append(proxy_config)
        logger.info(f"✅ 代理已添加到池: {proxy_config['server']}:{proxy_config['port']}")

    def add_mtproxy_link(self, link: str):
        """通过MTProxy链接添加代理"""
        proxy_config = ProxyManager.parse_mtproxy_link(link)
        if proxy_config:
            self.add_proxy(proxy_config)
            return True
        return False

    def get_next_proxy(self) -> Optional[Dict]:
        """获取下一个代理（轮询）"""
        if not self.proxies:
            return None

        proxy = self.proxies[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.proxies)

        return proxy

    def get_random_proxy(self) -> Optional[Dict]:
        """随机获取代理"""
        import random
        return random.choice(self.proxies) if self.proxies else None

    def remove_proxy(self, server: str, port: int):
        """移除代理"""
        self.proxies = [
            p for p in self.proxies
            if not (p['server'] == server and p['port'] == port)
        ]
        logger.info(f"✅ 代理已移除: {server}:{port}")

    def count(self) -> int:
        """获取代理数量"""
        return len(self.proxies)

    def list_proxies(self) -> list:
        """列出所有代理"""
        return [
            f"{p['type']}://{p['server']}:{p['port']}"
            for p in self.proxies
        ]


# 全局代理池实例
proxy_pool = ProxyPool()


# 示例使用
def example_usage():
    """示例：代理管理（无硬编码代理）"""

    # 1. 解析MTProxy链接示例（需要从管理后台添加）
    # mtproxy_link = "https://t.me/proxy?server=YOUR_SERVER&port=YOUR_PORT&secret=YOUR_SECRET"
    # proxy_config = ProxyManager.parse_mtproxy_link(mtproxy_link)
    # print(f"✅ MTProxy配置: {proxy_config}")

    # 2. 解析SOCKS5代理示例
    # socks5_proxy = "socks5://user:pass@127.0.0.1:1080"
    # socks5_config = ProxyManager.parse_socks5_string(socks5_proxy)
    # if socks5_config:
    #     proxy_pool.add_proxy(socks5_config)

    # 3. 查看代理池状态
    print(f"代理池数量: {proxy_pool.count()}")
    if proxy_pool.count() > 0:
        print(f"代理列表:")
        for proxy in proxy_pool.list_proxies():
            print(f"  - {proxy}")
    else:
        print("代理池为空 - 系统将在无代理模式下运行")
        print("可通过管理后台添加代理")

    # 4. 使用代理创建客户端示例
    proxy = proxy_pool.get_next_proxy()
    if proxy:
        print(f"\n✅ 可用代理: {proxy['server']}:{proxy['port']}")
    else:
        print("\n⚠️  无可用代理，将使用直连模式")


if __name__ == "__main__":
    example_usage()
