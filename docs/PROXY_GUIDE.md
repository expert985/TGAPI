# 🌐 代理配置指南

## 📋 支持的代理类型

### 1. MTProto代理（MTProxy）⭐ 推荐
**Telegram官方代理协议**
- ✅ 速度最快
- ✅ 最稳定
- ✅ 伪装成普通HTTPS流量
- ✅ 支持Telegram专用

### 2. SOCKS5代理
**通用代理协议**
- ✅ 支持广泛
- ✅ 可用于所有应用
- ✅ 支持用户名密码认证

### 3. HTTP代理
**HTTP/HTTPS代理**
- ✅ 简单易用
- ⚠️ 速度较慢

---

## 🔧 MTProxy代理配置

### MTProxy链接格式

```python
# MTProxy链接格式示例
https://t.me/proxy?server=YOUR_SERVER&port=YOUR_PORT&secret=YOUR_SECRET

# 示例
# Server: 1.2.3.4
# Port: 443
# Secret: your_secret_here
```

**注意**: 代理链接请通过管理后台添加，不要硬编码在代码中

### 使用方法

#### 方式1: 通过链接添加（推荐）

```python
from shared.utils.proxy_manager import proxy_pool

# 添加MTProxy代理（从管理后台获取链接）
mtproxy_link = "https://t.me/proxy?server=YOUR_SERVER&port=YOUR_PORT&secret=YOUR_SECRET"

proxy_pool.add_mtproxy_link(mtproxy_link)

# 使用代理创建客户端
from telethon import TelegramClient
from shared.utils.proxy_manager import ProxyManager

proxy = proxy_pool.get_next_proxy()
telethon_proxy = ProxyManager.create_telethon_proxy(proxy)

client = TelegramClient(
    'my_session',
    api_id=12345,
    api_hash='your_api_hash',
    proxy=telethon_proxy
)
```

#### 方式2: 手动配置

```python
from shared.utils.proxy_manager import ProxyManager

# 手动配置代理
proxy_config = {
    'type': 'mtproto',
    'server': 'YOUR_SERVER',
    'port': YOUR_PORT,
    'secret': 'YOUR_SECRET'
}

# 创建Telethon代理
telethon_proxy = ProxyManager.create_telethon_proxy(proxy_config)

# 使用代理
client = TelegramClient(
    'my_session',
    api_id,
    api_hash,
    proxy=telethon_proxy
)
```

---

## 🎯 集成到现有模块

### 1. TGAPI接码模块集成

```python
# modules/tgapi/core.py

async def create_api_link(
    self,
    session_string: str,
    api_id: int,
    api_hash: str,
    proxy_link: str = None,  # 新增：支持MTProxy链接
    **kwargs
):
    """创建TGAPI接码链接（支持代理）"""

    # 解析代理
    proxy = None
    if proxy_link:
        from shared.utils.proxy_manager import ProxyManager
        proxy_config = ProxyManager.parse_mtproxy_link(proxy_link)
        if proxy_config:
            proxy = ProxyManager.create_telethon_proxy(proxy_config)

    # 创建客户端（使用代理）
    client = TelegramClient(
        StringSession(session_string),
        api_id,
        api_hash,
        proxy=proxy  # 使用代理
    )

    await client.connect()
    # ... 其他逻辑
```

### 2. 逆向接码客户端集成

```python
# modules/tgapi-client/client.py

async def login_via_api(
    self,
    api_url: str,
    phone: str,
    api_id: int,
    api_hash: str,
    proxy_link: str = None,  # 新增：MTProxy链接
    **kwargs
):
    """通过TGAPI接码登录（支持代理）"""

    # 解析代理
    proxy = None
    if proxy_link:
        from shared.utils.proxy_manager import ProxyManager
        proxy_config = ProxyManager.parse_mtproxy_link(proxy_link)
        if proxy_config:
            proxy = ProxyManager.create_telethon_proxy(proxy_config)

    # 使用代理创建客户端
    client = TelegramClient(
        StringSession(),
        api_id,
        api_hash,
        proxy=proxy
    )

    # ... 其他逻辑
```

### 3. 账号管理模块集成

```python
# modules/account-manager/manager.py

class AccountManager:
    def __init__(self, default_proxy_link: str = None):
        self.clients = {}
        self.default_proxy = None

        # 设置默认代理
        if default_proxy_link:
            from shared.utils.proxy_manager import ProxyManager
            proxy_config = ProxyManager.parse_mtproxy_link(default_proxy_link)
            if proxy_config:
                self.default_proxy = ProxyManager.create_telethon_proxy(proxy_config)

    async def _get_client(self, account_id: int) -> Optional[TelegramClient]:
        """获取客户端（使用默认代理）"""
        # ... 其他逻辑

        client = TelegramClient(
            StringSession(session_data),
            api_id,
            api_hash,
            proxy=self.default_proxy  # 使用默认代理
        )

        # ... 其他逻辑
```

---

## 🔄 代理池管理

### 添加多个代理

```python
from shared.utils.proxy_manager import proxy_pool

# 添加多个MTProxy代理（从管理后台配置）
proxies = [
    "https://t.me/proxy?server=SERVER1&port=PORT1&secret=SECRET1",  # 代理1
    "https://t.me/proxy?server=SERVER2&port=PORT2&secret=SECRET2",  # 代理2
    "https://t.me/proxy?server=SERVER3&port=PORT3&secret=SECRET3",  # 代理3
]

for proxy_link in proxies:
    proxy_pool.add_mtproxy_link(proxy_link)

print(f"代理池数量: {proxy_pool.count()}")
```

### 轮询使用代理

