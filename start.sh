#!/bin/bash

# ============================================================
# TG Bot Manager - 智能多功能启动脚本
# ============================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目配置
PROJECT_NAME="tgbot_manager"
API_PORT=52000
VENV_DIR="venv"
LOG_DIR="logs"

# ============================================================
# 工具函数
# ============================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 显示横幅
show_banner() {
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════════════════╗"
    echo "║                                                        ║"
    echo "║          TG Bot Manager - 管理控制台                  ║"
    echo "║          Telegram账号综合管理系统                     ║"
    echo "║                                                        ║"
    echo "╚════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# ============================================================
# 环境检测函数
# ============================================================

# 检查Docker是否安装
check_docker() {
    log_info "检查Docker安装状态..."
    if command -v docker &> /dev/null; then
        DOCKER_VERSION=$(docker --version | awk '{print $3}' | tr -d ',')
        log_success "Docker已安装 (版本: $DOCKER_VERSION)"
        return 0
    else
        log_warning "Docker未安装"
        return 1
    fi
}

# 智能安装Docker
install_docker() {
    log_info "开始安装Docker..."

    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux系统
        log_info "检测到Linux系统，使用官方安装脚本..."
        curl -fsSL https://get.docker.com -o get-docker.sh
        sudo sh get-docker.sh
        sudo usermod -aG docker $USER
        rm get-docker.sh
        log_success "Docker安装完成！请重新登录以生效。"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        log_warning "请手动安装Docker Desktop for Mac: https://www.docker.com/products/docker-desktop"
        exit 1
    else
        log_error "不支持的操作系统"
        exit 1
    fi
}

# 检查docker-compose
check_docker_compose() {
    log_info "检查docker-compose状态..."
    if command -v docker-compose &> /dev/null || docker compose version &> /dev/null; then
        log_success "docker-compose已安装"
        return 0
    else
        log_warning "docker-compose未安装"
        return 1
    fi
}

# 安装docker-compose
install_docker_compose() {
    log_info "安装docker-compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    log_success "docker-compose安装完成"
}

# 检查端口占用
check_port() {
    local port=$1
    log_info "检查端口 $port 是否被占用..."

    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        local pid=$(lsof -Pi :$port -sTCP:LISTEN -t)
        local process=$(ps -p $pid -o comm=)
        log_warning "端口 $port 已被占用 (PID: $pid, 进程: $process)"

        read -p "是否要终止占用进程? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            kill -9 $pid
            log_success "进程已终止"
        else
            log_error "端口被占用，无法继续"
            exit 1
        fi
    else
        log_success "端口 $port 可用"
    fi
}

# 检查文件权限
check_permissions() {
    log_info "检查文件权限..."

    local dirs=("data" "sessions" "logs")
    for dir in "${dirs[@]}"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
            log_info "创建目录: $dir"
        fi

        if [ ! -w "$dir" ]; then
            log_warning "目录 $dir 不可写，尝试修复..."
            chmod 755 "$dir"
        fi
    done

    log_success "文件权限检查完成"
}

# 检查.env文件
check_env_file() {
    log_info "检查环境配置文件..."

    if [ ! -f ".env" ]; then
        log_warning ".env文件不存在，从示例文件创建..."
        if [ -f ".env.example" ]; then
            cp .env.example .env
            log_warning "请编辑 .env 文件填写必要的配置！"
            log_warning "至少需要设置: BOT_TOKEN, API_ID, API_HASH"
            exit 1
        else
            log_error ".env.example 文件不存在"
            exit 1
        fi
    else
        log_success ".env文件存在"

        # 检查关键配置
        if ! grep -q "BOT_TOKEN=" .env || grep -q "BOT_TOKEN=your_bot_token_here" .env; then
            log_error "BOT_TOKEN 未配置，请编辑 .env 文件"
            exit 1
        fi
    fi
}

# Python虚拟环境检查
check_python_venv() {
    log_info "检查Python虚拟环境..."

    if [ ! -d "$VENV_DIR" ]; then
        log_info "创建Python虚拟环境..."
        python3 -m venv $VENV_DIR
        log_success "虚拟环境创建完成"
    else
        log_success "虚拟环境已存在"
    fi
}

# 安装Python依赖
install_python_deps() {
    log_info "安装Python依赖..."

    source $VENV_DIR/bin/activate

    if [ -f "requirements.txt" ]; then
        pip install --upgrade pip -q
        pip install -r requirements.txt -q
        log_success "依赖安装完成"
    else
        log_error "requirements.txt 不存在"
        exit 1
    fi

    deactivate
}

# ============================================================
# 主要功能函数
# ============================================================

# 一键初始化检测
init_check() {
    show_banner
    log_info "开始环境初始化检测..."
    echo

    # 1. 检查Docker
    if ! check_docker; then
        read -p "是否要安装Docker? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            install_docker
        else
            log_warning "跳过Docker安装"
        fi
    fi

    # 2. 检查docker-compose
    if ! check_docker_compose; then
        read -p "是否要安装docker-compose? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            install_docker_compose
        fi
    fi

    # 3. 检查端口
    check_port $API_PORT

    # 4. 检查文件权限
    check_permissions

    # 5. 检查环境配置
    check_env_file

    # 6. 检查Python环境
    check_python_venv

    # 7. 安装依赖
    read -p "是否要安装Python依赖? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        install_python_deps
    fi

    echo
    log_success "✅ 环境初始化检测完成！"
    echo
}

# Docker启动
docker_start() {
    show_banner
    log_info "启动Docker容器..."

    check_env_file
    check_port $API_PORT

    docker-compose up -d

    log_success "容器启动成功！"
    echo
    log_info "查看状态: ./start.sh status"
    log_info "查看日志: ./start.sh logs"
}

# Docker停止
docker_stop() {
    show_banner
    log_info "停止Docker容器..."

    docker-compose down

    log_success "容器已停止"
}

# Docker重启
docker_restart() {
    show_banner
    log_info "重启Docker容器..."

    docker-compose restart

    log_success "容器重启成功"
}

# 查看容器状态
docker_status() {
    show_banner
    log_info "容器运行状态:"
    echo
    docker-compose ps
}

# 查看日志
docker_logs() {
    show_banner
    log_info "实时查看日志 (Ctrl+C退出)..."
    echo

    if [ -n "$1" ]; then
        # 查看指定服务的日志
        docker-compose logs -f --tail=100 $1
    else
        # 查看所有服务的日志
        docker-compose logs -f --tail=100
    fi
}

# 测试模式运行（不使用Docker）
test_mode() {
    show_banner
    log_info "启动测试模式..."

    check_env_file
    check_python_venv
    check_port $API_PORT

    # 激活虚拟环境
    source $VENV_DIR/bin/activate

    # 初始化数据库
    log_info "初始化数据库..."
    python -c "from shared.database.init import db; db.initialize()"

    # 启动API服务器（后台）
    log_info "启动API服务器..."
    python -m api.server &
    API_PID=$!

    sleep 3

    # 启动Bot
    log_info "启动Telegram Bot..."
    python -m bot.main &
    BOT_PID=$!

    log_success "测试模式启动成功！"
    echo
    log_info "API服务器 PID: $API_PID"
    log_info "Bot PID: $BOT_PID"
    echo
    log_info "按 Ctrl+C 停止..."

    # 等待中断信号
    trap "kill $API_PID $BOT_PID; exit" SIGINT SIGTERM

    # 实时显示日志
    tail -f logs/bot.log 2>/dev/null || wait

    deactivate
}

# 数据库管理
db_manage() {
    show_banner
    log_info "数据库管理工具"
    echo

    source $VENV_DIR/bin/activate

    case "$1" in
        init)
            log_info "初始化数据库..."
            python -c "from shared.database.init import db; db.initialize()"
            log_success "数据库初始化完成"
            ;;
        backup)
            log_info "备份数据库..."
            BACKUP_FILE="data/backup_$(date +%Y%m%d_%H%M%S).db"
            cp data/bot.db $BACKUP_FILE
            log_success "数据库已备份到: $BACKUP_FILE"
            ;;
        stats)
            log_info "数据库统计信息:"
            python -c "from shared.database.init import db; db.initialize(); stats = db.get_stats(); print(stats)"
            ;;
        *)
            echo "用法: $0 db {init|backup|stats}"
            ;;
    esac

    deactivate
}

