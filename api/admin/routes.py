"""
管理后台路由
"""
from fastapi import APIRouter, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
from datetime import datetime
import json

from .auth import AdminAuth, session_manager, login_tracker
from shared.database.init import db
from shared.utils.logger import logger
from shared.utils.proxy_manager import proxy_pool, ProxyManager
from shared.utils.license import LicenseManager
from shared.utils.authorization import auth_manager
from modules.tgapi.core import tgapi_manager

# 创建路由
admin_router = APIRouter(prefix="/admin", tags=["admin"])

# 模板引擎
templates = Jinja2Templates(directory="api/templates")

# 许可证管理器
license_manager = LicenseManager(db)


# ==================== 认证相关 ====================

@admin_router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """登录页面"""
    # 如果已登录，重定向到首页
    user = AdminAuth.get_current_user(request)
    if user:
        return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse("admin/login.html", {
        "request": request,
        "error": None
    })


@admin_router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    remember: bool = Form(False)
):
    """处理登录（带防爆破机制）"""
    # 获取客户端IP
    client_ip = request.client.host

    # 检查IP是否被锁定
    ip_locked, ip_message = login_tracker.is_locked(client_ip)
    if ip_locked:
        logger.warning(f"🔒 IP锁定尝试登录: {client_ip}")
        return templates.TemplateResponse("admin/login.html", {
            "request": request,
            "error": ip_message
        })

    # 检查用户名是否被锁定
    username_locked, username_message = login_tracker.is_locked(f"user:{username}")
    if username_locked:
        logger.warning(f"🔒 用户锁定尝试登录: {username}")
        return templates.TemplateResponse("admin/login.html", {
            "request": request,
            "error": username_message
        })

    # 尝试登录
    success, result, role = AdminAuth.login(username, password)

    if not success:
        # 登录失败，记录尝试
        login_tracker.record_attempt(client_ip)
        login_tracker.record_attempt(f"user:{username}")

        logger.warning(f"⚠️ 登录失败: {username} from {client_ip}")

        return templates.TemplateResponse("admin/login.html", {
            "request": request,
            "error": result
        })

    # 登录成功，清除尝试记录
    login_tracker.clear_attempts(client_ip)
    login_tracker.clear_attempts(f"user:{username}")

    logger.info(f"✅ 登录成功: {username} from {client_ip}")

    # 设置cookie
    response = RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="session_id",
        value=result,
        httponly=True,
        max_age=86400 * 30 if remember else 86400  # 30天 or 1天
    )
    return response


@admin_router.get("/logout")
async def logout(request: Request):
    """登出"""
    session_id = request.cookies.get("session_id")
    if session_id:
        AdminAuth.logout(session_id)

    response = RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("session_id")
    return response


# ==================== 首页 ====================

@admin_router.get("/", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """管理后台首页"""
    user = AdminAuth.get_current_user(request)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)

    # 获取统计数据
    stats = db.get_stats()

    # 获取代理池信息
    proxy_stats = {
        "count": proxy_pool.count(),
        "proxies": proxy_pool.list_proxies()
    }

    # 获取活跃的TGAPI会话
    active_sessions = db.fetchall(
        "SELECT COUNT(*) as count FROM tgapi_sessions WHERE status = 'active'"
    )[0]["count"]

    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "user": user,
        "stats": stats,
        "proxy_stats": proxy_stats,
        "active_sessions": active_sessions,
        "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })


# ==================== 代理管理 ====================

@admin_router.get("/proxies", response_class=HTMLResponse)
async def proxy_list(request: Request):
    """代理列表页面"""
    user = AdminAuth.get_current_user(request)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)

    proxies = proxy_pool.proxies
    return templates.TemplateResponse("admin/proxies.html", {
        "request": request,
        "user": user,
        "proxies": proxies,
        "count": len(proxies)
    })


