"""
Telethon与Pyrogram格式互转工具
参考用户提供的转换脚本
"""
import struct
import base64
from telethon.sessions.string import StringSession as TelethonStringSession
from telethon import TelegramClient
from typing import Optional

from shared.utils.logger import logger


# 默认API凭证（Telegram官方）
DEFAULT_API_ID = 6
DEFAULT_API_HASH = "eb06d4abfb49dc3eeb1aeb98ae0f581e"


class TelethonToPyrogramConverter:
    """Telethon到Pyrogram格式转换器"""

    # Pyrogram Session字符串格式
    # 格式: base64(struct.pack(format, dc_id, api_id, test_mode, auth_key, user_id, is_bot))
    PYROGRAM_SESSION_FORMAT = ">B?256sQ?"

    @staticmethod
    def telethon_to_pyrogram(
        telethon_string: str,
        api_id: int = DEFAULT_API_ID,
        api_hash: str = DEFAULT_API_HASH,
        proxy: Optional[dict] = None
    ) -> Optional[str]:
        """
        将Telethon Session字符串转换为Pyrogram格式

        Args:
            telethon_string: Telethon的Session字符串
            api_id: Telegram API ID
            api_hash: Telegram API Hash
            proxy: 代理配置（可选）

        Returns:
            Pyrogram格式的Session字符串
        """
        try:
            # 1. 解析Telethon Session
            telethon_session = TelethonStringSession(telethon_string)

            # 2. 使用Telethon客户端获取必要信息
            client_params = {
                'session': TelethonStringSession(telethon_string),
                'api_id': api_id,
                'api_hash': api_hash
            }

            if proxy:
                client_params['proxy'] = proxy

            with TelegramClient(**client_params) as client:
                # 获取用户信息
                me = client.get_me()

                # 提取Session数据
                dc_id = telethon_session.dc_id
                auth_key = telethon_session.auth_key.key
                user_id = me.id
                is_bot = me.bot

            # 3. 构建Pyrogram Session数据
            # 格式: dc_id (1 byte) + test_mode (bool) + auth_key (256 bytes) + user_id (8 bytes) + is_bot (bool)
            pyrogram_data = struct.pack(
                TelethonToPyrogramConverter.PYROGRAM_SESSION_FORMAT,
                dc_id,        # DC ID
                False,        # test_mode (默认False)
                auth_key,     # Auth Key (256 bytes)
                user_id,      # User ID
                is_bot        # Is Bot
            )

            # 4. Base64编码
            pyrogram_string = base64.urlsafe_b64encode(pyrogram_data).decode().rstrip("=")

            logger.info(f"✅ Telethon转Pyrogram成功 (User ID: {user_id})")
            return pyrogram_string

        except Exception as e:
            logger.error(f"❌ Telethon转Pyrogram失败: {str(e)}")
            return None

    @staticmethod
    def pyrogram_to_telethon(
        pyrogram_string: str,
        api_id: int = DEFAULT_API_ID,
        api_hash: str = DEFAULT_API_HASH
    ) -> Optional[str]:
        """
        将Pyrogram Session字符串转换为Telethon格式

        Args:
            pyrogram_string: Pyrogram的Session字符串
            api_id: Telegram API ID
            api_hash: Telegram API Hash

        Returns:
            Telethon格式的Session字符串
        """
        try:
            # 1. 解码Pyrogram Session
            # 补齐Base64填充
            padding = 4 - len(pyrogram_string) % 4
            if padding != 4:
                pyrogram_string += "=" * padding

            pyrogram_data = base64.urlsafe_b64decode(pyrogram_string)

            # 2. 解析数据
            dc_id, test_mode, auth_key, user_id, is_bot = struct.unpack(
                TelethonToPyrogramConverter.PYROGRAM_SESSION_FORMAT,
                pyrogram_data
            )

            # 3. 创建Telethon Session
            # Telethon Session格式需要完整的session对象，这里比较复杂
            # 暂时返回基本信息
            logger.warning("⚠️ Pyrogram转Telethon需要完整的Session对象，当前仅返回基本信息")

            return {
                "dc_id": dc_id,
                "auth_key": auth_key.hex(),
                "user_id": user_id,
                "is_bot": is_bot,
                "test_mode": test_mode
            }

        except Exception as e:
            logger.error(f"❌ Pyrogram转Telethon失败: {str(e)}")
            return None

    @staticmethod
    def batch_convert_telethon_to_pyrogram(
        telethon_strings: list,
        api_id: int = DEFAULT_API_ID,
        api_hash: str = DEFAULT_API_HASH,
        proxy: Optional[dict] = None
    ) -> dict:
        """
        批量转换Telethon到Pyrogram

        Args:
            telethon_strings: Telethon Session字符串列表
            api_id: API ID
            api_hash: API Hash
            proxy: 代理配置

        Returns:
            转换结果统计
        """
        results = {
            "total": len(telethon_strings),
            "success": 0,
            "failed": 0,
            "conversions": []
        }

        for idx, telethon_string in enumerate(telethon_strings, 1):
            logger.info(f"转换进度: {idx}/{results['total']}")

            pyrogram_string = TelethonToPyrogramConverter.telethon_to_pyrogram(
                telethon_string=telethon_string,
                api_id=api_id,
                api_hash=api_hash,
                proxy=proxy
            )

            if pyrogram_string:
                results["success"] += 1
                results["conversions"].append({
                    "index": idx,
                    "status": "success",
                    "telethon": telethon_string,
                    "pyrogram": pyrogram_string
                })
            else:
                results["failed"] += 1
                results["conversions"].append({
                    "index": idx,
                    "status": "failed",
                    "telethon": telethon_string,
                    "error": "转换失败"
                })

        logger.info(f"📊 批量转换完成: 成功 {results['success']}/{results['total']}")
        return results


# 全局实例
telethon_pyrogram_converter = TelethonToPyrogramConverter()


# 示例使用
def example_usage():
    """示例：Telethon转Pyrogram"""

    # Telethon Session字符串
    telethon_string = "YOUR_TELETHON_SESSION_STRING_HERE"

    # 转换
    pyrogram_string = telethon_pyrogram_converter.telethon_to_pyrogram(
        telethon_string=telethon_string,
        api_id=DEFAULT_API_ID,
        api_hash=DEFAULT_API_HASH
    )

    if pyrogram_string:
        print(f"✅ 转换成功！")
        print(f"Pyrogram Session: {pyrogram_string}")
    else:
        print("❌ 转换失败")


if __name__ == "__main__":
    example_usage()
