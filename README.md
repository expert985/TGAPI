# TGAPI - Telegram账号综合管理系统

> 🚀 强大的Telegram多账号管理平台 + Bot Pool负载均衡 + Web管理后台

## ⭐ 核心特性

### 🤖 智能Bot系统
- **Bot Pool负载均衡** - 多bot自动分配用户，高可用
- **用户授权管理** - 灵活租户系统（1月/3月/6月/1年/永久）
- **会话保持** - 同用户固定使用同一bot
- **健康监控** - 30秒心跳检查，自动故障隔离
- **日志管理** - 每日自动切割，30天自动清理
- **进程管理** - 支持Docker/PM2/手动三种部署方式

### 📱 TGAPI接码系统
- **Session转API** - 将Session文件转为Web接码链接
- **多格式支持** - Telethon/Pyrogram/TData
- **限制控制** - 登录次数和过期时间限制

### 🏢 多租户账号管理
- **账号池管理** - 批量导入、搜索、批量操作
- **格式转换** - Session/TData/JSON/AuthKey互转
- **状态监控** - 实时检查账号状态

### 🖥️ Web管理后台
- **实时监控** - 4个可视化图表
- **Bot Pool管理** - 动态添加/删除bot
- **用户授权** - 在线授权，查看未授权日志
- **Excel导出** - 完整数据报表

## 🚀 快速开始

### 1. 环境要求
```bash
# 必需
Python 3.9+
SQLite 3.31+ (Python内置，无需安装)

# 可选
Redis 7.0+ (Bot Pool模式需要)
Node.js 14+ + PM2 (使用PM2进程管理时需要)
Docker + Docker Compose (使用Docker部署时需要)
```

**💡 数据库说明**：
- 当前版本使用 **SQLite** 轻量级数据库（零配置）
- 适合场景：个人使用、中小规模部署（< 10万用户）
- 数据文件：`data/bot.db`
- 如需 MySQL 支持，请提交 Issue

### 2. 安装
```bash
git clone https://github.com/yourusername/TGAPI.git
cd TGAPI
pip install -r requirements.txt
```

### 3. 配置
```bash
cp .env.example .env
# 编辑 .env 文件，填入你的配置
```

**最小配置：**
```bash
BOT_TOKEN=your_bot_token_here
API_ID=your_api_id_here
API_HASH=your_api_hash_here
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_password
```

### 4. 启动

#### 🎯 方式一：交互式菜单（推荐）
```bash
./start.sh
```
进入交互式菜单，选择对应编号即可：
```
【Docker模式】
  1)  🔧 环境初始化检测
  2)  ▶️  启动Docker容器
  3)  ⏸️  停止Docker容器
  ...

【PM2模式】
  11) ▶️  使用PM2启动服务
  12) ⏸️  停止PM2服务
  ...

【Bot Pool管理】
  21) 📊 查看Bot Pool状态
  22) ➕ 添加Bot到池中
  23) 🔄 重启指定Bot
```

#### 🐳 方式二：Docker模式
```bash
# 初始化环境
./start.sh init

# 启动所有服务（Bot + API + Redis + MySQL）
./start.sh start

# 查看日志
./start.sh logs

# 停止服务
./start.sh stop
```

#### ⚡ 方式三：PM2模式（生产推荐）
```bash
# 安装PM2
npm install -g pm2

# 初始化环境
./start.sh init

# 启动服务
./start.sh pm2 start

# 查看状态
./start.sh pm2 status

# 实时监控
pm2 monit

# 查看日志
./start.sh pm2 logs
```

#### 🔧 方式四：手动启动
**单Bot模式**：
```bash
# 启动Bot
python -m bot.main

# 启动API服务（新终端）
python -m api.server
```

**Bot Pool模式**：
```bash
# 1. 启动Redis
docker run -d -p 6379:6379 redis

# 2. 修改 .env
ENABLE_BOT_POOL=true

# 3. 启动服务
python -m bot.main
python -m api.server

# 4. 访问后台添加多个bot
http://localhost:8000/admin/bot-pool
```

### 5. 访问管理后台
```
URL: http://localhost:8000/admin
账号: admin
密码: (你在.env设置的密码)
```

## 📚 文档

- **[机器人使用手册.md](机器人使用手册.md)** - 详细功能说明和使用教程
- **[部署与配置.md](部署与配置.md)** - 技术架构和配置指南

## 🎯 核心功能

### 1. TGAPI接码
将Telegram账号转为Web接码API
```
功能：上传Session → 生成链接 → 用户访问 → 获取验证码
支持：限制登录次数、设置过期时间
```

### 2. 账号管理
多账号统一管理
```
功能：批量导入、高级搜索、状态监控、批量删除
支持：按租户隔离、账号详情查看
```

### 3. 格式转换
13种格式互转
```
支持：Session ⟷ TData ⟷ JSON ⟷ AuthKey
格式：Telethon/Pyrogram Session文件
```

### 4. 自动做号
基于TGAPI生成新号
```
输入：API ID + Hash + 手机号
输出：Session/TData/JSON
```

### 5. Bot Pool负载均衡
多bot高可用架构
```
特性：智能分配、会话保持、健康检查、故障隔离
策略：最少连接/加权随机/优先级
```

## 🏗️ 项目结构
```
TGAPI/
├── bot/main.py           # Bot主程序
├── bot/pool/             # Bot Pool负载均衡
├── api/server.py         # Web API服务
├── api/admin/            # 管理后台
├── modules/              # 功能模块
│   ├── tgapi/           # TGAPI接码
│   ├── account_manager/ # 账号管理
│   ├── converter/       # 格式转换
│   └── auto_gen/        # 自动做号
├── shared/               # 共享组件
└── docs/                 # 文档目录
```

## 🔒 安全特性
- ✅ Session加密存储
- ✅ 防爆破登录（5次失败锁定15分钟）
- ✅ HttpOnly Cookie
- ✅ SQL注入防护
- ✅ 用户授权系统

## 🛠️ 技术栈
- **Bot**: python-telegram-bot 20.0+
- **Client**: Telethon / Pyrogram
- **Web**: FastAPI 0.104+
- **Database**: MySQL 8.0+
- **Cache**: Redis 7.0+
- **Frontend**: Bootstrap 5 + Chart.js

## 📊 使用场景

**个人使用**：单Bot模式，简单快速
**商业运营**：Bot Pool模式，高可用负载均衡
**SaaS平台**：用户授权系统，租户隔离

## 🤝 贡献
欢迎提交Issue和Pull Request！

## 📄 许可证
MIT License

---
**⚡ 立即体验专业的Telegram账号管理平台！**