@admin_router.post("/proxies/add")
async def add_proxy(
    request: Request,
    proxy_link: str = Form(...),
    proxy_type: str = Form("mtproto")
):
    """添加代理"""
    user = AdminAuth.get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "message": "未认证"}, status_code=401)

    try:
        if proxy_type == "mtproto":
            success = proxy_pool.add_mtproxy_link(proxy_link)
            if success:
                logger.info(f"✅ 管理员 {user} 添加MTProxy代理")
                return JSONResponse({"success": True, "message": "代理添加成功"})
            else:
                return JSONResponse({"success": False, "message": "代理链接格式错误"})

        elif proxy_type == "socks5":
            proxy_config = ProxyManager.parse_socks5_string(proxy_link)
            if proxy_config:
                proxy_pool.add_proxy(proxy_config)
                logger.info(f"✅ 管理员 {user} 添加SOCKS5代理")
                return JSONResponse({"success": True, "message": "代理添加成功"})
            else:
                return JSONResponse({"success": False, "message": "代理链接格式错误"})

        else:
            return JSONResponse({"success": False, "message": "不支持的代理类型"})

    except Exception as e:
        logger.error(f"添加代理失败: {str(e)}")
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)


@admin_router.post("/proxies/remove")
async def remove_proxy(
    request: Request,
    server: str = Form(...),
    port: int = Form(...)
):
    """删除代理"""
    user = AdminAuth.get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "message": "未认证"}, status_code=401)

    try:
        proxy_pool.remove_proxy(server, port)
        logger.info(f"✅ 管理员 {user} 删除代理: {server}:{port}")
        return JSONResponse({"success": True, "message": "代理删除成功"})
    except Exception as e:
        logger.error(f"删除代理失败: {str(e)}")
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)


@admin_router.post("/proxies/test")
async def test_proxy(
    request: Request,
    server: str = Form(...),
    port: int = Form(...),
    secret: str = Form(...)
):
    """测试代理"""
    user = AdminAuth.get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "message": "未认证"}, status_code=401)

    try:
        # TODO: 实现代理测试
        # 需要API ID和API Hash才能测试
        return JSONResponse({"success": True, "message": "代理测试功能开发中"})
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)


# ==================== 租户管理 ====================

@admin_router.get("/tenants", response_class=HTMLResponse)
async def tenant_list(request: Request):
    """租户列表"""
    user = AdminAuth.get_current_user(request)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)

    # 获取所有租户
    tenants = db.fetchall("SELECT * FROM tenants ORDER BY created_at DESC")

    return templates.TemplateResponse("admin/tenants.html", {
        "request": request,
        "user": user,
        "tenants": [dict(t) for t in tenants] if tenants else []
    })


@admin_router.post("/tenants/create")
async def create_tenant(
    request: Request,
    tenant_code: str = Form(...),
    tenant_name: str = Form(...),
    license_type: str = Form(...),
    max_accounts: int = Form(10),
    max_tgapi_sessions: int = Form(5)
):
    """创建租户"""
    user = AdminAuth.get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "message": "未认证"}, status_code=401)

    try:
        # 生成许可证
        license_key = license_manager.generate_license(
            tenant_code=tenant_code,
            tenant_name=tenant_name,
            license_type=license_type,
            max_accounts=max_accounts,
            max_tgapi_sessions=max_tgapi_sessions
        )

        logger.info(f"✅ 管理员 {user} 创建租户: {tenant_code}")
        return JSONResponse({
            "success": True,
            "message": "租户创建成功",
            "license_key": license_key
        })
    except Exception as e:
        logger.error(f"创建租户失败: {str(e)}")
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)


# ==================== 用户授权管理 ====================

@admin_router.get("/users", response_class=HTMLResponse)
async def authorized_users_list(request: Request, status_filter: Optional[str] = None):
    """授权用户列表"""
    user = AdminAuth.get_current_user(request)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)

    # 获取授权用户列表
    users = auth_manager.get_all_users(status=status_filter)

    # 获取未授权访问日志（最近50条）
    unauth_logs = db.fetchall(
        "SELECT * FROM unauthorized_access_logs ORDER BY access_time DESC LIMIT 50"
    )

    return templates.TemplateResponse("admin/authorized_users.html", {
        "request": request,
        "user": user,
        "users": users,
        "unauth_logs": [dict(l) for l in unauth_logs] if unauth_logs else [],
        "status_filter": status_filter
    })


