"""
REST API 服务器 - 提供TGAPI验证码获取接口 + 管理后台
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import uvicorn

from shared.config.settings import settings, load_env_file
from shared.database.init import db
from shared.utils.logger import logger
from shared.utils.license import LicenseManager

from modules.tgapi.core import tgapi_manager

# 导入管理后台
from api.admin import admin_router, start_session_cleanup


# FastAPI应用
app = FastAPI(
    title="TG Bot Manager API",
    description="Telegram账号管理系统 API + Web管理后台",
    version="1.0.0"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 集成管理后台路由
app.include_router(admin_router)

# 许可证管理器
license_manager = LicenseManager(db)


# ==================== 数据模型 ====================

class CodeResponse(BaseModel):
    """验证码响应模型"""
    success: bool
    code: Optional[str] = None
    message: Optional[str] = None
    type: Optional[str] = "code"  # 'code' 或 '2fa'
    timestamp: Optional[str] = None


class CreateTGAPIRequest(BaseModel):
    """创建TGAPI请求模型"""
    session_string: str
    api_id: int
    api_hash: str
    tenant_id: Optional[int] = None
    expire_hours: int = 24
    max_login: int = -1
    custom_copyright: Optional[str] = None


class LicenseValidateRequest(BaseModel):
    """许可证验证请求"""
    license_key: str
    machine_id: Optional[str] = None


# ==================== API路由 ====================

@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "TG Bot Manager API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    try:
        # 检查数据库连接
        stats = db.get_stats()
        return {
            "status": "healthy",
            "database": "connected",
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")


@app.get("/api/code/{api_token}")
async def get_verification_code(api_token: str, request: Request, timeout: int = 60):
    """
    获取验证码 - TGAPI核心接口

    Args:
        api_token: API Token
        timeout: 超时时间（秒）
    """
    try:
        # 获取客户端IP
        client_ip = request.client.host

        logger.info(f"📨 收到验证码请求: {api_token} (IP: {client_ip})")

        # 获取验证码
        code_data = await tgapi_manager.get_latest_code(api_token, timeout=timeout)

        if "error" in code_data:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": code_data["error"]
                }
            )

        # 检查是否是2FA消息
        if code_data.get("type") == "2fa":
            return JSONResponse(
                content={
                    "success": True,
                    "type": "2fa",
                    "message": code_data.get("message"),
                    "timestamp": code_data.get("time")
                }
            )

        # 返回验证码
        return JSONResponse(
            content={
                "success": True,
                "code": code_data.get("code"),
                "message": "验证码获取成功",
                "timestamp": code_data.get("time")
            }
        )

    except Exception as e:
        logger.error(f"获取验证码失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tgapi/create")
async def create_tgapi_link(request: CreateTGAPIRequest):
    """
    创建TGAPI链接

    Args:
        request: 创建请求
    """
    try:
        # 使用配置的API基础URL
        base_url = settings.tgapi.base_url

        success, result, token = await tgapi_manager.create_api_link(
            session_string=request.session_string,
            api_id=request.api_id,
            api_hash=request.api_hash,
            tenant_id=request.tenant_id,
            expire_hours=request.expire_hours,
            max_login=request.max_login,
            custom_copyright=request.custom_copyright,
            base_url=base_url
        )

        if success:
            return {
                "success": True,
                "api_url": result,
                "api_token": token,
                "message": "TGAPI链接创建成功"
            }
        else:
            raise HTTPException(status_code=400, detail=result)

    except Exception as e:
        logger.error(f"创建TGAPI链接失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/license/validate")
async def validate_license(request: LicenseValidateRequest, http_request: Request):
    """
    验证许可证

    Args:
        request: 验证请求
        http_request: HTTP请求对象
    """
    try:
        client_ip = http_request.client.host

        valid, msg, tenant_info = license_manager.validate_license(
            license_key=request.license_key,
            machine_id=request.machine_id,
            ip_address=client_ip
        )

        if valid:
            return {
                "success": True,
                "message": msg,
                "tenant": tenant_info
            }
        else:
            return JSONResponse(
                status_code=403,
                content={
                    "success": False,
                    "message": msg
                }
            )

    except Exception as e:
        logger.error(f"许可证验证失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
async def get_stats():
    """获取系统统计信息"""
    try:
        stats = db.get_stats()
        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tgapi/sessions")
async def list_tgapi_sessions(status: Optional[str] = None):
    """
    列出TGAPI会话

    Args:
        status: 筛选状态 ('active', 'expired', 'disabled')
    """
    try:
        if status:
            query = "SELECT * FROM tgapi_sessions WHERE status = ? ORDER BY created_at DESC"
            sessions = db.fetchall(query, (status,))
        else:
            query = "SELECT * FROM tgapi_sessions ORDER BY created_at DESC"
            sessions = db.fetchall(query)

        sessions_list = [dict(session) for session in sessions]

        return {
            "success": True,
            "count": len(sessions_list),
            "sessions": sessions_list
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 启动服务 ====================

def start_server():
    """启动API服务器 + Web管理后台"""
    # 加载环境变量
    load_env_file()

    # 初始化数据库
    logger.info("正在初始化数据库...")
    db.initialize()

    # 执行租户schema
    try:
        with open("shared/database/tenant_schema.sql", 'r', encoding='utf-8') as f:
            schema_sql = f.read()
            db.conn.executescript(schema_sql)
            db.conn.commit()
    except Exception as e:
        logger.warning(f"执行租户schema失败（可能已存在）: {str(e)}")

    # 启动会话清理任务
    logger.info("启动管理后台会话清理任务...")
    start_session_cleanup()

    # 启动服务器
    logger.info(f"🚀 启动API服务器 + Web管理后台")
    logger.info(f"   API地址: http://{settings.server.host}:{settings.server.port}")
    logger.info(f"   管理后台: http://{settings.server.host}:{settings.server.port}/admin")
    logger.info(f"   默认账号: admin / admin123")

    uvicorn.run(
        "api.server:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=settings.server.debug,
        log_level="info"
    )


if __name__ == "__main__":
    start_server()
