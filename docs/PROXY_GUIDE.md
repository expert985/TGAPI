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

### 你的新加坡高速代理

```python
# 代理信息
Server: 27.152.180.236
Port: 41101
Secret: ee38df3159cdeec7bf5122293ab5c28c4e617a7572652e6d6963726f736f66742e636f6d

# MTProxy链接
https://t.me/proxy?server=27.152.180.236&port=41101&secret=ee38df3159cdeec7bf5122293ab5c28c4e617a7572652e6d6963726f736f66742e636f6d
```

### 使用方法

#### 方式1: 通过链接添加（推荐）

```python
from shared.utils.proxy_manager import proxy_pool

# 添加你的新加坡代理
mtproxy_link = "https://t.me/proxy?server=27.152.180.236&port=41101&secret=ee38df3159cdeec7bf5122293ab5c28c4e617a7572652e6d6963726f736f66742e636f6d"

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
    'server': '27.152.180.236',
    'port': 41101,
    'secret': 'ee38df3159cdeec7bf5122293ab5c28c4e617a7572652e6d6963726f736f66742e636f6d'
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

# 添加多个MTProxy代理
proxies = [
    "https://t.me/proxy?server=27.152.180.236&port=41101&secret=ee38df3159...",  # 新加坡
    "https://t.me/proxy?server=1.2.3.4&port=443&secret=abcd...",                 # 美国
    "https://t.me/proxy?server=5.6.7.8&port=443&secret=efgh...",                 # 欧洲
]

for proxy_link in proxies:
    proxy_pool.add_mtproxy_link(proxy_link)

print(f"代理池数量: {proxy_pool.count()}")
```

### 轮询使用代理

```python
# 每次获取不同的代理（轮询）
proxy1 = proxy_pool.get_next_proxy()  # 新加坡
proxy2 = proxy_pool.get_next_proxy()  # 美国
proxy3 = proxy_pool.get_next_proxy()  # 欧洲
proxy4 = proxy_pool.get_next_proxy()  # 回到新加坡
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

# 测试你的新加坡代理
mtproxy_link = "https://t.me/proxy?server=27.152.180.236&port=41101&secret=ee38df3159..."

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

# 默认MTProxy代理（可选）
DEFAULT_MTPROXY_LINK=https://t.me/proxy?server=27.152.180.236&port=41101&secret=ee38df3159cdeec7bf5122293ab5c28c4e617a7572652e6d6963726f736f66742e636f6d

# 是否启用代理
PROXY_ENABLED=true

# 代理池（多个代理，用|分隔）
PROXY_POOL=https://t.me/proxy?server=27.152.180.236&port=41101&secret=xxx|https://t.me/proxy?server=1.2.3.4&port=443&secret=yyy

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
    # 1. 添加新加坡高速代理
    proxy_pool.add_mtproxy_link(
        "https://t.me/proxy?server=27.152.180.236&port=41101&secret=ee38df3159..."
    )

    # 2. 创建TGAPI链接（使用代理）
    success, api_url, token = await tgapi_manager.create_api_link(
        session_string="YOUR_SESSION",
        api_id=12345,
        api_hash="YOUR_HASH",
        proxy_link=proxy_pool.get_next_proxy()
    )

    if success:
        print(f"✅ API链接: {api_url}")
        print(f"✅ 使用代理: 新加坡高速MTProxy")

asyncio.run(main())
```

### 示例2: 使用代理池批量操作

```python
from shared.utils.proxy_manager import proxy_pool

# 添加多个代理
proxies = [
    "https://t.me/proxy?server=27.152.180.236&port=41101&secret=...",  # 新加坡
    "https://t.me/proxy?server=1.2.3.4&port=443&secret=...",            # 美国
    "https://t.me/proxy?server=5.6.7.8&port=443&secret=...",            # 欧洲
]

for link in proxies:
    proxy_pool.add_mtproxy_link(link)

# 批量操作，每个账号使用不同代理
accounts = [...]
for account in accounts:
    proxy = proxy_pool.get_next_proxy()  # 轮询获取代理
    # 使用proxy处理account
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
# 使用MTProxy（推荐）
PROXY_ENABLED=true
DEFAULT_MTPROXY_LINK=https://t.me/proxy?server=27.152.180.236&port=41101&secret=ee38df3159...
```

### 生产环境（海外）
```bash
# 可以不使用代理
PROXY_ENABLED=false
```

---

## 🚀 性能对比

| 代理类型 | 速度 | 稳定性 | 隐蔽性 | 推荐 |
|---------|-----|-------|-------|-----|
| **MTProxy** | ⚡⚡⚡⚡⚡ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ✅ **强烈推荐** |
| SOCKS5 | ⚡⚡⚡⚡ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ✅ 推荐 |
| HTTP | ⚡⚡⚡ | ⭐⭐⭐ | ⭐⭐ | ⚠️ 备选 |

**你的新加坡高速MTProxy是最佳选择！** ⭐

---

## 💡 最佳实践

1. **使用MTProxy**：优先使用你的新加坡高速MTProxy
2. **配置代理池**：准备多个不同地区的代理备用
3. **定期测试**：定期测试代理可用性
4. **轮询使用**：批量操作时轮询使用不同代理
5. **错误重试**：代理失败时自动切换到下一个

---

**✅ 你的新加坡高速MTProxy已完全集成到系统中！**

使用方法：
```python
proxy_pool.add_mtproxy_link("https://t.me/proxy?server=27.152.180.236...")
```