@admin_router.post("/users/authorize")
async def authorize_user(
    request: Request,
    telegram_id: int = Form(...),
    username: str = Form(None),
    full_name: str = Form(None),
    duration_type: str = Form(...),
    authorization_level: str = Form('basic'),
    max_accounts: int = Form(10),
    max_tgapi_sessions: int = Form(5),
    payment_info: str = Form(None),
    notes: str = Form(None)
):
    """授权用户"""
    admin_user = AdminAuth.get_current_user(request)
    if not admin_user:
        return JSONResponse({"success": False, "message": "未认证"}, status_code=401)

    try:
        success, message = auth_manager.authorize_user(
            telegram_id=telegram_id,
            duration_type=duration_type,
            username=username,
            full_name=full_name,
            authorization_level=authorization_level,
            max_accounts=max_accounts,
            max_tgapi_sessions=max_tgapi_sessions,
            authorized_by=admin_user,
            payment_info=payment_info,
            notes=notes
        )

        if success:
            logger.info(f"✅ 管理员 {admin_user} 授权用户: {telegram_id}")
            return JSONResponse({"success": True, "message": message})
        else:
            return JSONResponse({"success": False, "message": message})

    except Exception as e:
        logger.error(f"授权用户失败: {str(e)}")
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)


@admin_router.post("/users/{telegram_id}/suspend")
async def suspend_user(request: Request, telegram_id: int, notes: str = Form(None)):
    """暂停用户授权"""
    admin_user = AdminAuth.get_current_user(request)
    if not admin_user:
        return JSONResponse({"success": False, "message": "未认证"}, status_code=401)

    try:
        success, message = auth_manager.suspend_user(
            telegram_id=telegram_id,
            operated_by=admin_user,
            notes=notes
        )

        if success:
            logger.info(f"✅ 管理员 {admin_user} 暂停用户: {telegram_id}")
            return JSONResponse({"success": True, "message": message})
        else:
            return JSONResponse({"success": False, "message": message})

    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)


@admin_router.post("/users/{telegram_id}/activate")
async def activate_user(request: Request, telegram_id: int, notes: str = Form(None)):
    """激活用户授权"""
    admin_user = AdminAuth.get_current_user(request)
    if not admin_user:
        return JSONResponse({"success": False, "message": "未认证"}, status_code=401)

    try:
        success, message = auth_manager.activate_user(
            telegram_id=telegram_id,
            operated_by=admin_user,
            notes=notes
        )

        if success:
            logger.info(f"✅ 管理员 {admin_user} 激活用户: {telegram_id}")
            return JSONResponse({"success": True, "message": message})
        else:
            return JSONResponse({"success": False, "message": message})

    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)


# ==================== 账号管理 ====================

