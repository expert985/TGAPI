# 🤖 TG Bot Manager - Telegram账号综合管理系统

一个功能强大的Telegram账号管理机器人，集成了TGAPI接码、账号管理、格式转换和自动做号等功能。

## ✨ 核心功能

### 📱 TGAPI接码模块
将TG账号协议转换为在线API接码链接
- ✅ 实时验证码推送
- ✅ 自定义版权和2FA显示
- ✅ 设置过期时间和登录次数限制
- ✅ WebSocket实时通信

### 🛡️ 账号全功能处理
全方位的TG账号管理工具
- ✅ **防找回** - 修改密码、启用2FA、绑定邮箱
- ✅ **筛活** - 批量检测账号状态
- ✅ **账号清理** - 清除聊天记录、退出群组
- ✅ **账号维护** - 定期保活操作

### 🔄 格式转换器
支持多种TG账号格式互转
- ✅ TData ⟷ Session
- ✅ Session ⟷ JSON
- ✅ Session ⟷ AuthKey
- ✅ Telethon ⟷ Pyrogram
- ✅ 所有格式互转

### 🔨 逆向自动做号工具
基于TGAPI的自动做号工具
- ✅ 输入 API ID + Hash
- ✅ 自动生成新设备登录
- ✅ 输出多种格式: TData/Session/JSON/密钥

### 🔐 租户系统与反盗版
多租户系统，支持许可证管理
- ✅ 许可证密钥验证
- ✅ 硬件绑定（设备指纹）
- ✅ 多设备限制
- ✅ 使用统计和配额管理

## 🚀 快速开始

### 方式一：使用智能启动脚本（推荐）

```bash
# 1. 克隆项目
git clone <your-repo-url>
cd TGAPI

# 2. 一键初始化环境
./start.sh init

# 3. 编辑配置文件
nano .env
# 至少需要设置: BOT_TOKEN, API_ID, API_HASH, API_BASE_URL

# 4. 启动服务
./start.sh start

# 5. 查看日志
./start.sh logs
```

### 方式二：Docker Compose

```bash
# 1. 复制环境配置
cp .env.example .env
nano .env

# 2. 启动容器
docker-compose up -d

# 3. 查看状态
docker-compose ps

# 4. 查看日志
docker-compose logs -f
```

### 方式三：手动部署

```bash
# 1. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
nano .env

# 4. 初始化数据库
python -c "from shared.database.init import db; db.initialize()"

# 5. 启动API服务器（终端1）
python -m api.server

# 6. 启动Bot（终端2）
python -m bot.main
```

## 📋 环境配置

编辑 `.env` 文件：

```bash
# Telegram Bot配置
BOT_TOKEN=your_bot_token_here
API_ID=your_api_id_here
API_HASH=your_api_hash_here

# 管理员用户ID（多个用逗号分隔）
ADMIN_USER_IDS=123456789,987654321

# API服务配置
SERVER_PORT=52000
API_BASE_URL=https://api.yourdomain.com
# 如果使用HTTP: API_BASE_URL=http://yourdomain.com:52000

# 调试模式
DEBUG=false
```

## 🎯 start.sh 使用指南

智能多功能启动脚本，支持以下命令：

```bash
./start.sh init          # 一键环境检测和初始化
./start.sh start        # 启动Docker容器
./start.sh stop         # 停止Docker容器
./start.sh restart      # 重启Docker容器
./start.sh status       # 查看容器状态
./start.sh logs         # 查看所有日志（实时）
./start.sh test         # 测试模式运行（不使用Docker）
./start.sh db init      # 初始化数据库
./start.sh db backup    # 备份数据库
./start.sh clean        # 清理容器和数据
./start.sh help         # 显示帮助信息
```

## 📚 API接口文档

API服务默认运行在 `http://localhost:52000`

### 获取验证码（TGAPI核心接口）
```bash
GET /api/code/{api_token}?timeout=60
```

### 创建TGAPI链接
```bash
POST /api/tgapi/create
```

## 🤖 Bot命令列表

```
/start         - 显示欢迎信息和功能菜单
/menu          - 打开功能菜单
/tgapi         - TGAPI接码功能
/account       - 账号管理功能
/convert       - 格式转换功能
/autogen       - 自动做号功能
/stats         - 查看统计信息
/license       - 许可证管理
```

## ⚠️ 注意事项

1. **首次使用必须执行初始化**: `./start.sh init`
2. **必须配置环境变量**: BOT_TOKEN、API_ID、API_HASH、API_BASE_URL
3. **默认端口**: 52000（可通过SERVER_PORT修改）
4. **文档字符串**: 所有文件开头的 `"""..."""` 是Python docstring，不影响运行

---

**⭐ 如果这个项目对你有帮助，请给个Star！**
