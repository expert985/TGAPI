"""
加密和密钥生成工具
"""
import secrets
import string
import hashlib
import base64
from typing import Optional


def generate_api_token(length: int = 32) -> str:
    """
    生成API令牌

    Args:
        length: 令牌长度

    Returns:
        十六进制令牌字符串
    """
    return secrets.token_hex(length)


def generate_strong_password(length: int = 16) -> str:
    """
    生成强密码

    Args:
        length: 密码长度

    Returns:
        强密码字符串
    """
    alphabet = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password


def hash_password(password: str, salt: Optional[str] = None) -> tuple:
    """
    哈希密码

    Args:
        password: 明文密码
        salt: 盐值（可选）

    Returns:
        (哈希值, 盐值)
    """
    if not salt:
        salt = secrets.token_hex(16)

    pwd_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )

    return base64.b64encode(pwd_hash).decode('utf-8'), salt


def verify_password(password: str, hashed: str, salt: str) -> bool:
    """
    验证密码

    Args:
        password: 明文密码
        hashed: 哈希值
        salt: 盐值

    Returns:
        是否匹配
    """
    pwd_hash, _ = hash_password(password, salt)
    return pwd_hash == hashed


def encode_session_data(data: str) -> str:
    """
    编码会话数据

    Args:
        data: 原始数据

    Returns:
        Base64编码的数据
    """
    return base64.b64encode(data.encode('utf-8')).decode('utf-8')


def decode_session_data(encoded_data: str) -> str:
    """
    解码会话数据

    Args:
        encoded_data: Base64编码的数据

    Returns:
        原始数据
    """
    return base64.b64decode(encoded_data.encode('utf-8')).decode('utf-8')
