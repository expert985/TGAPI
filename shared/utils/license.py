"""
许可证管理和反盗版模块
"""
import hashlib
import uuid
import platform
import subprocess
from datetime import datetime, timedelta
from typing import Optional, Tuple
import json


class LicenseManager:
    """许可证管理器"""

    def __init__(self, db):
        self.db = db

    def generate_license_key(self, tenant_code: str, license_type: str) -> str:
        """
        生成许可证密钥

        Args:
            tenant_code: 租户代码
            license_type: 许可证类型

        Returns:
            许可证密钥
        """
        # 使用租户代码+类型+时间戳+随机数生成唯一密钥
        raw_data = f"{tenant_code}:{license_type}:{datetime.now().isoformat()}:{uuid.uuid4()}"
        hash_value = hashlib.sha256(raw_data.encode()).hexdigest()

        # 格式化为友好格式: XXXX-XXXX-XXXX-XXXX
        key_parts = [hash_value[i:i+4].upper() for i in range(0, 16, 4)]
        return "-".join(key_parts)

    def get_machine_id(self) -> str:
        """
        获取机器唯一标识（用于硬件绑定）

        Returns:
            机器ID
        """
        try:
            # 尝试多种方式获取唯一标识
            identifiers = []

            # 1. MAC地址
            mac = hex(uuid.getnode())[2:]
            identifiers.append(mac)

            # 2. 主板序列号（Linux）
            try:
                if platform.system() == "Linux":
                    result = subprocess.run(
                        ["cat", "/sys/class/dmi/id/product_uuid"],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    if result.returncode == 0:
                        identifiers.append(result.stdout.strip())
            except:
                pass

            # 3. 系统信息
            identifiers.append(platform.machine())
            identifiers.append(platform.system())

            # 组合并哈希
            combined = ":".join(identifiers)
            machine_id = hashlib.md5(combined.encode()).hexdigest()

            return machine_id

        except Exception as e:
            # 如果获取失败，使用UUID（每次运行都会变化，不推荐）
            return str(uuid.uuid4())

    def get_device_info(self) -> dict:
        """
        获取设备详细信息

        Returns:
            设备信息字典
        """
        return {
            "platform": platform.platform(),
            "system": platform.system(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "hostname": platform.node()
        }

    def create_tenant(self, tenant_code: str, tenant_name: str,
                     license_type: str, contact_info: str = None,
                     max_accounts: int = 10, max_tgapi_sessions: int = 5,
                     features: list = None) -> Tuple[bool, str, Optional[int]]:
        """
        创建租户

        Args:
            tenant_code: 租户代码
            tenant_name: 租户名称
            license_type: 许可证类型 ('trial', 'monthly', 'yearly', 'lifetime')
            contact_info: 联系信息
            max_accounts: 最大账号数
            max_tgapi_sessions: 最大TGAPI会话数
            features: 功能列表

        Returns:
            (是否成功, 许可证密钥或错误信息, 租户ID)
        """
        try:
            # 生成许可证密钥
            license_key = self.generate_license_key(tenant_code, license_type)

            # 计算过期时间
            expire_at = None
            if license_type == 'trial':
                expire_at = datetime.now() + timedelta(days=7)
            elif license_type == 'monthly':
                expire_at = datetime.now() + timedelta(days=30)
            elif license_type == 'yearly':
                expire_at = datetime.now() + timedelta(days=365)
            # lifetime不设置过期时间

            # 功能列表转JSON
            features_json = json.dumps(features or [
                "tgapi", "account_manager", "converter", "autogen"
            ])

            # 插入数据库
            query = """
                INSERT INTO tenants
                (tenant_code, tenant_name, contact_info, license_key, license_type,
                 expire_at, max_accounts, max_tgapi_sessions, features, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
            """

            cursor = self.db.execute(query, (
                tenant_code, tenant_name, contact_info, license_key, license_type,
                expire_at, max_accounts, max_tgapi_sessions, features_json
            ))

            tenant_id = cursor.lastrowid

            return True, license_key, tenant_id

        except Exception as e:
            return False, str(e), None

    def validate_license(self, license_key: str, machine_id: str = None,
                        ip_address: str = None) -> Tuple[bool, str, Optional[dict]]:
        """
        验证许可证

        Args:
            license_key: 许可证密钥
            machine_id: 机器ID（可选，如果不提供则自动获取）
            ip_address: IP地址

        Returns:
            (是否有效, 错误信息, 租户信息)
        """
        try:
            # 获取机器ID
            if not machine_id:
                machine_id = self.get_machine_id()

            # 查询租户
            query = "SELECT * FROM tenants WHERE license_key = ?"
            tenant = self.db.fetchone(query, (license_key,))

            if not tenant:
                self._log_validation(None, machine_id, ip_address, "failed", "许可证不存在")
                return False, "许可证无效", None

            tenant_id = tenant['id']

            # 检查状态
            if tenant['status'] != 'active':
                self._log_validation(tenant_id, machine_id, ip_address, "failed", "租户已停用")
                return False, f"租户状态: {tenant['status']}", None

            # 检查过期时间
            if tenant['expire_at']:
                expire_at = datetime.fromisoformat(tenant['expire_at'])
                if datetime.now() > expire_at:
                    # 更新租户状态为已过期
                    self.db.execute(
                        "UPDATE tenants SET status = 'expired' WHERE id = ?",
                        (tenant_id,)
                    )
                    self._log_validation(tenant_id, machine_id, ip_address, "expired", "许可证已过期")
                    return False, "许可证已过期", None

            # 检查设备绑定（反盗版）
            device_check = self._check_device_binding(tenant_id, machine_id)
            if not device_check[0]:
                self._log_validation(tenant_id, machine_id, ip_address, "failed", device_check[1])
                return False, device_check[1], None

            # 更新设备活跃时间
            self._update_device_active_time(tenant_id, machine_id)

            # 记录成功验证
            self._log_validation(tenant_id, machine_id, ip_address, "success", None)

            # 返回租户信息
            tenant_info = {
                "tenant_id": tenant['id'],
                "tenant_code": tenant['tenant_code'],
                "tenant_name": tenant['tenant_name'],
                "license_type": tenant['license_type'],
                "expire_at": tenant['expire_at'],
                "max_accounts": tenant['max_accounts'],
                "max_tgapi_sessions": tenant['max_tgapi_sessions'],
                "features": json.loads(tenant['features'])
            }

            return True, "验证成功", tenant_info

        except Exception as e:
            return False, f"验证错误: {str(e)}", None

    def _check_device_binding(self, tenant_id: int, machine_id: str,
                             max_devices: int = 3) -> Tuple[bool, str]:
        """
        检查设备绑定（反盗版核心）

        Args:
            tenant_id: 租户ID
            machine_id: 机器ID
            max_devices: 最大允许绑定设备数

        Returns:
            (是否允许, 错误信息)
        """
        try:
            # 查询当前设备
            query = """
                SELECT * FROM license_devices
                WHERE tenant_id = ? AND machine_id = ? AND status = 'active'
            """
            device = self.db.fetchone(query, (tenant_id, machine_id))

            if device:
                # 设备已绑定，允许使用
                return True, "设备已授权"

            # 检查已绑定设备数量
            query = """
                SELECT COUNT(*) as count FROM license_devices
                WHERE tenant_id = ? AND status = 'active'
            """
            result = self.db.fetchone(query, (tenant_id,))
            active_devices = result['count'] if result else 0

            if active_devices >= max_devices:
                return False, f"已达到最大设备数限制({max_devices}台)"

            # 绑定新设备
            device_info = json.dumps(self.get_device_info())
            query = """
                INSERT INTO license_devices
                (tenant_id, machine_id, device_info, status)
                VALUES (?, ?, ?, 'active')
            """
            self.db.execute(query, (tenant_id, machine_id, device_info))

            return True, "新设备已绑定"

        except Exception as e:
            return False, f"设备检查错误: {str(e)}"

    def _update_device_active_time(self, tenant_id: int, machine_id: str):
        """更新设备最后活跃时间"""
        query = """
            UPDATE license_devices
            SET last_active_time = ?, bind_count = bind_count + 1
            WHERE tenant_id = ? AND machine_id = ?
        """
        self.db.execute(query, (datetime.now(), tenant_id, machine_id))

    def _log_validation(self, tenant_id: Optional[int], machine_id: str,
                       ip_address: Optional[str], status: str, error_message: Optional[str]):
        """记录验证日志"""
        query = """
            INSERT INTO license_validations
            (tenant_id, machine_id, ip_address, status, error_message)
            VALUES (?, ?, ?, ?, ?)
        """
        self.db.execute(query, (tenant_id, machine_id, ip_address, status, error_message))

    def revoke_device(self, tenant_id: int, machine_id: str) -> Tuple[bool, str]:
        """
        撤销设备授权

        Args:
            tenant_id: 租户ID
            machine_id: 机器ID

        Returns:
            (是否成功, 消息)
        """
        try:
            query = """
                UPDATE license_devices
                SET status = 'revoked'
                WHERE tenant_id = ? AND machine_id = ?
            """
            cursor = self.db.execute(query, (tenant_id, machine_id))

            if cursor.rowcount > 0:
                return True, "设备授权已撤销"
            else:
                return False, "设备不存在或已撤销"

        except Exception as e:
            return False, f"撤销失败: {str(e)}"

    def get_tenant_stats(self, tenant_id: int) -> dict:
        """
        获取租户统计信息

        Args:
            tenant_id: 租户ID

        Returns:
            统计信息字典
        """
        stats = {}

        # 账号数量
        result = self.db.fetchone(
            "SELECT COUNT(*) as count FROM accounts WHERE tenant_id = ?",
            (tenant_id,)
        )
        stats['accounts_count'] = result['count'] if result else 0

        # TGAPI会话数量
        result = self.db.fetchone(
            "SELECT COUNT(*) as count FROM tgapi_sessions WHERE tenant_id = ? AND status = 'active'",
            (tenant_id,)
        )
        stats['tgapi_sessions_count'] = result['count'] if result else 0

        # 绑定设备数量
        result = self.db.fetchone(
            "SELECT COUNT(*) as count FROM license_devices WHERE tenant_id = ? AND status = 'active'",
            (tenant_id,)
        )
        stats['devices_count'] = result['count'] if result else 0

        return stats


if __name__ == "__main__":
    from shared.database.init import db

    # 初始化
    db.initialize()

    # 创建许可证管理器
    lm = LicenseManager(db)

    # 测试创建租户
    success, license_key, tenant_id = lm.create_tenant(
        tenant_code="TEST001",
        tenant_name="测试租户",
        license_type="trial",
        contact_info="test@example.com"
    )

    if success:
        print(f"✅ 租户创建成功")
        print(f"   许可证密钥: {license_key}")
        print(f"   租户ID: {tenant_id}")

        # 测试验证许可证
        valid, msg, tenant_info = lm.validate_license(license_key)
        if valid:
            print(f"✅ 许可证验证成功")
            print(f"   租户信息: {tenant_info}")
        else:
            print(f"❌ 许可证验证失败: {msg}")
    else:
        print(f"❌ 租户创建失败: {license_key}")