# PM2管理
pm2_start() {
    show_banner
    log_info "使用PM2启动服务..."

    check_env_file
    check_python_venv

    # 检查PM2是否安装
    if ! command -v pm2 &> /dev/null; then
        log_error "PM2未安装，请先安装: npm install -g pm2"
        exit 1
    fi

    # 启动服务
    pm2 start ecosystem.config.js

    log_success "服务启动成功！"
    echo
    log_info "查看状态: pm2 status 或 ./start.sh pm2 status"
    log_info "查看日志: pm2 logs 或 ./start.sh pm2 logs"
}

pm2_stop() {
    show_banner
    log_info "停止PM2服务..."
    pm2 stop ecosystem.config.js
    log_success "服务已停止"
}

pm2_restart() {
    show_banner
    log_info "重启PM2服务..."
    pm2 restart ecosystem.config.js
    log_success "服务重启成功"
}

pm2_status() {
    show_banner
    log_info "PM2服务状态:"
    echo
    pm2 status
}

pm2_logs() {
    show_banner
    log_info "实时查看PM2日志 (Ctrl+C退出)..."
    echo
    if [ -n "$1" ]; then
        pm2 logs $1
    else
        pm2 logs
    fi
}

pm2_delete() {
    show_banner
    log_warning "删除PM2服务..."
    read -p "确定要删除所有PM2服务? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        pm2 delete ecosystem.config.js
        log_success "PM2服务已删除"
    fi
}

