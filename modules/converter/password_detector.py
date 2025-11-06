"""
密码自动识别模块 - 从文件中自动识别2FA密码
"""
import json
from pathlib import Path
from typing import Optional, Dict, List

from shared.utils.logger import logger


class PasswordDetector:
    """密码自动识别器"""

    # 常见的密码文件名
    PASSWORD_FILES = [
        'password.txt',
        '2fa.txt',
        'twofa.txt',
        'pass.txt',
        'pwd.txt',
        'two_factor.txt',
        'two_step.txt'
    ]

    # JSON中可能包含密码的字段名
    PASSWORD_FIELDS = [
        'password',
        '2fa',
        'twofa',
        'two_fa',
        'two_factor',
        'pass',
        'pwd',
        'cloud_password'
    ]

    @staticmethod
    def detect_password(base_path: Path) -> Optional[str]:
        """
        自动检测并识别2FA密码

        Args:
            base_path: 基础路径（文件或目录）

        Returns:
            识别到的密码
        """
        if not isinstance(base_path, Path):
            base_path = Path(base_path)

        # 如果是文件，转为其所在目录
        if base_path.is_file():
            base_path = base_path.parent

        logger.info(f"🔍 开始密码自动识别: {base_path}")

        # 1. 优先检查JSON文件中的密码字段
        password = PasswordDetector._check_json_files(base_path)
        if password:
            logger.success(f"✅ 从JSON文件识别到密码")
            return password

        # 2. 检查常见的密码文本文件
        password = PasswordDetector._check_password_files(base_path)
        if password:
            logger.success(f"✅ 从密码文件识别到密码")
            return password

        # 3. 检查session文件同名的配置文件
        password = PasswordDetector._check_session_config(base_path)
        if password:
            logger.success(f"✅ 从session配置文件识别到密码")
            return password

        logger.warning("⚠️ 未能自动识别密码")
        return None

    @staticmethod
    def _check_json_files(base_path: Path) -> Optional[str]:
        """检查JSON文件中的密码字段"""
        json_files = list(base_path.glob('*.json'))

        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                    # 检查所有可能的密码字段
                    for field in PasswordDetector.PASSWORD_FIELDS:
                        if field in data and data[field]:
                            password = str(data[field]).strip()
                            if password:
                                logger.info(f"   找到密码字段: {json_file.name} -> {field}")
                                return password

            except Exception as e:
                logger.debug(f"   读取JSON文件失败 {json_file}: {str(e)}")
                continue

        return None

    @staticmethod
    def _check_password_files(base_path: Path) -> Optional[str]:
        """检查常见的密码文本文件"""
        for filename in PasswordDetector.PASSWORD_FILES:
            password_file = base_path / filename

            if password_file.exists() and password_file.is_file():
                try:
                    content = password_file.read_text(encoding='utf-8').strip()

                    # 跳过空文件
                    if not content:
                        continue

                    # 如果文件有多行，取第一行
                    lines = content.split('\n')
                    password = lines[0].strip()

                    if password:
                        logger.info(f"   找到密码文件: {filename}")
                        return password

                except Exception as e:
                    logger.debug(f"   读取密码文件失败 {filename}: {str(e)}")
                    continue

        return None

    @staticmethod
    def _check_session_config(base_path: Path) -> Optional[str]:
        """检查session文件对应的配置文件"""
        # 查找.session文件
        session_files = list(base_path.glob('*.session'))

        for session_file in session_files:
            # 检查同名的json配置文件
            json_config = session_file.with_suffix('.json')

            if json_config.exists():
                try:
                    with open(json_config, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                        for field in PasswordDetector.PASSWORD_FIELDS:
                            if field in data and data[field]:
                                password = str(data[field]).strip()
                                if password:
                                    logger.info(f"   找到session配置: {json_config.name} -> {field}")
                                    return password

                except Exception as e:
                    logger.debug(f"   读取session配置失败 {json_config}: {str(e)}")
                    continue

        return None

    @staticmethod
    def batch_detect_passwords(base_paths: List[Path]) -> Dict[Path, Optional[str]]:
        """
        批量检测密码

        Args:
            base_paths: 路径列表

        Returns:
            路径到密码的映射
        """
        results = {}

        for path in base_paths:
            password = PasswordDetector.detect_password(path)
            results[path] = password

        success_count = sum(1 for p in results.values() if p is not None)
        logger.info(f"📊 批量密码识别完成: {success_count}/{len(base_paths)}")

        return results

    @staticmethod
    def create_password_file(directory: Path, password: str, filename: str = 'password.txt'):
        """
        创建密码文件

        Args:
            directory: 目录路径
            password: 密码
            filename: 文件名
        """
        try:
            directory = Path(directory)
            directory.mkdir(parents=True, exist_ok=True)

            password_file = directory / filename
            password_file.write_text(password, encoding='utf-8')

            logger.info(f"✅ 密码文件已创建: {password_file}")

        except Exception as e:
            logger.error(f"创建密码文件失败: {str(e)}")


# 全局实例
password_detector = PasswordDetector()


# 示例使用
def example_usage():
    """示例：密码自动识别"""

    # 单个路径检测
    session_dir = Path("/path/to/sessions/account1")
    password = password_detector.detect_password(session_dir)

    if password:
        print(f"✅ 识别到密码: {password}")
    else:
        print("❌ 未识别到密码")

    # 批量检测
    directories = [
        Path("/path/to/sessions/account1"),
        Path("/path/to/sessions/account2"),
        Path("/path/to/sessions/account3"),
    ]

    results = password_detector.batch_detect_passwords(directories)

    for path, pwd in results.items():
        if pwd:
            print(f"✅ {path.name}: {pwd}")
        else:
            print(f"❌ {path.name}: 未找到密码")


if __name__ == "__main__":
    example_usage()
