"""
TG账号全格式转换器
支持: TData ⟷ Session ⟷ JSON ⟷ AuthKey
"""
import json
import base64
import struct
from pathlib import Path
from typing import Optional, Union
from telethon.sessions import StringSession
from telethon import TelegramClient

from shared.utils.logger import logger
from shared.database.init import db


class FormatConverter:
    """格式转换器"""

    @staticmethod
    def session_to_json(session_string: str, api_id: int, api_hash: str) -> dict:
        """
        Session字符串转JSON

        Args:
            session_string: Session字符串
            api_id: API ID
            api_hash: API Hash

        Returns:
            JSON格式的账号信息
        """
        try:
            # 解码session字符串
            decoded = base64.urlsafe_b64decode(session_string + "=" * (-len(session_string) % 4))

            # 解析session数据
            # Session格式: dc_id (1 byte) + server_address (variable) + port (2 bytes) + auth_key (256 bytes)
            dc_id = decoded[0]

            result = {
                "session_string": session_string,
                "api_id": api_id,
                "api_hash": api_hash,
                "dc_id": dc_id,
                "format": "session"
            }

            logger.info("✅ Session转JSON成功")
            return result

        except Exception as e:
            logger.error(f"Session转JSON失败: {str(e)}")
            return {}

    @staticmethod
    def json_to_session(json_data: dict) -> Optional[str]:
        """
        JSON转Session字符串

        Args:
            json_data: JSON格式的账号数据

        Returns:
            Session字符串
        """
        try:
            if "session_string" in json_data:
                return json_data["session_string"]

            logger.error("JSON数据中缺少session_string字段")
            return None

        except Exception as e:
            logger.error(f"JSON转Session失败: {str(e)}")
            return None

    @staticmethod
    def session_to_authkey(session_string: str) -> Optional[bytes]:
        """
        Session字符串转AuthKey

        Args:
            session_string: Session字符串

        Returns:
            AuthKey字节数据
        """
        try:
            decoded = base64.urlsafe_b64decode(session_string + "=" * (-len(session_string) % 4))

            # AuthKey通常是最后256字节
            if len(decoded) >= 256:
                auth_key = decoded[-256:]
                logger.info("✅ Session转AuthKey成功")
                return auth_key

            logger.error("Session数据长度不足")
            return None

        except Exception as e:
            logger.error(f"Session转AuthKey失败: {str(e)}")
            return None

    @staticmethod
    def authkey_to_hex(auth_key: bytes) -> str:
        """
        AuthKey转十六进制字符串

        Args:
            auth_key: AuthKey字节数据

        Returns:
            十六进制字符串
        """
        return auth_key.hex()

    @staticmethod
    def hex_to_authkey(hex_string: str) -> bytes:
        """
        十六进制字符串转AuthKey

        Args:
            hex_string: 十六进制字符串

        Returns:
            AuthKey字节数据
        """
        return bytes.fromhex(hex_string)

    @staticmethod
    async def tdata_to_session(tdata_path: str, api_id: int, api_hash: str) -> Optional[str]:
        """
        TData转Session (需要opentele库)

        Args:
            tdata_path: TData目录路径
            api_id: API ID
            api_hash: API Hash

        Returns:
            Session字符串
        """
        try:
            # 注意: 需要安装 opentele 库
            # pip install opentele
            from opentele.api import API
            from opentele.td import TDesktop

            # 加载TData
            tdesk = TDesktop(tdata_path)
            assert tdesk.isLoaded()

            # 转换为Telethon
            client = await tdesk.ToTelethon(session="session", flag=API.TelegramDesktop)

            # 获取session字符串
            session_string = StringSession.save(client.session)

            logger.info("✅ TData转Session成功")
            return session_string

        except ImportError:
            logger.error("❌ 未安装opentele库，请运行: pip install opentele")
            return None
        except Exception as e:
            logger.error(f"TData转Session失败: {str(e)}")
            return None

    @staticmethod
    async def session_to_tdata(session_string: str, api_id: int, api_hash: str,
                               output_path: str = "output_tdata") -> bool:
        """
        Session转TData (需要opentele库)

        Args:
            session_string: Session字符串
            api_id: API ID
            api_hash: API Hash
            output_path: 输出TData目录路径

        Returns:
            是否成功
        """
        try:
            from opentele.td import TDesktop
            from opentele.tl import TelegramClient as OpenTeleClient

            # 创建Telethon客户端
            client = TelegramClient(StringSession(session_string), api_id, api_hash)
            await client.connect()

            # 转换为TData
            tdesk = await client.ToTDesktop(flag=TDesktop.Account)

            # 保存TData
            tdesk.SaveTData(output_path)

            logger.info(f"✅ Session转TData成功: {output_path}")
            return True

        except ImportError:
            logger.error("❌ 未安装opentele库，请运行: pip install opentele")
            return False
        except Exception as e:
            logger.error(f"Session转TData失败: {str(e)}")
            return False

    @staticmethod
    def save_to_file(data: Union[str, dict, bytes], output_path: str, format_type: str):
        """
        保存数据到文件

        Args:
            data: 要保存的数据
            output_path: 输出文件路径
            format_type: 格式类型 ('session', 'json', 'authkey')
        """
        try:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            if format_type == 'json':
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            elif format_type == 'authkey':
                with open(output_path, 'wb') as f:
                    f.write(data)
            else:  # session 或其他文本格式
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(str(data))

            logger.info(f"✅ 数据已保存: {output_path}")

        except Exception as e:
            logger.error(f"保存文件失败: {str(e)}")

    @staticmethod
    def load_from_file(file_path: str, format_type: str) -> Optional[Union[str, dict, bytes]]:
        """
        从文件加载数据

        Args:
            file_path: 文件路径
            format_type: 格式类型

        Returns:
            加载的数据
        """
        try:
            if format_type == 'json':
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            elif format_type == 'authkey':
                with open(file_path, 'rb') as f:
                    return f.read()
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read().strip()

        except Exception as e:
            logger.error(f"加载文件失败: {str(e)}")
            return None