# Bot Pool管理
pool_status() {
    show_banner
    log_info "查询Bot Pool状态..."

    source $VENV_DIR/bin/activate

    # 使用Python查询Bot Pool状态
    python -c "
from shared.database.init import db
from bot.pool.redis_cache import BotPoolRedisCache
import redis
import os

db.initialize()

# 查询数据库中的bot配置
bots = db.fetchall('SELECT * FROM bot_configs ORDER BY priority DESC')

print('\\n📊 Bot Pool状态:\\n')
print(f'总Bot数: {len(bots)}')

for bot in bots:
    status_icon = '✅' if bot['status'] == 'active' else '⚠️'
    print(f'{status_icon} Bot #{bot[\"id\"]} (@{bot[\"bot_username\"]}) - {bot[\"status\"]} - 优先级:{bot[\"priority\"]}')

# 查询Redis缓存
try:
    redis_client = redis.Redis(
        host=os.getenv('REDIS_HOST', 'localhost'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        db=int(os.getenv('REDIS_DB', 0)),
        decode_responses=True
    )
    cache = BotPoolRedisCache(redis_client)

    # 获取可用bot列表
    available_bots = redis_client.zrange('bot_pool:available_bots', 0, -1, withscores=True)
    if available_bots:
        print('\\n📈 当前负载:')
        for bot_id, load in available_bots:
            print(f'  Bot #{bot_id}: {int(load)} 活跃用户')
except Exception as e:
    print(f'\\n⚠️  Redis连接失败: {str(e)}')
"

    deactivate
}

pool_add() {
    show_banner
    log_info "添加Bot到Pool..."

    read -p "Bot Token: " bot_token
    read -p "Bot Username (如@MyBot): " bot_username
    read -p "Bot名称: " bot_name
    read -p "最大负载 (默认100): " max_load
    read -p "优先级 (1-10, 默认5): " priority

    max_load=${max_load:-100}
    priority=${priority:-5}

    source $VENV_DIR/bin/activate

    python -c "
from shared.database.init import db

db.initialize()

db.execute('''
    INSERT INTO bot_configs (bot_token, bot_username, bot_name, max_load, priority, status)
    VALUES (?, ?, ?, ?, ?, 'inactive')
''', ('$bot_token', '$bot_username', '$bot_name', $max_load, $priority))

print('✅ Bot已添加到池中')
print('⚠️  请重启Bot Pool服务以加载新bot')
"

    deactivate
}

pool_restart_bot() {
    show_banner

    if [ -z "$1" ]; then
        log_error "请指定Bot ID"
        echo "用法: ./start.sh pool restart <bot_id>"
        exit 1
    fi

    log_info "重启Bot #$1..."

    source $VENV_DIR/bin/activate

    python -c "
from shared.database.init import db

db.initialize()

# 设置bot为maintenance状态
db.execute('UPDATE bot_configs SET status = \"maintenance\" WHERE id = ?', ($1,))
print('⏸️  Bot #$1 已设为维护模式')

# 等待3秒
import time
time.sleep(3)

# 恢复为active状态
db.execute('UPDATE bot_configs SET status = \"active\" WHERE id = ?', ($1,))
print('✅ Bot #$1 已恢复运行')
"

    deactivate
}

# 清理
clean() {
    show_banner
    log_warning "清理项目文件..."

    read -p "确定要清理所有容器和数据? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker-compose down -v
        log_success "Docker容器和卷已清理"

        read -p "是否删除数据文件? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf data/* sessions/* logs/*
            log_success "数据文件已清理"
        fi
    fi
}

# 显示帮助
show_help() {
    show_banner
    echo -e "${GREEN}使用方法:${NC}"
    echo "  $0 <命令> [选项]"
    echo
    echo -e "${GREEN}Docker模式命令:${NC}"
    echo -e "  ${BLUE}init${NC}           - 一键环境检测和初始化"
    echo -e "  ${BLUE}start${NC}          - 启动Docker容器"
    echo -e "  ${BLUE}stop${NC}           - 停止Docker容器"
    echo -e "  ${BLUE}restart${NC}        - 重启Docker容器"
    echo -e "  ${BLUE}status${NC}         - 查看容器状态"
    echo -e "  ${BLUE}logs${NC} [服务]    - 查看日志（可选指定服务: api/bot）"
    echo
    echo -e "${GREEN}PM2模式命令:${NC}"
    echo -e "  ${BLUE}pm2${NC} start      - 使用PM2启动服务"
    echo -e "  ${BLUE}pm2${NC} stop       - 停止PM2服务"
    echo -e "  ${BLUE}pm2${NC} restart    - 重启PM2服务"
    echo -e "  ${BLUE}pm2${NC} status     - 查看PM2状态"
    echo -e "  ${BLUE}pm2${NC} logs       - 查看PM2日志"
    echo -e "  ${BLUE}pm2${NC} delete     - 删除PM2服务"
    echo
    echo -e "${GREEN}Bot Pool管理:${NC}"
    echo -e "  ${BLUE}pool${NC} status    - 查看Bot Pool状态"
    echo -e "  ${BLUE}pool${NC} add       - 添加Bot到池中"
    echo -e "  ${BLUE}pool${NC} restart <id> - 重启指定Bot"
    echo
    echo -e "${GREEN}其他命令:${NC}"
    echo -e "  ${BLUE}test${NC}           - 测试模式运行（不使用Docker）"
    echo -e "  ${BLUE}db${NC} <操作>      - 数据库管理 (init/backup/stats)"
    echo -e "  ${BLUE}clean${NC}          - 清理容器和数据"
    echo -e "  ${BLUE}help${NC}           - 显示此帮助信息"
    echo
    echo -e "${GREEN}示例:${NC}"
    echo "  $0 init                # 首次使用，初始化环境"
    echo "  $0 start               # 启动Docker服务"
    echo "  $0 pm2 start           # 使用PM2启动"
    echo "  $0 pool status         # 查看Bot Pool状态"
    echo "  $0 pool add            # 添加新Bot"
    echo "  $0 pool restart 1      # 重启Bot #1"
    echo "  $0 logs api            # 查看API服务日志"
    echo "  $0 test                # 测试模式运行"
    echo "  $0 db backup           # 备份数据库"
    echo
}

# ============================================================
# 主程序入口
# ============================================================

main() {
    case "${1:-help}" in
        init)
            init_check
            ;;
        start)
            docker_start
            ;;
        stop)
            docker_stop
            ;;
        restart)
            docker_restart
            ;;
        status)
            docker_status
            ;;
        logs)
            docker_logs $2
            ;;
        test)
            test_mode
            ;;
        db)
            db_manage $2
            ;;
        pm2)
            case "$2" in
                start)
                    pm2_start
                    ;;
                stop)
                    pm2_stop
                    ;;
                restart)
                    pm2_restart
                    ;;
                status)
                    pm2_status
                    ;;
                logs)
                    pm2_logs $3
                    ;;
                delete)
                    pm2_delete
                    ;;
                *)
                    log_error "未知PM2命令: $2"
                    echo "用法: $0 pm2 {start|stop|restart|status|logs|delete}"
                    exit 1
                    ;;
            esac
            ;;
        pool)
            case "$2" in
                status)
                    pool_status
                    ;;
                add)
                    pool_add
                    ;;
                restart)
                    pool_restart_bot $3
                    ;;
                *)
                    log_error "未知Pool命令: $2"
                    echo "用法: $0 pool {status|add|restart <id>}"
                    exit 1
                    ;;
            esac
            ;;
        clean)
            clean
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "未知命令: $1"
            echo
            show_help
            exit 1
            ;;
    esac
}

# 运行主程序
main "$@"
