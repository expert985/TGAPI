"""
设备管理模块 - 管理和踢出其他登录设备（防找回核心功能）
"""
from telethon import functions, types
from telethon import TelegramClient
from datetime import datetime
from typing import List, Dict, Optional

from shared.utils.logger import logger


class DeviceManager:
    """设备管理器 - 踢出其他设备是防找回的核心步骤"""

    @staticmethod
    async def get_active_sessions(client: TelegramClient) -> List[Dict]:
        """
        获取所有活跃设备列表

        Args:
            client: Telegram客户端

        Returns:
            活跃设备列表
        """
        try:
            result = await client(functions.account.GetAuthorizationsRequest())

            sessions = []
            for auth in result.authorizations:
                session_info = {
                    "hash": auth.hash,
                    "device": auth.device_model,
                    "platform": auth.platform,
                    "system_version": auth.system_version,
                    "app_name": auth.app_name,
                    "app_version": auth.app_version,
                    "date_created": datetime.fromtimestamp(auth.date_created),
                    "date_active": datetime.fromtimestamp(auth.date_active),
                    "ip": auth.ip,
                    "country": auth.country,
                    "region": auth.region,
                    "current": auth.current  # 是否为当前设备
                }
                sessions.append(session_info)

            logger.info(f"📱 获取到 {len(sessions)} 个活跃设备")
            return sessions

        except Exception as e:
            logger.error(f"获取活跃设备列表失败: {str(e)}")
            return []

    @staticmethod
    async def terminate_all_other_sessions(client: TelegramClient) -> tuple[bool, str]:
        """
        踢出所有其他活跃设备（防找回的核心功能）

        Args:
            client: Telegram客户端

        Returns:
            (是否成功, 消息)
        """
        try:
            # 获取当前设备数量
            sessions_before = await DeviceManager.get_active_sessions(client)
            other_devices = [s for s in sessions_before if not s["current"]]

            logger.info(f"🔨 准备踢出 {len(other_devices)} 个其他设备...")

            # 执行踢出操作
            result = await client(functions.auth.ResetAuthorizationsRequest())

            if result:
                logger.success(f"✅ 成功踢出所有其他设备 (共 {len(other_devices)} 个)")

                # 记录被踢出的设备信息
                for device in other_devices:
                    logger.info(f"   - {device['device']} ({device['platform']}) - IP: {device['ip']}")

                return True, f"成功踢出 {len(other_devices)} 个设备"
            else:
                return False, "踢出设备失败"

        except Exception as e:
            error_msg = f"踢出设备失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    @staticmethod
    async def terminate_specific_session(client: TelegramClient, session_hash: int) -> tuple[bool, str]:
        """
        踢出指定设备

        Args:
            client: Telegram客户端
            session_hash: 设备会话哈希值

        Returns:
            (是否成功, 消息)
        """
        try:
            result = await client(
                functions.account.ResetAuthorizationRequest(hash=session_hash)
            )

            if result:
                logger.info(f"✅ 成功踢出设备 (Hash: {session_hash})")
                return True, "设备已踢出"
            else:
                return False, "踢出失败"

        except Exception as e:
            error_msg = f"踢出指定设备失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    @staticmethod
    async def terminate_by_criteria(
        client: TelegramClient,
        device_pattern: Optional[str] = None,
        platform_pattern: Optional[str] = None,
        older_than_days: Optional[int] = None
    ) -> tuple[bool, str, int]:
        """
        按条件踢出设备

        Args:
            client: Telegram客户端
            device_pattern: 设备名称匹配模式（如"iPhone"）
            platform_pattern: 平台匹配模式（如"Android"）
            older_than_days: 踢出N天前活跃的设备

        Returns:
            (是否成功, 消息, 踢出数量)
        """
        try:
            sessions = await DeviceManager.get_active_sessions(client)
            to_terminate = []

            for session in sessions:
                if session["current"]:
                    continue  # 不踢当前设备

                should_terminate = True

                # 设备名称匹配
                if device_pattern and device_pattern.lower() not in session["device"].lower():
                    should_terminate = False

                # 平台匹配
                if platform_pattern and platform_pattern.lower() not in session["platform"].lower():
                    should_terminate = False

                # 时间匹配
                if older_than_days:
                    days_inactive = (datetime.now() - session["date_active"]).days
                    if days_inactive < older_than_days:
                        should_terminate = False

                if should_terminate:
                    to_terminate.append(session)

            # 执行踢出
            kicked_count = 0
            for session in to_terminate:
                success, _ = await DeviceManager.terminate_specific_session(
                    client, session["hash"]
                )
                if success:
                    kicked_count += 1

            return True, f"成功踢出 {kicked_count}/{len(to_terminate)} 个设备", kicked_count

        except Exception as e:
            error_msg = f"按条件踢出设备失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, 0


# 全局实例
device_manager = DeviceManager()


# 示例使用
async def example_usage():
    """示例：设备管理"""
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    # 创建客户端
    session_string = "YOUR_SESSION_STRING"
    api_id = 12345
    api_hash = "your_api_hash"

    client = TelegramClient(StringSession(session_string), api_id, api_hash)
    await client.connect()

    # 1. 查看所有活跃设备
    print("📱 当前活跃设备:")
    sessions = await device_manager.get_active_sessions(client)
    for i, session in enumerate(sessions, 1):
        current_mark = "✨ 当前设备" if session["current"] else ""
        print(f"{i}. {session['device']} ({session['platform']}) {current_mark}")
        print(f"   IP: {session['ip']} | 地区: {session['country']}")
        print(f"   最后活跃: {session['date_active']}")
        print()

    # 2. 踢出所有其他设备（防找回核心功能）
    success, msg = await device_manager.terminate_all_other_sessions(client)
    print(f"\n🔨 踢出结果: {msg}")

    # 3. 按条件踢出（例如：踢出所有Android设备）
    success, msg, count = await device_manager.terminate_by_criteria(
        client,
        platform_pattern="Android"
    )
    print(f"\n🎯 按条件踢出: {msg}")

    await client.disconnect()


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())
