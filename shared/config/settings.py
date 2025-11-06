"""
配置管理模块
"""
import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class TelegramConfig:
    """Telegram配置"""
    bot_token: str
    api_id: Optional[int] = None
    api_hash: Optional[str] = None


@dataclass
class DatabaseConfig:
    """数据库配置"""
    path: str = "data/bot.db"
    backup_enabled: bool = True
    backup_interval_hours: int = 24


@dataclass
class TGAPIConfig:
    """TGAPI配置"""
    base_url: str = "http://localhost:3000/api"
    default_expire_hours: int = 24
    default_max_login: int = -1  # -1表示无限制
    enable_custom_copyright: bool = True


@dataclass
class ServerConfig:
    """服务器配置"""
    host: str = "0.0.0.0"
    port: int = 3000
    debug: bool = False


class Settings:
    """全局设置"""

    def __init__(self):
        self.telegram = TelegramConfig(
            bot_token=os.getenv("BOT_TOKEN", ""),
            api_id=int(os.getenv("API_ID", "0")) or None,
            api_hash=os.getenv("API_HASH", "") or None
        )

        self.database = DatabaseConfig(
            path=os.getenv("DATABASE_PATH", "data/bot.db")
        )

        self.tgapi = TGAPIConfig(
            base_url=os.getenv("TGAPI_BASE_URL", "http://localhost:3000/api")
        )

        self.server = ServerConfig(
            host=os.getenv("SERVER_HOST", "0.0.0.0"),
            port=int(os.getenv("SERVER_PORT", "3000")),
            debug=os.getenv("DEBUG", "false").lower() == "true"
        )

        # 管理员用户ID列表
        self.admin_user_ids = self._parse_admin_ids()

        # 项目根目录
        self.root_dir = Path(__file__).parent.parent.parent

        # 数据目录
        self.data_dir = self.root_dir / "data"
        self.sessions_dir = self.root_dir / "sessions"
        self.logs_dir = self.root_dir / "logs"

        # 确保目录存在
        self._ensure_dirs()

    def _parse_admin_ids(self):
        """解析管理员ID"""
        admin_ids_str = os.getenv("ADMIN_USER_IDS", "")
        if not admin_ids_str:
            return []

        try:
            return [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()]
        except ValueError:
            return []

    def _ensure_dirs(self):
        """确保必要的目录存在"""
        for dir_path in [self.data_dir, self.sessions_dir, self.logs_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

    def is_admin(self, user_id: int) -> bool:
        """检查是否为管理员"""
        return user_id in self.admin_user_ids

    def validate(self) -> tuple[bool, list[str]]:
        """
        验证配置

        Returns:
            (是否有效, 错误信息列表)
        """
        errors = []

        if not self.telegram.bot_token:
            errors.append("❌ BOT_TOKEN 未设置")

        if not self.telegram.api_id or not self.telegram.api_hash:
            errors.append("⚠️  API_ID 和 API_HASH 未设置（部分功能将不可用）")

        return len(errors) == 0, errors


# 全局配置实例
settings = Settings()


def load_env_file(env_file: str = ".env"):
    """
    加载环境变量文件

    Args:
        env_file: 环境变量文件路径
    """
    env_path = Path(env_file)
    if not env_path.exists():
        return

    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, _, value = line.partition('=')
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value:
                    os.environ[key] = value


if __name__ == "__main__":
    # 加载环境变量
    load_env_file()

    # 验证配置
    is_valid, errors = settings.validate()

    print("📋 配置检查:")
    if is_valid:
        print("✅ 所有必需配置已设置")
    else:
        for error in errors:
            print(error)

    print(f"\n📂 目录:")
    print(f"  数据目录: {settings.data_dir}")
    print(f"  会话目录: {settings.sessions_dir}")
    print(f"  日志目录: {settings.logs_dir}")
