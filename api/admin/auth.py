"""
管理员认证模块
"""
import secrets
import os
from datetime import datetime, timedelta
from typing import Optional, Dict
from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse
import hashlib

from shared.utils.logger import logger


class SessionManager:
    """会话管理器"""

    def __init__(self):
        self.sessions: Dict[str, Dict] = {}  # session_id -> {user_id, created_at, last_active}
        self.session_timeout = timedelta(hours=24)

    def create_session(self, user_id: str) -> str:
        """创建会话"""
        session_id = secrets.token_urlsafe(32)
        self.sessions[session_id] = {
            "user_id": user_id,
            "created_at": datetime.now(),
            "last_active": datetime.now()
        }
        logger.info(f"✅ 创建会话: {user_id} -> {session_id[:8]}...")
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict]:
        """获取会话"""
        if session_id not in self.sessions:
            return None

        session = self.sessions[session_id]

        # 检查超时
        if datetime.now() - session["last_active"] > self.session_timeout:
            del self.sessions[session_id]
            return None

        # 更新最后活动时间
        session["last_active"] = datetime.now()
        return session

    def delete_session(self, session_id: str):
        """删除会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"✅ 删除会话: {session_id[:8]}...")

    def cleanup_expired_sessions(self):
        """清理过期会话"""
        now = datetime.now()
        expired = [
            sid for sid, session in self.sessions.items()
            if now - session["last_active"] > self.session_timeout
        ]
        for sid in expired:
            del self.sessions[sid]
        if expired:
            logger.info(f"🧹 清理过期会话: {len(expired)}个")


# 全局会话管理器
session_manager = SessionManager()


class AdminAuth:
    """管理员认证"""

    @staticmethod
    def _get_admin_config():
        """从环境变量获取管理员配置"""
        username = os.getenv("ADMIN_USERNAME", "admin")
        password = os.getenv("ADMIN_PASSWORD", "admin123")

        return {
            "username": username,
            "password_hash": hashlib.sha256(password.encode()).hexdigest(),
            "role": "admin"
        }

    @staticmethod
    def hash_password(password: str) -> str:
        """哈希密码"""
        return hashlib.sha256(password.encode()).hexdigest()

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        return AdminAuth.hash_password(plain_password) == hashed_password

    @staticmethod
    def authenticate(username: str, password: str) -> tuple[bool, Optional[str]]:
        """
        认证用户

        Returns:
            (是否成功, 错误消息)
        """
        # 从环境变量获取管理员配置
        admin_config = AdminAuth._get_admin_config()

        if username != admin_config["username"]:
            return False, "用户名或密码错误"

        if not AdminAuth.verify_password(password, admin_config["password_hash"]):
            return False, "用户名或密码错误"

        return True, None

    @staticmethod
    def login(username: str, password: str) -> tuple[bool, Optional[str], Optional[str]]:
        """
        登录

        Returns:
            (是否成功, session_id或错误消息, 用户角色)
        """
        success, error = AdminAuth.authenticate(username, password)
        if not success:
            return False, error, None

        # 创建会话
        session_id = session_manager.create_session(username)
        admin_config = AdminAuth._get_admin_config()
        return True, session_id, admin_config["role"]

    @staticmethod
    def logout(session_id: str):
        """登出"""
        session_manager.delete_session(session_id)

    @staticmethod
    def get_current_user(request: Request) -> Optional[str]:
        """
        获取当前用户

        Returns:
            用户名 或 None
        """
        session_id = request.cookies.get("session_id")
        if not session_id:
            return None

        session = session_manager.get_session(session_id)
        if not session:
            return None

        return session["user_id"]

    @staticmethod
    def require_auth(request: Request):
        """
        要求认证（装饰器辅助函数）

        Raises:
            HTTPException: 如果未认证
        """
        user = AdminAuth.get_current_user(request)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未认证"
            )
        return user


# 定期清理过期会话
import asyncio

async def cleanup_sessions_periodically():
    """定期清理过期会话"""
    while True:
        await asyncio.sleep(3600)  # 每小时清理一次
        session_manager.cleanup_expired_sessions()


def start_session_cleanup():
    """启动会话清理任务"""
    asyncio.create_task(cleanup_sessions_periodically())