@admin_router.get("/accounts", response_class=HTMLResponse)
async def account_list(
    request: Request,
    status_filter: Optional[str] = None,
    tenant_id: Optional[int] = None,
    search: Optional[str] = None,
    page: int = 1,
    per_page: int = 50
):
    """账号列表（增强版 - 支持高级搜索）"""
    user = AdminAuth.get_current_user(request)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)

    # 构建查询条件
    conditions = []
    params = []

    if status_filter:
        conditions.append("status = ?")
        params.append(status_filter)

    if tenant_id:
        conditions.append("tenant_id = ?")
        params.append(tenant_id)

    if search:
        conditions.append("(phone LIKE ? OR username LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    # 组装SQL
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    offset = (page - 1) * per_page

    # 获取总数
    count_sql = f"SELECT COUNT(*) as total FROM accounts WHERE {where_clause}"
    total = db.fetchone(count_sql, tuple(params))["total"] if params else \
            db.fetchone("SELECT COUNT(*) as total FROM accounts")["total"]

    # 获取账号列表
    query = f"""
        SELECT * FROM accounts
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    """
    params.extend([per_page, offset])
    accounts = db.fetchall(query, tuple(params)) if params else \
               db.fetchall(f"SELECT * FROM accounts ORDER BY created_at DESC LIMIT ? OFFSET ?", (per_page, offset))

    # 获取所有租户（用于筛选下拉框） - 使用authorized_users表
    tenants = db.fetchall("SELECT id, telegram_id, username, full_name FROM authorized_users ORDER BY created_at DESC")

    # 为账号添加租户信息
    accounts_list = []
    if accounts:
        for account in accounts:
            account_dict = dict(account)
            # 查找租户信息
            if account_dict.get('tenant_id'):
                tenant_info = db.fetchone("SELECT full_name, username FROM authorized_users WHERE id = ?", (account_dict['tenant_id'],))
                if tenant_info:
                    account_dict['tenant_full_name'] = tenant_info['full_name'] or tenant_info['username']
            accounts_list.append(account_dict)

    # 计算总页数
    total_pages = (total + per_page - 1) // per_page

    return templates.TemplateResponse("admin/accounts.html", {
        "request": request,
        "user": user,
        "accounts": accounts_list,
        "tenants": [dict(t) for t in tenants] if tenants else [],
        "status_filter": status_filter,
        "tenant_id": tenant_id,
        "search": search,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages
    })


@admin_router.get("/accounts/{account_id}", response_class=HTMLResponse)
async def account_detail(request: Request, account_id: int):
    """账号详情页"""
    user = AdminAuth.get_current_user(request)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)

    # 获取账号信息
    account = db.fetchone("SELECT * FROM accounts WHERE id = ?", (account_id,))
    if not account:
        return templates.TemplateResponse("admin/error.html", {
            "request": request,
            "user": user,
            "error": "账号不存在"
        })

    account_dict = dict(account)

    # 解析JSON数据
    import json
    if account_dict.get('session_data'):
        try:
            account_dict['session_data_parsed'] = json.loads(account_dict['session_data'])
        except:
            account_dict['session_data_parsed'] = {}

    # 获取租户信息（从authorized_users表）
    tenant = None
    if account_dict.get('tenant_id'):
        tenant = db.fetchone("SELECT * FROM authorized_users WHERE id = ?", (account_dict['tenant_id'],))

    # 获取相关的TGAPI会话
    tgapi_sessions = db.fetchall(
        "SELECT * FROM tgapi_sessions WHERE account_id = ? ORDER BY created_at DESC",
        (account_id,)
    )

    # 获取操作日志（假设logs表存在，如果不存在会返回空列表）
    logs = []
    try:
        logs = db.fetchall(
            """SELECT timestamp, action, operator, details FROM logs
               WHERE details LIKE ?
               ORDER BY timestamp DESC LIMIT 20""",
            (f"%account:{account_id}%",)
        )
    except:
        # 如果logs表不存在，返回空列表
        pass

    return templates.TemplateResponse("admin/account_detail.html", {
        "request": request,
        "user": user,
        "account": account_dict,
        "session_data_parsed": account_dict.get('session_data_parsed'),
        "tenant": dict(tenant) if tenant else None,
        "tgapi_sessions": [dict(s) for s in tgapi_sessions] if tgapi_sessions else [],
        "logs": [dict(l) for l in logs] if logs else []
    })


@admin_router.post("/accounts/bulk-delete")
async def bulk_delete_accounts(request: Request, account_ids: str = Form(...)):
    """批量删除账号"""
    user = AdminAuth.get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "message": "未认证"}, status_code=401)

    try:
        ids = [int(id.strip()) for id in account_ids.split(",") if id.strip()]

        for account_id in ids:
            db.execute("DELETE FROM accounts WHERE id = ?", (account_id,))

        logger.info(f"✅ 管理员 {user} 批量删除账号: {len(ids)}个")
        return JSONResponse({"success": True, "message": f"成功删除 {len(ids)} 个账号"})

    except Exception as e:
        logger.error(f"批量删除账号失败: {str(e)}")
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)


