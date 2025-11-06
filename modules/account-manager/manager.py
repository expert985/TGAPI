"""
账号全功能处理模块 - 防找回、筛活、清理、维护
"""
import asyncio
from datetime import datetime
from typing import Optional, List, Dict
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneNumberBannedError

from shared.database.init import db
from shared.utils.logger import logger
from shared.utils.crypto import generate_strong_password


class AccountManager:
    """账号全功能管理器"""

    def __init__(self):
        self.clients: Dict[int, TelegramClient] = {}

    async def _get_client(self, account_id: int) -> Optional[TelegramClient]:
        """
        获取或创建Telegram客户端

        Args:
            account_id: 账号ID

        Returns:
            TelegramClient实例
        """
        try:
            # 如果客户端已存在，直接返回
            if account_id in self.clients:
                return self.clients[account_id]

            # 从数据库获取账号信息
            account = db.get_account(account_id)
            if not account:
                logger.error(f"账号不存在: {account_id}")
                return None

            # 创建客户端
            if account['session_type'] == 'session':
                client = TelegramClient(
                    StringSession(account['session_data']),
                    int(account['api_id']),
                    account['api_hash']
                )
                await client.connect()
                self.clients[account_id] = client
                return client

            # 其他类型需要先转换
            logger.error(f"不支持的session类型: {account['session_type']}")
            return None

        except Exception as e:
            logger.error(f"获取客户端失败: {str(e)}")
            return None

    async def protect_account(
        self,
        account_id: int,
        set_password: bool = True,
        enable_2fa: bool = True,
        bind_email: Optional[str] = None
    ) -> tuple[bool, str, Optional[dict]]:
        """
        账号防找回设置

        Args:
            account_id: 账号ID
            set_password: 是否设置密码
            enable_2fa: 是否启用2FA
            bind_email: 绑定邮箱

        Returns:
            (是否成功, 消息, 凭证信息)
        """
        try:
            client = await self._get_client(account_id)
            if not client:
                return False, "无法连接到账号", None

            credentials = {}

            # 1. 设置强密码
            if set_password:
                new_password = generate_strong_password(16)
                try:
                    # 检查是否已有密码
                    try:
                        await client.edit_2fa(new_password=new_password)
                        credentials['password'] = new_password
                        logger.info(f"✅ 密码设置成功: {account_id}")
                    except SessionPasswordNeededError:
                        # 已有密码，需要旧密码才能修改
                        logger.warning(f"账号已设置密码，需要旧密码才能修改: {account_id}")
                except Exception as e:
                    logger.error(f"设置密码失败: {str(e)}")

            # 2. 启用2FA
            if enable_2fa:
                try:
                    # 获取2FA设置
                    result = await client.edit_2fa(
                        new_password=credentials.get('password'),
                        hint="Account Security"
                    )
                    if result:
                        credentials['2fa_enabled'] = True
                        logger.info(f"✅ 2FA启用成功: {account_id}")
                except Exception as e:
                    logger.error(f"启用2FA失败: {str(e)}")

            # 3. 绑定邮箱
            if bind_email:
                try:
                    # Telethon不直接支持邮箱绑定，需要通过其他方式
                    credentials['email'] = bind_email
                    logger.info(f"✅ 邮箱记录: {bind_email}")
                except Exception as e:
                    logger.error(f"绑定邮箱失败: {str(e)}")

            # 保存凭证到数据库
            db.execute(
                """
                UPDATE accounts
                SET password = ?, email = ?, two_fa_secret = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    credentials.get('password'),
                    credentials.get('email'),
                    str(credentials.get('2fa_enabled', False)),
                    datetime.now(),
                    account_id
                )
            )

            # 记录操作日志
            db.log_operation(
                account_id=account_id,
                operation='protect',
                details=f"密码: {set_password}, 2FA: {enable_2fa}, 邮箱: {bind_email}",
                result='success'
            )

            return True, "防找回设置完成", credentials

        except Exception as e:
            error_msg = f"防找回设置失败: {str(e)}"
            logger.error(error_msg)
            db.log_operation(
                account_id=account_id,
                operation='protect',
                details="",
                result='failed',
                error_message=error_msg
            )
            return False, error_msg, None

    async def check_account_status(self, account_id: int) -> tuple[bool, str, str]:
        """
        筛活 - 检查账号状态

        Args:
            account_id: 账号ID

        Returns:
            (是否成功, 状态, 详细信息)
        """
        try:
            client = await self._get_client(account_id)
            if not client:
                status = "unknown"
                db.update_account_status(account_id, status)
                return False, status, "无法连接"

            # 检查是否能正常连接
            if not await client.is_user_authorized():
                status = "expired"
                db.update_account_status(account_id, status)
                return False, status, "会话已过期"

            # 获取账号信息
            me = await client.get_me()

            # 检查是否被封禁
            try:
                dialogs = await client.get_dialogs(limit=1)
                status = "active"
            except PhoneNumberBannedError:
                status = "banned"
                db.update_account_status(account_id, status)
                return False, status, "账号已被封禁"

            # 更新数据库状态
            db.update_account_status(account_id, status)

            # 记录日志
            db.log_operation(
                account_id=account_id,
                operation='check',
                details=f"用户ID: {me.id}, 用户名: {me.username}",
                result='success'
            )

            info = {
                "status": status,
                "user_id": me.id,
                "username": me.username,
                "phone": me.phone,
                "first_name": me.first_name,
                "last_name": me.last_name
            }

            return True, status, str(info)

        except Exception as e:
            error_msg = f"检查账号状态失败: {str(e)}"
            logger.error(error_msg)
            db.update_account_status(account_id, "unknown")
            db.log_operation(
                account_id=account_id,
                operation='check',
                details="",
                result='failed',
                error_message=error_msg
            )
            return False, "unknown", error_msg

    async def clean_account(
        self,
        account_id: int,
        clear_chats: bool = True,
        leave_groups: bool = False,
        delete_contacts: bool = False
    ) -> tuple[bool, str, dict]:
        """
        账号清理

        Args:
            account_id: 账号ID
            clear_chats: 是否清除聊天记录
            leave_groups: 是否退出群组
            delete_contacts: 是否删除联系人

        Returns:
            (是否成功, 消息, 统计信息)
        """
        try:
            client = await self._get_client(account_id)
            if not client:
                return False, "无法连接到账号", {}

            stats = {
                "cleared_chats": 0,
                "left_groups": 0,
                "deleted_contacts": 0
            }

            # 1. 清除聊天记录
            if clear_chats:
                try:
                    dialogs = await client.get_dialogs()
                    for dialog in dialogs:
                        if not dialog.is_group and not dialog.is_channel:
                            await client.delete_dialog(dialog)
                            stats["cleared_chats"] += 1
                    logger.info(f"✅ 已清除 {stats['cleared_chats']} 个聊天")
                except Exception as e:
                    logger.error(f"清除聊天失败: {str(e)}")

            # 2. 退出群组
            if leave_groups:
                try:
                    dialogs = await client.get_dialogs()
                    for dialog in dialogs:
                        if dialog.is_group:
                            await client.delete_dialog(dialog)
                            stats["left_groups"] += 1
                    logger.info(f"✅ 已退出 {stats['left_groups']} 个群组")
                except Exception as e:
                    logger.error(f"退出群组失败: {str(e)}")

            # 3. 删除联系人
            if delete_contacts:
                try:
                    contacts = await client.get_contacts()
                    for contact in contacts:
                        await client.delete_contacts(contact)
                        stats["deleted_contacts"] += 1
                    logger.info(f"✅ 已删除 {stats['deleted_contacts']} 个联系人")
                except Exception as e:
                    logger.error(f"删除联系人失败: {str(e)}")

            # 记录日志
            db.log_operation(
                account_id=account_id,
                operation='clean',
                details=str(stats),
                result='success'
            )

            return True, "清理完成", stats

        except Exception as e:
            error_msg = f"账号清理失败: {str(e)}"
            logger.error(error_msg)
            db.log_operation(
                account_id=account_id,
                operation='clean',
                details="",
                result='failed',
                error_message=error_msg
            )
            return False, error_msg, {}

    async def maintain_account(self, account_id: int) -> tuple[bool, str]:
        """
        账号维护（保活）

        Args:
            account_id: 账号ID

        Returns:
            (是否成功, 消息)
        """
        try:
            client = await self._get_client(account_id)
            if not client:
                return False, "无法连接到账号"

            # 执行保活操作
            # 1. 更新在线状态
            await client.get_me()

            # 2. 获取对话列表（模拟活跃）
            await client.get_dialogs(limit=5)

            # 记录日志
            db.log_operation(
                account_id=account_id,
                operation='maintain',
                details="保活操作完成",
                result='success'
            )

            logger.info(f"✅ 账号保活完成: {account_id}")
            return True, "保活成功"

        except Exception as e:
            error_msg = f"账号维护失败: {str(e)}"
            logger.error(error_msg)
            db.log_operation(
                account_id=account_id,
                operation='maintain',
                details="",
                result='failed',
                error_message=error_msg
            )
            return False, error_msg

    async def batch_check_accounts(self, account_ids: List[int]) -> Dict[int, str]:
        """
        批量筛活

        Args:
            account_ids: 账号ID列表

        Returns:
            账号ID到状态的映射
        """
        results = {}

        tasks = [self.check_account_status(aid) for aid in account_ids]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        for account_id, response in zip(account_ids, responses):
            if isinstance(response, Exception):
                results[account_id] = "error"
            else:
                _, status, _ = response
                results[account_id] = status

        return results


# 全局实例
account_manager = AccountManager()


# 示例使用
async def example_usage():
    """示例：账号管理操作"""

    # 假设账号ID
    account_id = 1

    # 1. 筛活
    print("📊 检查账号状态...")
    success, status, info = await account_manager.check_account_status(account_id)
    print(f"状态: {status}")
    print(f"信息: {info}")

    # 2. 防找回
    print("\n🔒 设置防找回...")
    success, msg, credentials = await account_manager.protect_account(
        account_id=account_id,
        set_password=True,
        enable_2fa=True
    )
    print(f"结果: {msg}")
    if credentials:
        print(f"凭证: {credentials}")

    # 3. 清理
    print("\n🧹 清理账号...")
    success, msg, stats = await account_manager.clean_account(
        account_id=account_id,
        clear_chats=True,
        leave_groups=False
    )
    print(f"结果: {msg}")
    print(f"统计: {stats}")

    # 4. 保活
    print("\n💚 账号保活...")
    success, msg = await account_manager.maintain_account(account_id)
    print(f"结果: {msg}")


if __name__ == "__main__":
    # 初始化数据库
    db.initialize()

    # 运行示例
    asyncio.run(example_usage())
