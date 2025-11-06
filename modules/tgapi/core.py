"""
TGAPI核心模块 - 将TG账号协议转换为在线接码API
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict
from telethon import TelegramClient, events
from telethon.sessions import StringSession
import json

from shared.database.init import db
from shared.utils.crypto import generate_api_token
from shared.utils.logger import logger


class TGAPIManager:
    """TGAPI管理器 - 核心功能类"""

    def __init__(self):
        self.active_sessions: Dict[str, TelegramClient] = {}
        self.code_handlers: Dict[str, asyncio.Queue] = {}

    async def create_api_link(
        self,
        session_string: str,
        api_id: int,
        api_hash: str,
        tenant_id: Optional[int] = None,
        account_id: Optional[int] = None,
        expire_hours: int = 24,
        max_login: int = -1,
        custom_copyright: str = None,
        show_2fa: bool = True,
        base_url: str = "http://localhost:3000"
    ) -> tuple[bool, str, Optional[str]]:
        """
        创建TGAPI接码链接

        Args:
            session_string: Session字符串
            api_id: Telegram API ID
            api_hash: Telegram API Hash
            tenant_id: 租户ID
            account_id: 账号ID
            expire_hours: 过期小时数
            max_login: 最大登录次数（-1为无限制）
            custom_copyright: 自定义版权信息
            show_2fa: 是否显示2FA
            base_url: API基础URL

        Returns:
            (是否成功, API链接或错误信息, API Token)
        """
        try:
            # 生成唯一的API Token
            api_token = generate_api_token()

            # 计算过期时间
            expire_at = datetime.now() + timedelta(hours=expire_hours)

            # 构建API URL
            api_url = f"{base_url}/api/code/{api_token}"

            # 保存到数据库
            db.create_tgapi_session(
                account_id=account_id,
                session_data=session_string,
                api_token=api_token,
                api_url=api_url,
                expire_at=expire_at,
                max_login=max_login,
                custom_copyright=custom_copyright
            )

            # 启动验证码监听
            await self._start_code_listener(
                api_token=api_token,
                session_string=session_string,
                api_id=api_id,
                api_hash=api_hash,
                show_2fa=show_2fa
            )

            logger.info(f"✅ TGAPI链接创建成功: {api_url}")
            return True, api_url, api_token

        except Exception as e:
            error_msg = f"创建TGAPI链接失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, None

    async def _start_code_listener(
        self,
        api_token: str,
        session_string: str,
        api_id: int,
        api_hash: str,
        show_2fa: bool = True
    ):
        """
        启动验证码监听器

        Args:
            api_token: API Token
            session_string: Session字符串
            api_id: Telegram API ID
            api_hash: Telegram API Hash
            show_2fa: 是否显示2FA
        """
        try:
            # 创建Telegram客户端
            client = TelegramClient(
                StringSession(session_string),
                api_id,
                api_hash
            )

            # 创建验证码队列
            code_queue = asyncio.Queue()
            self.code_handlers[api_token] = code_queue

            # 连接客户端
            await client.connect()

            # 注册消息处理器
            @client.on(events.NewMessage(incoming=True))
            async def handle_new_message(event):
                message = event.message.message
                sender = await event.get_sender()

                # 检测验证码消息
                code = self._extract_code(message)
                if code:
                    logger.info(f"📨 收到验证码: {code} (API Token: {api_token})")

                    # 推送到队列
                    await code_queue.put({
                        "code": code,
                        "message": message,
                        "sender": sender.username if sender else "Unknown",
                        "time": datetime.now().isoformat()
                    })

                    # 保存到数据库
                    db.add_code_push_log(
                        api_token=api_token,
                        code=code
                    )

                # 检测2FA消息
                if show_2fa and "two-step" in message.lower():
                    await code_queue.put({
                        "type": "2fa",
                        "message": message,
                        "time": datetime.now().isoformat()
                    })

            # 保存客户端实例
            self.active_sessions[api_token] = client

            logger.info(f"🎧 验证码监听器已启动: {api_token}")

        except Exception as e:
            logger.error(f"启动验证码监听器失败: {str(e)}")

    def _extract_code(self, message: str) -> Optional[str]:
        """
        从消息中提取验证码

        Args:
            message: 消息文本

        Returns:
            验证码（如果找到）
        """
        import re

        # 常见的验证码模式
        patterns = [
            r'\b(\d{5,6})\b',  # 5-6位数字
            r'code[:\s]+(\d{5,6})',  # "code: 12345"
            r'(\d{5,6})\s+is your',  # "12345 is your code"
        ]

        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    async def get_latest_code(self, api_token: str, timeout: int = 60) -> Optional[dict]:
        """
        获取最新的验证码

        Args:
            api_token: API Token
            timeout: 超时时间（秒）

        Returns:
            验证码信息字典
        """
        try:
            # 检查会话是否有效
            session_info = db.get_tgapi_session(api_token)
            if not session_info:
                return {"error": "API Token无效"}

            # 检查是否过期
            if session_info['expire_at']:
                expire_at = datetime.fromisoformat(session_info['expire_at'])
                if datetime.now() > expire_at:
                    return {"error": "API链接已过期"}

            # 检查登录次数限制
            if session_info['max_login'] > 0:
                if session_info['login_count'] >= session_info['max_login']:
                    return {"error": "已达到最大登录次数限制"}

            # 增加登录次数
            db.increment_login_count(api_token)

            # 从队列获取验证码
            if api_token in self.code_handlers:
                queue = self.code_handlers[api_token]
                try:
                    code_data = await asyncio.wait_for(queue.get(), timeout=timeout)
                    return code_data
                except asyncio.TimeoutError:
                    return {"error": "等待验证码超时"}

            return {"error": "验证码监听器未启动"}

        except Exception as e:
            logger.error(f"获取验证码失败: {str(e)}")
            return {"error": str(e)}

    async def stop_listener(self, api_token: str):
        """
        停止验证码监听器

        Args:
            api_token: API Token
        """
        try:
            if api_token in self.active_sessions:
                client = self.active_sessions[api_token]
                await client.disconnect()
                del self.active_sessions[api_token]

            if api_token in self.code_handlers:
                del self.code_handlers[api_token]

            logger.info(f"🔇 验证码监听器已停止: {api_token}")

        except Exception as e:
            logger.error(f"停止监听器失败: {str(e)}")

    async def cleanup_expired_sessions(self):
        """清理过期的会话"""
        try:
            # 查询所有过期的会话
            query = """
                SELECT api_token FROM tgapi_sessions
                WHERE status = 'active'
                AND expire_at IS NOT NULL
                AND expire_at < ?
            """
            expired_sessions = db.fetchall(query, (datetime.now(),))

            for session in expired_sessions:
                api_token = session['api_token']

                # 停止监听器
                await self.stop_listener(api_token)

                # 更新数据库状态
                db.execute(
                    "UPDATE tgapi_sessions SET status = 'expired' WHERE api_token = ?",
                    (api_token,)
                )

            logger.info(f"🧹 已清理 {len(expired_sessions)} 个过期会话")

        except Exception as e:
            logger.error(f"清理过期会话失败: {str(e)}")


# 全局实例
tgapi_manager = TGAPIManager()


# 示例使用
async def example_usage():
    """示例：创建TGAPI链接"""

    # 假设的session字符串和API凭证
    session_string = "YOUR_SESSION_STRING_HERE"
    api_id = 12345
    api_hash = "your_api_hash_here"

    # 创建API链接
    success, result, token = await tgapi_manager.create_api_link(
        session_string=session_string,
        api_id=api_id,
        api_hash=api_hash,
        expire_hours=24,
        max_login=10,
        custom_copyright="Powered by TGAPI"
    )

    if success:
        print(f"✅ API链接: {result}")
        print(f"🔑 Token: {token}")

        # 等待验证码
        print("⏳ 等待验证码...")
        code_data = await tgapi_manager.get_latest_code(token, timeout=120)
        print(f"📨 收到验证码: {code_data}")
    else:
        print(f"❌ 创建失败: {result}")


if __name__ == "__main__":
    # 初始化数据库
    db.initialize()

    # 运行示例
    asyncio.run(example_usage())