@admin_router.get("/accounts/export")
async def export_accounts(
    request: Request,
    status_filter: Optional[str] = None,
    tenant_id: Optional[int] = None
):
    """导出账号（CSV格式）"""
    user = AdminAuth.get_current_user(request)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)

    try:
        # 构建查询条件
        conditions = []
        params = []

        if status_filter:
            conditions.append("status = ?")
            params.append(status_filter)

        if tenant_id:
            conditions.append("tenant_id = ?")
            params.append(tenant_id)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # 获取账号数据
        query = f"SELECT * FROM accounts WHERE {where_clause} ORDER BY created_at DESC"
        accounts = db.fetchall(query, tuple(params)) if params else db.fetchall(query)

        # 生成CSV
        import csv
        import io
        from fastapi.responses import StreamingResponse

        output = io.StringIO()
        writer = csv.writer(output)

        # 写入表头
        writer.writerow(['ID', '手机号', '用户名', 'Session类型', '状态', '创建时间', '最后检查'])

        # 写入数据
        for account in accounts:
            writer.writerow([
                account['id'],
                account['phone'],
                account.get('username', ''),
                account['session_type'],
                account['status'],
                account['created_at'],
                account.get('last_check', '')
            ])

        output.seek(0)
        logger.info(f"✅ 管理员 {user} 导出账号: {len(accounts)}个")

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=accounts_export.csv"}
        )

    except Exception as e:
        logger.error(f"导出账号失败: {str(e)}")
        return templates.TemplateResponse("admin/error.html", {
            "request": request,
            "user": user,
            "error": f"导出失败: {str(e)}"
        })


# ==================== TGAPI会话管理 ====================

@admin_router.get("/tgapi-sessions", response_class=HTMLResponse)
async def tgapi_sessions(request: Request):
    """TGAPI会话列表"""
    user = AdminAuth.get_current_user(request)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)

    # 获取TGAPI会话
    sessions = db.fetchall(
        "SELECT * FROM tgapi_sessions ORDER BY created_at DESC LIMIT 100"
    )

    return templates.TemplateResponse("admin/tgapi_sessions.html", {
        "request": request,
        "user": user,
        "sessions": [dict(s) for s in sessions] if sessions else []
    })


@admin_router.post("/tgapi-sessions/{session_id}/disable")
async def disable_tgapi_session(request: Request, session_id: int):
    """禁用TGAPI会话"""
    user = AdminAuth.get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "message": "未认证"}, status_code=401)

    try:
        db.execute(
            "UPDATE tgapi_sessions SET status = 'disabled' WHERE id = ?",
            (session_id,)
        )
        logger.info(f"✅ 管理员 {user} 禁用TGAPI会话: {session_id}")
        return JSONResponse({"success": True, "message": "会话已禁用"})
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)


# ==================== 许可证管理 ====================

@admin_router.get("/licenses", response_class=HTMLResponse)
async def license_list(request: Request):
    """许可证列表"""
    user = AdminAuth.get_current_user(request)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)

    # 获取所有租户（含许可证信息）
    tenants = db.fetchall("SELECT * FROM tenants ORDER BY created_at DESC")

    return templates.TemplateResponse("admin/licenses.html", {
        "request": request,
        "user": user,
        "licenses": [dict(t) for t in tenants] if tenants else []
    })


# ==================== 系统日志 ====================

@admin_router.get("/logs", response_class=HTMLResponse)
async def system_logs(request: Request, log_type: str = "operation"):
    """系统日志"""
    user = AdminAuth.get_current_user(request)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)

    # 获取日志
    if log_type == "operation":
        logs = db.fetchall(
            "SELECT * FROM operation_logs ORDER BY created_at DESC LIMIT 200"
        )
    else:
        logs = []

    return templates.TemplateResponse("admin/logs.html", {
        "request": request,
        "user": user,
        "logs": [dict(l) for l in logs] if logs else [],
        "log_type": log_type
    })


# ==================== 系统设置 ====================

@admin_router.get("/settings", response_class=HTMLResponse)
async def system_settings(request: Request):
    """系统设置"""
    user = AdminAuth.get_current_user(request)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)

    from shared.config.settings import settings

    return templates.TemplateResponse("admin/settings.html", {
        "request": request,
        "user": user,
        "settings": {
            "database_type": settings.database.type,
            "server_host": settings.server.host,
            "server_port": settings.server.port,
            "tgapi_base_url": settings.tgapi.base_url
        }
    })


# ==================== API接口（JSON） ====================

@admin_router.get("/api/stats")
async def get_admin_stats(request: Request):
    """获取统计数据（API）"""
    user = AdminAuth.get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "message": "未认证"}, status_code=401)

    try:
        stats = db.get_stats()
        return JSONResponse({"success": True, "stats": stats})
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)
