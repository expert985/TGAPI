# 📝 环境变量配置说明

## 🚀 快速开始

### 1. 复制配置文件

```bash
cp .env.example .env
```

### 2. 编辑配置文件

```bash
nano .env
# 或
vim .env
```

---

## 📋 完整配置说明

### 1. Telegram Bot配置

```bash
# Telegram Bot Token（从 @BotFather 获取）
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz

# Telegram API凭证（从 https://my.telegram.org 获取）
API_ID=12345678
API_HASH=abcdef1234567890abcdef1234567890

# 管理员用户ID（多个用逗号分隔）
ADMIN_USER_IDS=123456789,987654321
```

**如何获取**：
- **BOT_TOKEN**: 与[@BotFather](https://t.me/BotFather)对话，发送`/newbot`创建机器人
- **API_ID/API_HASH**: 访问[https://my.telegram.org/apps](https://my.telegram.org/apps)注册应用
- **ADMIN_USER_IDS**: 与[@userinfobot](https://t.me/userinfobot)对话获取您的用户ID

---

### 2. 数据库配置

```bash
# SQLite数据库路径（默认）
DATABASE_PATH=data/bot.db
```

---

### 3. API服务配置

```bash
# 服务器监听地址
SERVER_HOST=0.0.0.0  # 0.0.0.0 = 监听所有网卡
SERVER_PORT=8000     # 端口号

# 调试模式
DEBUG=false  # 生产环境设为false
```

---

### 4. TGAPI接码配置 ⭐ **重要**

```bash
# TGAPI接码基础URL（客户端访问此URL获取验证码）
TGAPI_BASE_URL=https://api.yourdomain.com

# 示例：
# 生产环境（HTTPS）: TGAPI_BASE_URL=https://api.example.com
# 测试环境（HTTP）:  TGAPI_BASE_URL=http://example.com:8000
# 本地测试:          TGAPI_BASE_URL=http://localhost:8000

# TGAPI默认配置
TGAPI_DEFAULT_EXPIRE_HOURS=24  # 链接有效期（小时）
TGAPI_DEFAULT_MAX_LOGIN=-1     # 最大登录次数（-1=无限制）
```

**作用说明**：
- 当您创建TGAPI接码链接时，系统会生成如下格式的链接：
  ```
  {TGAPI_BASE_URL}/api/code/{token}

  例如：
  https://api.example.com/api/code/abc123xyz
  ```
- 客户端访问此链接即可获取TG登录验证码

**域名配置建议**：
1. **公网访问**: 使用您的域名 + Nginx反向代理
2. **内网访问**: 使用内网IP + 端口号
3. **本地测试**: 使用 `http://localhost:8000`

---

### 5. Web管理后台配置 ⭐ **重要**

```bash
# 管理员账号
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
# ⚠️ 生产环境请立即修改默认密码！

# Session密钥（用于加密Session Cookie）
# 生成方法: python -c "import secrets; print(secrets.token_hex(32))"
SESSION_SECRET_KEY=your_secret_key_here_change_in_production

# Session过期时间（小时）
SESSION_TIMEOUT_HOURS=24
```

**管理后台访问地址**：
```
本地: http://localhost:8000/admin
公网: http://yourdomain.com:8000/admin
```

**首次登录**：
- 用户名: `admin`（可自定义）
- 密码: `admin123`（务必修改！）

**生成安全密钥**：
```bash
python -c "import secrets; print(secrets.token_hex(32))"
# 输出: a1b2c3d4e5f6...（64个字符的随机密钥）
```

---

### 6. 许可证配置

```bash
# 每个许可证最多绑定的设备数
LICENSE_MAX_DEVICES=3
```

---

### 7. 数据库配置（高级）

#### SQLite（默认，适合小规模）

```bash
DATABASE_TYPE=sqlite
DATABASE_PATH=data/bot.db
```

#### MySQL（生产环境推荐）

```bash
DATABASE_TYPE=mysql

# MySQL连接配置
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=tgbot
MYSQL_PASSWORD=your_strong_password_here
MYSQL_DATABASE=tgbot_manager
MYSQL_CHARSET=utf8mb4
```

**MySQL设置步骤**：
```sql
-- 1. 创建数据库
CREATE DATABASE tgbot_manager CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 2. 创建用户并授权
CREATE USER 'tgbot'@'localhost' IDENTIFIED BY 'your_strong_password_here';
GRANT ALL PRIVILEGES ON tgbot_manager.* TO 'tgbot'@'localhost';
FLUSH PRIVILEGES;

-- 3. 导入数据库结构
mysql -u tgbot -p tgbot_manager < shared/database/mysql_init.sql
```

---

### 8. Redis配置（可选，用于缓存加速）

```bash
# 是否启用Redis
REDIS_ENABLED=false

# Redis连接配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0
```

**启用Redis的好处**：
- 10-100x性能提升
- 支持百万级数据
- 减少数据库负载

---

### 9. 代理配置（可选）

```bash
# 是否启用代理
PROXY_ENABLED=false

# 注意：代理无需在此配置！
# 请通过Web管理后台动态添加代理：
# 访问: http://localhost:8000/admin/proxies
```

**代理管理方式**：
1. 登录管理后台
2. 进入"代理管理"页面
3. 点击"添加代理"
4. 输入MTProxy/SOCKS5链接
5. 立即生效

---

### 10. 备份配置

```bash
# 是否启用自动备份
BACKUP_ENABLED=true

# 备份间隔（小时）
BACKUP_INTERVAL_HOURS=24
```

---

## 🔧 配置示例

### 示例1: 本地开发环境

```bash
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
API_ID=12345678
API_HASH=abcdef1234567890abcdef1234567890
ADMIN_USER_IDS=123456789

DATABASE_PATH=data/bot.db

SERVER_HOST=0.0.0.0
SERVER_PORT=8000
DEBUG=true

TGAPI_BASE_URL=http://localhost:8000

ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
SESSION_SECRET_KEY=dev_secret_key_for_testing_only

DATABASE_TYPE=sqlite
REDIS_ENABLED=false
PROXY_ENABLED=false
```

### 示例2: 生产环境（公网部署）

```bash
BOT_TOKEN=YOUR_REAL_BOT_TOKEN
API_ID=YOUR_REAL_API_ID
API_HASH=YOUR_REAL_API_HASH
ADMIN_USER_IDS=YOUR_TELEGRAM_ID

DATABASE_PATH=data/bot.db

SERVER_HOST=0.0.0.0
SERVER_PORT=8000
DEBUG=false

# 使用您的域名
TGAPI_BASE_URL=https://api.yourdomain.com

# 修改默认密码！
ADMIN_USERNAME=admin
ADMIN_PASSWORD=YourStrongPassword123!
SESSION_SECRET_KEY=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6

# 使用MySQL
DATABASE_TYPE=mysql
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=tgbot
MYSQL_PASSWORD=YourMySQLPassword123!
MYSQL_DATABASE=tgbot_manager

# 启用Redis
REDIS_ENABLED=true
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=YourRedisPassword123!

PROXY_ENABLED=false  # 通过后台管理代理
BACKUP_ENABLED=true
BACKUP_INTERVAL_HOURS=24
```

---

## 🚨 安全建议

### 1. 修改默认密码
```bash
# ❌ 不安全
ADMIN_PASSWORD=admin123

# ✅ 安全
ADMIN_PASSWORD=MyStr0ng!P@ssw0rd#2024
```

### 2. 生成强密钥
```bash
# 使用Python生成随机密钥
python -c "import secrets; print(secrets.token_hex(32))"

# 或使用OpenSSL
openssl rand -hex 32
```

### 3. 限制访问
```bash
# 仅允许本地访问管理后台
SERVER_HOST=127.0.0.1  # 仅本地访问

# 使用Nginx反向代理并启用HTTPS
# 配置Nginx的IP白名单
```

### 4. 使用HTTPS
```nginx
# Nginx配置示例
server {
    listen 443 ssl;
    server_name api.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 🔍 常见问题

### Q1: TGAPI_BASE_URL应该填什么？

**A**: 填写客户端访问您服务器的URL：
- 本地测试: `http://localhost:8000`
- 内网部署: `http://192.168.1.100:8000`
- 公网部署: `https://api.yourdomain.com`

### Q2: 如何修改管理员密码？

**A**: 修改`.env`文件中的`ADMIN_PASSWORD`，然后重启服务。

### Q3: 是否必须使用MySQL？

**A**: 不是。SQLite可以支持10万级账号，MySQL支持百万级。根据需求选择。

### Q4: Redis是否必需？

**A**: 不是。Redis可选，启用后性能提升10-100倍。

### Q5: 代理在哪里配置？

**A**: 不在`.env`配置！通过Web管理后台动态添加：
```
http://localhost:8000/admin/proxies
```

---

## 📚 相关文档

- [管理后台使用指南](./ADMIN_DASHBOARD.md)
- [代理配置指南](./PROXY_GUIDE.md)
- [MySQL+Redis架构](./MYSQL_REDIS_ARCHITECTURE.md)
- [系统架构设计](./ARCHITECTURE.md)

---

**✅ 配置完成后，启动系统**:
```bash
./start.sh start
```

**访问管理后台**:
```
http://localhost:8000/admin
```