class ConversionPipeline:
    """转换流水线 - 批量转换"""

    def __init__(self):
        self.converter = FormatConverter()

    async def batch_convert(
        self,
        input_files: list,
        input_format: str,
        output_format: str,
        output_dir: str = "converted",
        api_id: int = None,
        api_hash: str = None
    ) -> dict:
        """
        批量格式转换

        Args:
            input_files: 输入文件列表
            input_format: 输入格式 ('session', 'json', 'tdata', 'authkey')
            output_format: 输出格式
            output_dir: 输出目录
            api_id: API ID (某些转换需要)
            api_hash: API Hash (某些转换需要)

        Returns:
            转换结果统计
        """
        stats = {
            "total": len(input_files),
            "success": 0,
            "failed": 0,
            "errors": []
        }

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        for input_file in input_files:
            try:
                # 加载输入数据
                input_data = self.converter.load_from_file(input_file, input_format)
                if not input_data:
                    stats["failed"] += 1
                    stats["errors"].append(f"{input_file}: 加载失败")
                    continue

                # 执行转换
                output_data = None
                output_filename = Path(input_file).stem

                if input_format == 'session' and output_format == 'json':
                    output_data = self.converter.session_to_json(input_data, api_id, api_hash)
                    output_file = f"{output_dir}/{output_filename}.json"

                elif input_format == 'json' and output_format == 'session':
                    output_data = self.converter.json_to_session(input_data)
                    output_file = f"{output_dir}/{output_filename}.session"

                elif input_format == 'session' and output_format == 'authkey':
                    output_data = self.converter.session_to_authkey(input_data)
                    output_file = f"{output_dir}/{output_filename}.key"

                elif input_format == 'tdata' and output_format == 'session':
                    output_data = await self.converter.tdata_to_session(input_data, api_id, api_hash)
                    output_file = f"{output_dir}/{output_filename}.session"

                elif input_format == 'session' and output_format == 'tdata':
                    success = await self.converter.session_to_tdata(
                        input_data, api_id, api_hash,
                        f"{output_dir}/{output_filename}_tdata"
                    )
                    if success:
                        stats["success"] += 1
                    else:
                        stats["failed"] += 1
                    continue

                else:
                    stats["failed"] += 1
                    stats["errors"].append(f"{input_file}: 不支持的转换 {input_format} -> {output_format}")
                    continue

                # 保存输出数据
                if output_data:
                    self.converter.save_to_file(output_data, output_file, output_format)
                    stats["success"] += 1

                    # 记录转换日志到数据库
                    db.execute(
                        """
                        INSERT INTO conversion_logs
                        (input_format, output_format, input_file, output_file, status)
                        VALUES (?, ?, ?, ?, 'success')
                        """,
                        (input_format, output_format, input_file, output_file)
                    )
                else:
                    stats["failed"] += 1
                    stats["errors"].append(f"{input_file}: 转换失败")

            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append(f"{input_file}: {str(e)}")
                logger.error(f"转换失败 {input_file}: {str(e)}")

        return stats


# 全局实例
converter = FormatConverter()
conversion_pipeline = ConversionPipeline()


# 示例使用
async def example_usage():
    """示例：格式转换"""

    # 1. Session转JSON
    session_string = "YOUR_SESSION_STRING"
    api_id = 12345
    api_hash = "your_api_hash"

    json_data = converter.session_to_json(session_string, api_id, api_hash)
    print("Session转JSON:")
    print(json.dumps(json_data, indent=2))

    # 2. Session转AuthKey
    auth_key = converter.session_to_authkey(session_string)
    if auth_key:
        print(f"\nAuthKey (hex): {converter.authkey_to_hex(auth_key)[:64]}...")

    # 3. 批量转换
    input_files = ["session1.txt", "session2.txt"]
    stats = await conversion_pipeline.batch_convert(
        input_files=input_files,
        input_format="session",
        output_format="json",
        api_id=api_id,
        api_hash=api_hash
    )
    print(f"\n批量转换结果: {stats}")


if __name__ == "__main__":
    import asyncio

    # 初始化数据库
    db.initialize()

    # 运行示例
    asyncio.run(example_usage())
