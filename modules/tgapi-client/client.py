"""
TGAPI接码客户端 - 逆向接码工具
通过TGAPI URL自动接码并生成新设备（号商接管账号的核心工具）
"""
import asyncio
import aiohttp
from typing import Optional, Dict
from telethon import TelegramClient, functions
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

from shared.utils.logger import logger
from shared.database.init import db


class TGAPIClient:
    """TGAPI接码客户端 - 逆向接码生成新设备"""

    def __init__(self):
        self.sessions = {}

    async def login_via_api(
        self,
        api_url: str,
        phone: str,
        api_id: int,
        api_hash: str,
        proxy: Optional[Dict] = None,
        kick_other_devices: bool = True,
        output_format: str = "session",
        timeout: int = 120
    ) -> tuple[bool, str, Optional[Dict]]:
        """
        通过TGAPI URL接码登录并生成新设备

        Args:
            api_url: TGAPI接码链接
            phone: 手机号
            api_id: Telegram API ID
            api_hash: Telegram API Hash
            proxy: 代理配置（可选）
            kick_other_devices: 是否踢出其他设备
            output_format: 输出格式 ('session', 'json', 'tdata')
            timeout: 接码超时时间（秒）

        Returns:
            (是否成功, 消息, 结果数据)
        """
        try:
            logger.info(f"🔨 开始通过TGAPI接码登录: {phone}")

            # 1. 创建Telegram客户端
            client_params = {}
            if proxy:
                client_params['proxy'] = (
                    proxy.get('type', 'socks5'),
                    proxy.get('host'),
                    proxy.get('port'),
                    True,  # rdns
                    proxy.get('username'),
                    proxy.get('password')
                )

            client = TelegramClient(
                StringSession(),
                api_id,
                api_hash,
                **client_params
            )

            await client.connect()

            # 2. 发送验证码
            logger.info(f"📱 正在发送验证码到: {phone}")
            sent_code = await client.send_code_request(phone)

            # 3. 从TGAPI URL获取验证码
            logger.info(f"⏳ 正在从TGAPI获取验证码...")
            code = await self._fetch_code_from_api(api_url, timeout)

            if not code:
                await client.disconnect()
                return False, "获取验证码超时", None

            logger.info(f"📨 收到验证码: {code}")

            # 4. 使用验证码登录
            try:
                await client.sign_in(phone, code, phone_code_hash=sent_code.phone_code_hash)
            except SessionPasswordNeededError:
                # 需要两步验证密码
                logger.info("🔐 需要两步验证密码")

                # 尝试从API获取2FA密码
                password = await self._fetch_2fa_from_api(api_url, timeout=60)

                if not password:
                    await client.disconnect()
                    return False, "需要两步验证密码", {"requires_2fa": True}

                # 使用密码登录
                await client.sign_in(password=password)

            # 5. 验证登录成功
            if not await client.is_user_authorized():
                await client.disconnect()
                return False, "登录失败", None

            # 获取用户信息
            me = await client.get_me()
            logger.info(f"✅ 登录成功: {me.first_name} (@{me.username})")

            # 6. 踢出其他设备（防找回）
            if kick_other_devices:
                logger.info("🔨 正在踢出其他设备...")
                await client(functions.auth.ResetAuthorizationsRequest())
                logger.info("✅ 其他设备已踢出")

            # 7. 保存Session
            session_string = StringSession.save(client.session)

            result = {
                "phone": phone,
                "user_id": me.id,
                "username": me.username,
                "first_name": me.first_name,
                "session_string": session_string,
                "api_id": api_id,
                "api_hash": api_hash
            }

            # 8. 根据输出格式处理
            if output_format == "json":
                from modules.converter.converter import converter
                json_data = converter.session_to_json(session_string, api_id, api_hash)
                result["json_data"] = json_data

            elif output_format == "tdata":
                logger.warning("TData格式需要opentele库，请确保已安装")
                # 可以调用converter的session_to_tdata方法

            # 保存到数据库
            cursor = db.execute(
                """
                INSERT INTO accounts (phone, session_type, session_data, api_id, api_hash, status)
                VALUES (?, ?, ?, ?, ?, 'active')
                """,
                (phone, output_format, str(result), str(api_id), api_hash)
            )
            account_id = cursor.lastrowid
            result["account_id"] = account_id

            await client.disconnect()

            logger.success(f"🎉 TGAPI接码登录完成: {phone}")
            return True, "登录成功", result

        except Exception as e:
            error_msg = f"TGAPI接码登录失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, None

    async def _fetch_code_from_api(self, api_url: str, timeout: int = 120) -> Optional[str]:
        """
        从TGAPI URL获取验证码

        Args:
            api_url: API链接
            timeout: 超时时间

        Returns:
            验证码
        """
        try:
            async with aiohttp.ClientSession() as session:
                # 构建完整的API URL
                if not api_url.endswith('/'):
                    api_url += '/'

                # 等待验证码
                async with session.get(
                    api_url,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()

                        if data.get('success'):
                            code = data.get('code')
                            logger.info(f"✅ 从API获取验证码成功: {code}")
                            return code
                        else:
                            logger.error(f"API返回错误: {data.get('message')}")
                            return None
                    else:
                        logger.error(f"API请求失败: HTTP {resp.status}")
                        return None

        except asyncio.TimeoutError:
            logger.error("获取验证码超时")
            return None
        except Exception as e:
            logger.error(f"从API获取验证码失败: {str(e)}")
            return None

    async def _fetch_2fa_from_api(self, api_url: str, timeout: int = 60) -> Optional[str]:
        """
        从TGAPI URL获取两步验证密码

        Args:
            api_url: API链接
            timeout: 超时时间

        Returns:
            2FA密码
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    api_url,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()

                        # 检查是否返回了2FA密码
                        if data.get('type') == '2fa':
                            # 从消息中提取密码（需要根据实际API格式调整）
                            password = data.get('password') or data.get('message')
                            logger.info("✅ 从API获取2FA密码")
                            return password

                    return None

        except Exception as e:
            logger.error(f"从API获取2FA密码失败: {str(e)}")
            return None

    async def batch_login_via_api(
        self,
        api_configs: list,
        proxy: Optional[Dict] = None,
        max_concurrent: int = 5
    ) -> Dict:
        """
        批量通过TGAPI接码登录

        Args:
            api_configs: API配置列表，每项包含 {api_url, phone, api_id, api_hash}
            proxy: 代理配置
            max_concurrent: 最大并发数

        Returns:
            统计结果
        """
        stats = {
            "total": len(api_configs),
            "success": 0,
            "failed": 0,
            "results": []
        }

        # 使用信号量控制并发
        semaphore = asyncio.Semaphore(max_concurrent)

        async def login_with_limit(config):
            async with semaphore:
                return await self.login_via_api(
                    api_url=config['api_url'],
                    phone=config['phone'],
                    api_id=config['api_id'],
                    api_hash=config['api_hash'],
                    proxy=proxy
                )

        # 并发执行
        tasks = [login_with_limit(config) for config in api_configs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 统计结果
        for config, result in zip(api_configs, results):
            if isinstance(result, Exception):
                stats["failed"] += 1
                stats["results"].append({
                    "phone": config['phone'],
                    "success": False,
                    "error": str(result)
                })
            else:
                success, msg, data = result
                if success:
                    stats["success"] += 1
                else:
                    stats["failed"] += 1

                stats["results"].append({
                    "phone": config['phone'],
                    "success": success,
                    "message": msg,
                    "data": data
                })

        logger.info(f"📊 批量接码完成: 成功 {stats['success']}/{stats['total']}")
        return stats


# 全局实例
tgapi_client = TGAPIClient()


# 示例使用
async def example_usage():
    """示例：通过TGAPI接码登录"""

    # 单个账号接码
    api_url = "https://api.yourdomain.com/api/code/YOUR_API_TOKEN"
    phone = "+1234567890"
    api_id = 12345
    api_hash = "your_api_hash"

    # 可选：配置代理
    proxy = {
        "type": "socks5",
        "host": "127.0.0.1",
        "port": 1080,
        "username": "user",
        "password": "pass"
    }

    success, msg, result = await tgapi_client.login_via_api(
        api_url=api_url,
        phone=phone,
        api_id=api_id,
        api_hash=api_hash,
        proxy=None,  # 不使用代理
        kick_other_devices=True,  # 踢出其他设备
        output_format="session"
    )

    if success:
        print(f"✅ {msg}")
        print(f"Session: {result['session_string'][:50]}...")
        print(f"用户: {result['first_name']} (@{result['username']})")
    else:
        print(f"❌ {msg}")


if __name__ == "__main__":
    asyncio.run(example_usage())