```python
# 每次获取不同的代理（轮询）
proxy1 = proxy_pool.get_next_proxy()  # 代理1
proxy2 = proxy_pool.get_next_proxy()  # 代理2
proxy3 = proxy_pool.get_next_proxy()  # 代理3
proxy4 = proxy_pool.get_next_proxy()  # 回到代理1
```

### 随机获取代理

```python
# 随机获取代理
proxy = proxy_pool.get_random_proxy()
```

---

## 🧪 代理测试

```python
from shared.utils.proxy_manager import ProxyManager

# 测试代理
mtproxy_link = "https://t.me/proxy?server=YOUR_SERVER&port=YOUR_PORT&secret=YOUR_SECRET"

proxy_config = ProxyManager.parse_mtproxy_link(mtproxy_link)

# 测试连接
is_working = ProxyManager.test_proxy(
    proxy_config,
    api_id=12345,
    api_hash='your_api_hash'
)

if is_working:
    print("✅ 代理工作正常！")
else:
    print("❌ 代理连接失败")
```

---

## ⚙️ 环境配置

在 `.env` 文件中添加代理配置：

```bash
# 代理配置

# 默认MTProxy代理（可选 - 建议通过管理后台配置）
# DEFAULT_MTPROXY_LINK=https://t.me/proxy?server=YOUR_SERVER&port=YOUR_PORT&secret=YOUR_SECRET

# 是否启用代理（可选，不添加代理也能正常运行）
PROXY_ENABLED=false

# 代理池（多个代理，用|分隔 - 建议通过管理后台配置）
# PROXY_POOL=https://t.me/proxy?server=SERVER1&port=PORT1&secret=SECRET1|https://t.me/proxy?server=SERVER2&port=PORT2&secret=SECRET2

# SOCKS5代理（可选）
SOCKS5_PROXY=socks5://user:pass@127.0.0.1:1080
```

---

## 📚 完整使用示例

### 示例1: 使用MTProxy进行TGAPI接码

```python
import asyncio
from modules.tgapi.core import tgapi_manager
from shared.utils.proxy_manager import proxy_pool

async def main():
    # 1. 添加MTProxy代理（从管理后台配置）
    # proxy_pool.add_mtproxy_link(
    #     "https://t.me/proxy?server=YOUR_SERVER&port=YOUR_PORT&secret=YOUR_SECRET"
    # )

    # 2. 创建TGAPI链接（可选使用代理）
    success, api_url, token = await tgapi_manager.create_api_link(
        session_string="YOUR_SESSION",
        api_id=12345,
        api_hash="YOUR_HASH",
        proxy_link=proxy_pool.get_next_proxy()  # 如果代理池为空，将使用直连
    )

    if success:
        print(f"✅ API链接: {api_url}")
        if proxy_pool.count() > 0:
            print(f"✅ 使用代理模式")
        else:
            print(f"✅ 使用直连模式")

asyncio.run(main())
```

### 示例2: 使用代理池批量操作

```python
from shared.utils.proxy_manager import proxy_pool

# 添加多个代理（从管理后台配置）
# proxies = [
#     "https://t.me/proxy?server=SERVER1&port=PORT1&secret=SECRET1",
#     "https://t.me/proxy?server=SERVER2&port=PORT2&secret=SECRET2",
#     "https://t.me/proxy?server=SERVER3&port=PORT3&secret=SECRET3",
# ]
#
# for link in proxies:
#     proxy_pool.add_mtproxy_link(link)

# 批量操作，每个账号可选使用不同代理
accounts = [...]
for account in accounts:
    proxy = proxy_pool.get_next_proxy()  # 轮询获取代理（如果代理池为空返回None）
    # 使用proxy处理account（proxy为None时使用直连）
```

---

## 🎯 推荐配置

### 开发环境
```bash
# 不使用代理或使用本地SOCKS5
PROXY_ENABLED=false
```

### 生产环境（国内）
```bash
# 使用MTProxy（推荐通过管理后台配置）
PROXY_ENABLED=false  # 代理通过管理后台动态添加
# DEFAULT_MTPROXY_LINK=  # 建议在管理后台配置
```

### 生产环境（海外）
```bash
# 可以不使用代理（直连即可）
PROXY_ENABLED=false
```

---

## 🚀 性能对比

| 代理类型 | 速度 | 稳定性 | 隐蔽性 | 推荐 |
|---------|-----|-------|-------|-----|
| **MTProxy** | ⚡⚡⚡⚡⚡ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ✅ **强烈推荐** |
| SOCKS5 | ⚡⚡⚡⚡ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ✅ 推荐 |
| HTTP | ⚡⚡⚡ | ⭐⭐⭐ | ⭐⭐ | ⚠️ 备选 |

**MTProxy是生产环境的最佳选择！** ⭐（请通过管理后台配置代理）

---

## 💡 最佳实践

1. **使用MTProxy**：优先使用MTProxy代理（速度最快、最稳定）
2. **管理后台配置**：通过Web管理后台动态添加/删除代理
3. **配置代理池**：准备多个不同地区的代理备用
4. **定期测试**：定期测试代理可用性
5. **轮询使用**：批量操作时轮询使用不同代理
6. **错误重试**：代理失败时自动切换到下一个
7. **可选使用**：系统支持无代理直连模式

---

**✅ 代理管理系统已完全集成！**

使用方法：
```python
# 方式1: 通过管理后台添加（推荐）
# 访问 http://your-domain/admin/proxies 添加代理

# 方式2: 通过代码添加
from shared.utils.proxy_manager import proxy_pool
proxy_pool.add_mtproxy_link("https://t.me/proxy?server=YOUR_SERVER&port=YOUR_PORT&secret=YOUR_SECRET")
```

**注意**：不添加代理时，系统将使用直连模式运行

