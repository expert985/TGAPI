"""
Telegram Bot 主程序 - 综合功能管理机器人
支持多Bot负载均衡
"""
import asyncio
import os
import redis
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from shared.config.settings import settings, load_env_file
from shared.database.init import db
from shared.utils.logger import logger
from shared.utils.license import LicenseManager
from shared.utils.authorization import auth_manager

from modules.tgapi.core import tgapi_manager
from modules.account_manager.manager import account_manager
from modules.converter.converter import conversion_pipeline
from modules.auto_gen.autogen import autogen_tool

# Bot Pool支持
from bot.pool import BotPoolManager, LoadBalanceStrategy


# 授权检查装饰器
def require_authorization(func):
    """要求用户授权的装饰器（支持命令和回调）"""
    async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        telegram_id = user.id
        username = user.username
        full_name = user.full_name

        # 检查授权
        authorized, message, user_info = auth_manager.check_authorization(telegram_id)

        if not authorized:
            # 记录未授权访问
            command = None
            if update.message:
                command = update.message.text
            elif update.callback_query:
                command = f"callback:{update.callback_query.data}"

            auth_manager.log_unauthorized_access(
                telegram_id=telegram_id,
                username=username,
                full_name=full_name,
                command=command,
                message=update.message.text if update.message else command
            )

            # 发送未授权消息
            unauthorized_message = f"""
⚠️ **未授权访问**

{message}

**您的信息**：
👤 Telegram ID: `{telegram_id}`
📛 用户名: @{username or '无'}
👨 全名: {full_name or '无'}

**如何获取授权？**
1️⃣ 联系管理员
2️⃣ 提供您的 Telegram ID: `{telegram_id}`
3️⃣ 完成付款后管理员将为您授权

💡 授权后即可使用机器人的所有功能！
"""

            # 根据update类型回复消息
            if update.message:
                await update.message.reply_text(unauthorized_message)
            elif update.callback_query:
                await update.callback_query.message.reply_text(unauthorized_message)
            return

        # 授权通过，执行原函数
        return await func(self, update, context)

    return wrapper


