"""
用户授权管理模块
"""
from datetime import datetime, timedelta
from typing import Optional, Tuple
from shared.database.init import db
from shared.utils.logger import logger


class AuthorizationManager:
    """用户授权管理器"""

    # 时长类型到天数的映射
    DURATION_MAP = {
        '1month': 30,
        '3months': 90,
        '6months': 180,
        '1year': 365,
        'permanent': None  # 永久
    }

    # 时长类型显示名称
    DURATION_NAMES = {
        '1month': '1个月',
        '3months': '3个月',
        '6months': '6个月',
        '1year': '1年',
        'permanent': '永久'
    }

    @staticmethod
    def check_authorization(telegram_id: int) -> Tuple[bool, str, Optional[dict]]:
        """
        检查用户是否有授权

        Args:
            telegram_id: Telegram用户ID

        Returns:
            (是否授权, 消息, 用户信息)
        """
        try:
            # 查询用户
            user = db.fetchone(
                "SELECT * FROM authorized_users WHERE telegram_id = ?",
                (telegram_id,)
            )

            if not user:
                return False, "您还没有授权使用本机器人，请联系管理员获取授权", None

            user_dict = dict(user)

            # 检查状态
            if user_dict['status'] == 'suspended':
                return False, "您的授权已被暂停，请联系管理员", None

            # 检查过期时间
            if user_dict['expire_date']:
                expire_date = datetime.fromisoformat(user_dict['expire_date'])
                if datetime.now() > expire_date:
                    # 自动更新状态为过期
                    db.execute(
                        "UPDATE authorized_users SET status = 'expired' WHERE telegram_id = ?",
                        (telegram_id,)
                    )
                    return False, f"您的授权已于 {user_dict['expire_date']} 过期，请联系管理员续费", None

            # 更新最后活跃时间
            db.execute(
                "UPDATE authorized_users SET last_active = ? WHERE telegram_id = ?",
                (datetime.now().isoformat(), telegram_id)
            )

            return True, "授权有效", user_dict

        except Exception as e:
            logger.error(f"检查授权失败: {str(e)}")
            return False, "系统错误，请稍后再试", None

    @staticmethod
    def authorize_user(
        telegram_id: int,
        duration_type: str,
        username: str = None,
        full_name: str = None,
        authorization_level: str = 'basic',
        max_accounts: int = 10,
        max_tgapi_sessions: int = 5,
        authorized_by: str = 'admin',
        payment_info: str = None,
        notes: str = None
    ) -> Tuple[bool, str]:
        """
        授权用户

        Args:
            telegram_id: Telegram用户ID
            duration_type: 时长类型 (1month, 3months, 6months, 1year, permanent)
            username: TG用户名
            full_name: 用户全名
            authorization_level: 授权等级
            max_accounts: 最大账号数
            max_tgapi_sessions: 最大TGAPI会话数
            authorized_by: 授权管理员
            payment_info: 付款信息
            notes: 备注

        Returns:
            (是否成功, 消息)
        """
        try:
            # 检查时长类型
            if duration_type not in AuthorizationManager.DURATION_MAP:
                return False, f"无效的时长类型: {duration_type}"

            # 计算过期时间
            expire_date = None
            days = AuthorizationManager.DURATION_MAP[duration_type]
            if days is not None:
                expire_date = (datetime.now() + timedelta(days=days)).isoformat()

            # 检查用户是否已存在
            existing = db.fetchone(
                "SELECT id FROM authorized_users WHERE telegram_id = ?",
                (telegram_id,)
            )

            if existing:
                # 更新现有用户
                db.execute("""
                    UPDATE authorized_users
                    SET username = ?,
                        full_name = ?,
                        authorization_level = ?,
                        authorized_by = ?,
                        authorization_date = ?,
                        expire_date = ?,
                        duration_type = ?,
                        max_accounts = ?,
                        max_tgapi_sessions = ?,
                        status = 'active',
                        payment_info = ?,
                        notes = ?,
                        updated_at = ?
                    WHERE telegram_id = ?
                """, (
                    username, full_name, authorization_level, authorized_by,
                    datetime.now().isoformat(), expire_date, duration_type,
                    max_accounts, max_tgapi_sessions,
                    payment_info, notes,
                    datetime.now().isoformat(),
                    telegram_id
                ))
                action = "renew"
                message = f"用户 {telegram_id} 授权已续期"
            else:
                # 创建新用户
                db.execute("""
                    INSERT INTO authorized_users (
                        telegram_id, username, full_name, authorization_level,
                        authorized_by, authorization_date, expire_date, duration_type,
                        max_accounts, max_tgapi_sessions, status,
                        payment_info, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    telegram_id, username, full_name, authorization_level,
                    authorized_by, datetime.now().isoformat(), expire_date, duration_type,
                    max_accounts, max_tgapi_sessions, 'active',
                    payment_info, notes
                ))
                action = "authorize"
                message = f"用户 {telegram_id} 授权成功"

            # 记录授权日志
            db.execute("""
                INSERT INTO authorization_logs (
                    telegram_id, action, duration_type, expire_date,
                    operated_by, notes
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                telegram_id, action, duration_type, expire_date,
                authorized_by, notes
            ))

            duration_name = AuthorizationManager.DURATION_NAMES[duration_type]
            logger.info(f"✅ {message}，时长：{duration_name}")

            return True, f"{message}，时长：{duration_name}"

        except Exception as e:
            logger.error(f"授权用户失败: {str(e)}")
            return False, f"授权失败: {str(e)}"

    @staticmethod
    def suspend_user(telegram_id: int, operated_by: str = 'admin', notes: str = None) -> Tuple[bool, str]:
        """
        暂停用户授权

        Args:
            telegram_id: Telegram用户ID
            operated_by: 操作管理员
            notes: 备注

        Returns:
            (是否成功, 消息)
        """
        try:
            db.execute(
                "UPDATE authorized_users SET status = 'suspended', updated_at = ? WHERE telegram_id = ?",
                (datetime.now().isoformat(), telegram_id)
            )

            # 记录日志
            db.execute("""
                INSERT INTO authorization_logs (
                    telegram_id, action, operated_by, notes
                ) VALUES (?, ?, ?, ?)
            """, (telegram_id, 'suspend', operated_by, notes))

            logger.info(f"✅ 用户 {telegram_id} 授权已暂停")
            return True, f"用户 {telegram_id} 授权已暂停"

        except Exception as e:
            logger.error(f"暂停用户授权失败: {str(e)}")
            return False, f"暂停失败: {str(e)}"

    @staticmethod
    def activate_user(telegram_id: int, operated_by: str = 'admin', notes: str = None) -> Tuple[bool, str]:
        """
        激活用户授权

        Args:
            telegram_id: Telegram用户ID
            operated_by: 操作管理员
            notes: 备注

        Returns:
            (是否成功, 消息)
        """
        try:
            db.execute(
                "UPDATE authorized_users SET status = 'active', updated_at = ? WHERE telegram_id = ?",
                (datetime.now().isoformat(), telegram_id)
            )

            # 记录日志
            db.execute("""
                INSERT INTO authorization_logs (
                    telegram_id, action, operated_by, notes
                ) VALUES (?, ?, ?, ?)
            """, (telegram_id, 'activate', operated_by, notes))

            logger.info(f"✅ 用户 {telegram_id} 授权已激活")
            return True, f"用户 {telegram_id} 授权已激活"

        except Exception as e:
            logger.error(f"激活用户授权失败: {str(e)}")
            return False, f"激活失败: {str(e)}"

    @staticmethod
    def log_unauthorized_access(
        telegram_id: int,
        username: str = None,
        full_name: str = None,
        command: str = None,
        message: str = None
    ):
        """
        记录未授权访问日志

        Args:
            telegram_id: Telegram用户ID
            username: TG用户名
            full_name: 用户全名
            command: 尝试的命令
            message: 消息内容
        """
        try:
            db.execute("""
                INSERT INTO unauthorized_access_logs (
                    telegram_id, username, full_name, command, message
                ) VALUES (?, ?, ?, ?, ?)
            """, (telegram_id, username, full_name, command, message))

            logger.warning(f"⚠️ 未授权访问: TG用户 {telegram_id} ({username}) 尝试使用命令 {command}")

        except Exception as e:
            logger.error(f"记录未授权访问失败: {str(e)}")

    @staticmethod
    def get_user_info(telegram_id: int) -> Optional[dict]:
        """
        获取用户信息

        Args:
            telegram_id: Telegram用户ID

        Returns:
            用户信息字典或None
        """
        try:
            user = db.fetchone(
                "SELECT * FROM authorized_users WHERE telegram_id = ?",
                (telegram_id,)
            )
            return dict(user) if user else None

        except Exception as e:
            logger.error(f"获取用户信息失败: {str(e)}")
            return None

    @staticmethod
    def get_all_users(status: str = None) -> list:
        """
        获取所有用户

        Args:
            status: 状态筛选 (active, expired, suspended)

        Returns:
            用户列表
        """
        try:
            if status:
                users = db.fetchall(
                    "SELECT * FROM authorized_users WHERE status = ? ORDER BY created_at DESC",
                    (status,)
                )
            else:
                users = db.fetchall(
                    "SELECT * FROM authorized_users ORDER BY created_at DESC"
                )

            return [dict(user) for user in users] if users else []

        except Exception as e:
            logger.error(f"获取用户列表失败: {str(e)}")
            return []

    @staticmethod
    def check_expired_users():
        """检查并更新过期用户"""
        try:
            db.execute("""
                UPDATE authorized_users
                SET status = 'expired'
                WHERE expire_date IS NOT NULL
                  AND expire_date < ?
                  AND status = 'active'
            """, (datetime.now().isoformat(),))

            logger.info("✅ 已更新过期用户状态")

        except Exception as e:
            logger.error(f"检查过期用户失败: {str(e)}")


# 全局授权管理器实例
auth_manager = AuthorizationManager()
