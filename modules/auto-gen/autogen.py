"""
逆向自动做号工具 - 基于TGAPI反向生成账号
输入API ID + Hash，输出各种格式账号
"""
import asyncio
from typing import Optional, Tuple
from telethon import TelegramClient
from telethon.sessions import StringSession
from pathlib import Path

from shared.utils.logger import logger
from shared.database.init import db
from modules.converter.converter import FormatConverter


class AutoGenTool:
    """自动做号工具"""

    def __init__(self):
        self.converter = FormatConverter()

    async def generate_account(
        self,
        api_id: int,
        api_hash: str,
        phone: str,
        output_format: str = "session",
        output_dir: str = "generated",
        tenant_id: Optional[int] = None
    ) -> Tuple[bool, str, Optional[dict]]:
        """
        自动生成账号

        Args:
            api_id: Telegram API ID
            api_hash: Telegram API Hash
            phone: 手机号
            output_format: 输出格式 ('session', 'json', 'tdata', 'authkey')
            output_dir: 输出目录
            tenant_id: 租户ID

        Returns:
            (是否成功, 消息, 生成的数据)
        """
        try:
            logger.info(f"🔨 开始自动做号: {phone}")

            # 创建输出目录
            Path(output_dir).mkdir(parents=True, exist_ok=True)

            # 创建Telegram客户端
            session_name = f"{output_dir}/{phone}"
            client = TelegramClient(session_name, api_id, api_hash)

            # 连接并登录
            await client.connect()

            if not await client.is_user_authorized():
                logger.info(f"📱 发送验证码到: {phone}")
                await client.send_code_request(phone)

                # 这里需要用户输入验证码（实际使用时可以通过API获取）
                # 为了演示，这里返回等待验证码的状态
                return False, "等待验证码输入", {
                    "phone": phone,
                    "status": "waiting_code",
                    "session_file": session_name
                }

            # 获取session字符串
            session_string = StringSession.save(client.session)

            # 获取用户信息
            me = await client.get_me()

            result = {
                "phone": phone,
                "user_id": me.id,
                "username": me.username,
                "api_id": api_id,
                "api_hash": api_hash,
                "session_string": session_string
            }

            # 根据输出格式保存
            output_data = None
            output_file = None

            if output_format == "session":
                output_file = f"{output_dir}/{phone}.session"
                self.converter.save_to_file(session_string, output_file, "session")
                output_data = session_string

            elif output_format == "json":
                output_file = f"{output_dir}/{phone}.json"
                json_data = self.converter.session_to_json(session_string, api_id, api_hash)
                self.converter.save_to_file(json_data, output_file, "json")
                output_data = json_data

            elif output_format == "authkey":
                output_file = f"{output_dir}/{phone}.key"
                auth_key = self.converter.session_to_authkey(session_string)
                if auth_key:
                    self.converter.save_to_file(auth_key, output_file, "authkey")
                    output_data = self.converter.authkey_to_hex(auth_key)

            elif output_format == "tdata":
                output_path = f"{output_dir}/{phone}_tdata"
                success = await self.converter.session_to_tdata(
                    session_string, api_id, api_hash, output_path
                )
                if success:
                    output_file = output_path
                    output_data = {"tdata_path": output_path}

            # 保存到数据库
            if output_data:
                # 添加账号到数据库
                cursor = db.execute(
                    """
                    INSERT INTO accounts (phone, session_type, session_data, api_id, api_hash, tenant_id, status)
                    VALUES (?, ?, ?, ?, ?, ?, 'active')
                    """,
                    (phone, output_format, str(output_data), str(api_id), api_hash, tenant_id)
                )
                account_id = cursor.lastrowid

                # 记录生成日志
                db.execute(
                    """
                    INSERT INTO autogen_logs
                    (api_id, api_hash, output_format, output_path, phone, status)
                    VALUES (?, ?, ?, ?, ?, 'success')
                    """,
                    (str(api_id), api_hash, output_format, output_file, phone)
                )

                result["account_id"] = account_id
                result["output_file"] = output_file

            await client.disconnect()

            logger.info(f"✅ 账号生成成功: {phone}")
            return True, "账号生成成功", result

        except Exception as e:
            error_msg = f"账号生成失败: {str(e)}"
            logger.error(error_msg)

            # 记录失败日志
            db.execute(
                """
                INSERT INTO autogen_logs
                (api_id, api_hash, output_format, phone, status, error_message)
                VALUES (?, ?, ?, ?, 'failed', ?)
                """,
                (str(api_id), api_hash, output_format, phone, error_msg)
            )

            return False, error_msg, None

    async def complete_login(
        self,
        session_file: str,
        api_id: int,
        api_hash: str,
        phone: str,
        code: str,
        password: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        完成登录（输入验证码后）

        Args:
            session_file: Session文件路径
            api_id: API ID
            api_hash: API Hash
            phone: 手机号
            code: 验证码
            password: 两步验证密码（如果有）

        Returns:
            (是否成功, 消息)
        """
        try:
            # 加载已有的session
            client = TelegramClient(session_file, api_id, api_hash)
            await client.connect()

            # 使用验证码登录
            await client.sign_in(phone, code)

            # 如果需要两步验证
            if password:
                await client.sign_in(password=password)

            # 验证是否登录成功
            if await client.is_user_authorized():
                me = await client.get_me()
                logger.info(f"✅ 登录成功: {me.first_name} (@{me.username})")
                await client.disconnect()
                return True, "登录成功"
            else:
                await client.disconnect()
                return False, "登录失败"

        except Exception as e:
            error_msg = f"完成登录失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    async def batch_generate(
        self,
        accounts_data: list,
        output_format: str = "session",
        output_dir: str = "generated"
    ) -> dict:
        """
        批量生成账号

        Args:
            accounts_data: 账号数据列表，每项包含 {api_id, api_hash, phone}
            output_format: 输出格式
            output_dir: 输出目录

        Returns:
            统计信息
        """
        stats = {
            "total": len(accounts_data),
            "success": 0,
            "failed": 0,
            "waiting_code": 0,
            "results": []
        }

        for account_data in accounts_data:
            success, msg, result = await self.generate_account(
                api_id=account_data['api_id'],
                api_hash=account_data['api_hash'],
                phone=account_data['phone'],
                output_format=output_format,
                output_dir=output_dir
            )

            if success:
                stats["success"] += 1
            elif "等待验证码" in msg:
                stats["waiting_code"] += 1
            else:
                stats["failed"] += 1

            stats["results"].append({
                "phone": account_data['phone'],
                "success": success,
                "message": msg,
                "data": result
            })

        logger.info(f"📊 批量生成完成: {stats}")
        return stats


# 全局实例
autogen_tool = AutoGenTool()


# 示例使用
async def example_usage():
    """示例：自动做号"""

    # 单个账号生成
    api_id = 12345
    api_hash = "your_api_hash"
    phone = "+1234567890"

    success, msg, result = await autogen_tool.generate_account(
        api_id=api_id,
        api_hash=api_hash,
        phone=phone,
        output_format="session"
    )

    if success:
        print(f"✅ {msg}")
        print(f"结果: {result}")
    else:
        print(f"❌ {msg}")
        if result and result.get("status") == "waiting_code":
            # 等待验证码输入
            code = input("请输入验证码: ")
            success, msg = await autogen_tool.complete_login(
                session_file=result['session_file'],
                api_id=api_id,
                api_hash=api_hash,
                phone=phone,
                code=code
            )
            print(f"登录结果: {msg}")


if __name__ == "__main__":
    # 初始化数据库
    db.initialize()

    # 运行示例
    asyncio.run(example_usage())