class TGBotManager:
    """Telegram Bot管理器"""

    def __init__(self):
        self.license_manager = LicenseManager(db)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """开始命令"""
        user = update.effective_user
        user_id = user.id

        # 欢迎消息
        welcome_text = f"""
👋 欢迎使用 Telegram 账号管理机器人！

🔹 **核心功能模块**

📱 **TGAPI接码** - 将TG账号转换为在线API接码链接
🛡️ **账号管理** - 防找回、筛活、清理、维护
🔄 **格式转换** - TData/Session/JSON/密钥互转
🔨 **自动做号** - 基于API自动生成账号

📋 **可用命令**
/start - 显示此帮助信息
/menu - 打开功能菜单
/tgapi - TGAPI接码功能
/account - 账号管理功能
/convert - 格式转换功能
/autogen - 自动做号功能
/stats - 查看统计信息
/license - 许可证管理

💡 使用 /menu 开始使用
"""

        keyboard = [
            [
                InlineKeyboardButton("📱 TGAPI", callback_data="menu_tgapi"),
                InlineKeyboardButton("🛡️ 账号管理", callback_data="menu_account")
            ],
            [
                InlineKeyboardButton("🔄 格式转换", callback_data="menu_convert"),
                InlineKeyboardButton("🔨 自动做号", callback_data="menu_autogen")
            ],
            [
                InlineKeyboardButton("📊 统计信息", callback_data="menu_stats"),
                InlineKeyboardButton("🔑 许可证", callback_data="menu_license")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(welcome_text, reply_markup=reply_markup)

    @require_authorization
    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """菜单命令"""
        keyboard = [
            [
                InlineKeyboardButton("📱 TGAPI", callback_data="menu_tgapi"),
                InlineKeyboardButton("🛡️ 账号管理", callback_data="menu_account")
            ],
            [
                InlineKeyboardButton("🔄 格式转换", callback_data="menu_convert"),
                InlineKeyboardButton("🔨 自动做号", callback_data="menu_autogen")
            ],
            [
                InlineKeyboardButton("📊 统计信息", callback_data="menu_stats"),
                InlineKeyboardButton("🔑 许可证", callback_data="menu_license")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text("🎯 请选择功能:", reply_markup=reply_markup)

    @require_authorization
    async def license_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """许可证命令"""
        user_id = update.effective_user.id

        # 查询用户的租户信息
        tenant_user = db.fetchone(
            "SELECT * FROM tenant_telegram_users WHERE telegram_user_id = ?",
            (user_id,)
        )

        if not tenant_user:
            await update.message.reply_text(
                "❌ 您还未绑定许可证\n\n"
                "请联系管理员获取许可证密钥，然后使用:\n"
                "/bind_license <许可证密钥>"
            )
            return

        tenant_id = tenant_user['tenant_id']
        tenant = db.fetchone("SELECT * FROM tenants WHERE id = ?", (tenant_id,))

        if not tenant:
            await update.message.reply_text("❌ 许可证信息不存在")
            return

        # 获取统计信息
        stats = self.license_manager.get_tenant_stats(tenant_id)

        license_info = f"""
🔑 **许可证信息**

📋 租户: {tenant['tenant_name']} ({tenant['tenant_code']})
🎫 类型: {tenant['license_type']}
📅 到期时间: {tenant['expire_at'] or '永久'}
📊 状态: {tenant['status']}

📈 **使用情况**
📱 账号数: {stats['accounts_count']} / {tenant['max_accounts']}
🔗 TGAPI会话: {stats['tgapi_sessions_count']} / {tenant['max_tgapi_sessions']}
💻 绑定设备: {stats['devices_count']}

🔐 许可证密钥: `{tenant['license_key']}`
"""

        await update.message.reply_text(license_info, parse_mode='Markdown')

    @require_authorization
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """统计信息命令"""
        stats = db.get_stats()

        stats_text = f"""
📊 **系统统计**

📱 总账号数: {stats['total_accounts']}
✅ 活跃账号: {stats['active_accounts']}
🔗 活跃TGAPI会话: {stats['active_tgapi_sessions']}
📨 今日验证码推送: {stats['today_code_pushes']}
"""

        await update.message.reply_text(stats_text, parse_mode='Markdown')

    @require_authorization
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """按钮回调处理"""
        query = update.callback_query
        await query.answer()

        callback_data = query.data

        if callback_data == "menu_tgapi":
            text = """
📱 **TGAPI 接码功能**

将TG账号协议转换为在线API接码链接

🔸 功能特点:
• 实时验证码推送
• 自定义版权和2FA显示
• 设置过期时间和登录次数限制

📝 使用方法:
1. 发送 /create_tgapi 创建接码链接
2. 提供Session字符串和API凭证
3. 获取在线接码API URL

💡 示例:
/create_tgapi <session> <api_id> <api_hash>
"""

        elif callback_data == "menu_account":
            text = """
🛡️ **账号管理功能**

全方位的TG账号处理工具

🔸 功能模块:
• 防找回 - 修改密码、启用2FA、绑定邮箱
• 筛活 - 批量检测账号状态
• 账号清理 - 清除聊天、退出群组
• 账号维护 - 定期保活操作

📝 使用方法:
/check_account <账号ID> - 检查账号状态
/protect_account <账号ID> - 防找回设置
/clean_account <账号ID> - 清理账号
/maintain_account <账号ID> - 保活操作
"""

        elif callback_data == "menu_convert":
            text = """
🔄 **格式转换功能**

支持多种TG账号格式互转

🔸 支持格式:
• TData ⟷ Session
• Session ⟷ JSON
• Session ⟷ AuthKey
• 全格式互转

📝 使用方法:
1. 上传需要转换的文件
2. 选择输出格式
3. 下载转换后的文件

💡 命令:
/convert <输入格式> <输出格式>
"""

        elif callback_data == "menu_autogen":
            text = """
🔨 **自动做号功能**

基于TGAPI的逆向自动做号工具

🔸 功能说明:
输入 API ID + Hash，自动生成新设备登录
输出多种格式: TData/Session/JSON/密钥

📝 使用方法:
/autogen <api_id> <api_hash> <phone> <输出格式>

💡 示例:
/autogen 12345 abc123... +1234567890 session
"""

        elif callback_data == "menu_stats":
            await self.stats_command(update, context)
            return

        elif callback_data == "menu_license":
            await self.license_command(update, context)
            return

        else:
            text = "功能开发中..."

        await query.edit_message_text(text, parse_mode='Markdown')

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理普通消息"""
        # 处理文件上传（用于格式转换）
        if update.message.document:
            await update.message.reply_text("📁 文件已收到，正在处理...")
            # TODO: 实现文件转换逻辑


async def setup_handlers(application: Application):
    """
    为Application设置handlers
    此函数会被BotPoolManager用于初始化每个bot实例
    """
    # 创建Bot管理器
    bot_manager = TGBotManager()

    # 注册命令处理器
    application.add_handler(CommandHandler("start", bot_manager.start_command))
    application.add_handler(CommandHandler("menu", bot_manager.menu_command))
    application.add_handler(CommandHandler("license", bot_manager.license_command))
    application.add_handler(CommandHandler("stats", bot_manager.stats_command))

    # 注册回调处理器
    application.add_handler(CallbackQueryHandler(bot_manager.button_callback))

    # 注册消息处理器
    application.add_handler(MessageHandler(filters.ALL, bot_manager.handle_message))

    logger.debug("✅ Handlers设置完成")


async def main():
    """主函数 - 支持Bot Pool负载均衡"""
    # 加载环境变量
    load_env_file()

    # 验证配置
    is_valid, errors = settings.validate()
    if not is_valid:
        logger.error("配置验证失败:")
        for error in errors:
            logger.error(f"  {error}")
        return

    # 初始化数据库
    logger.info("正在初始化数据库...")
    db.initialize()

    # 执行bot_pool_schema（如果尚未执行）
    try:
        # 执行Bot Pool schema
        with open("shared/database/bot_pool_schema.sql", 'r', encoding='utf-8') as f:
            schema_sql = f.read()
            # 移除DELIMITER语句（Python DB-API不支持）
            schema_sql = schema_sql.replace('DELIMITER //', '').replace('DELIMITER ;', '')
            for statement in schema_sql.split(';'):
                if statement.strip():
                    db.execute(statement)
        logger.info("✅ Bot Pool schema初始化成功")
    except Exception as e:
        logger.warning(f"执行Bot Pool schema失败（可能已存在）: {str(e)}")

    # 执行授权用户schema（如果尚未执行）
    try:
        with open("shared/database/authorized_users_schema.sql", 'r', encoding='utf-8') as f:
            schema_sql = f.read()
            db.conn.executescript(schema_sql)
            db.conn.commit()
        logger.info("✅ 授权用户schema初始化成功")
    except Exception as e:
        logger.warning(f"执行授权用户schema失败（可能已存在）: {str(e)}")

    # 检查是否启用Bot Pool模式
    use_bot_pool = os.getenv("ENABLE_BOT_POOL", "false").lower() == "true"

    if use_bot_pool:
        logger.info("🚀 启动模式: Bot Pool (负载均衡)")

        # 初始化Redis连接
        redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0)),
            decode_responses=True
        )

        # 创建BotPoolManager
        pool_manager = BotPoolManager(
            redis_client=redis_client,
            handlers_setup_func=setup_handlers,
            lb_strategy=LoadBalanceStrategy.LEAST_CONNECTIONS
        )

        # 初始化Bot池（从数据库加载所有bot配置）
        await pool_manager.initialize()

        # 启动Bot池
        await pool_manager.start()

        # 保持运行
        logger.info("✅ Bot Pool运行中...")
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("收到停止信号，正在关闭...")
            await pool_manager.stop()

    else:
        logger.info("🚀 启动模式: 单Bot (传统)")

        # 传统单Bot模式
        application = Application.builder().token(settings.telegram.bot_token).build()

        # 设置handlers
        await setup_handlers(application)

        # 启动Bot
        logger.info("✅ Bot启动成功！")
        await application.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
