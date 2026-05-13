# ============================================================
# CoolAI 智能业务平台 - FastAPI 主应用入口
# ============================================================
#
# 本文件是整个应用的主入口点
# 负责：
# 1. 创建FastAPI应用实例
# 2. 配置中间件
# 3. 注册路由
# 4. 配置CORS
# 5. 启动事件处理
#
# 启动方式：
# 1. 开发环境：uvicorn app.main:app --reload
# 2. 生产环境：uvicorn app.main:app --host 0.0.0.0 --port 8000
#
# Author: CoolAI Team
# Date: 2026-05-13
# ============================================================

import logging
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.config import settings
from app.core.database import init_db, engine
from app.api import api_router


# ============================================================
# 日志配置
# ============================================================

# 配置根日志记录器
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================
# 应用生命周期管理
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理器
    
    处理应用启动和关闭时的资源管理
    - 启动时：初始化数据库、加载配置
    - 关闭时：清理资源、关闭连接
    
    使用方式：
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 启动时的代码
        await init_db()
        yield
        # 关闭时的代码
        await cleanup()
    """
    # ============================================================
    # 应用启动时执行
    # ============================================================
    logger.info(f"启动 {settings.APP_NAME} ...")
    
    # 初始化数据库
    try:
        await init_db()
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
    
    # 其他启动任务可以在这里添加
    # 例如：初始化缓存、预加载模型等
    
    logger.info(f"{settings.APP_NAME} 启动成功！")
    
    # yield 之后的代码将在应用关闭时执行
    yield
    
    # ============================================================
    # 应用关闭时执行
    # ============================================================
    logger.info("正在关闭应用...")
    
    # 关闭数据库连接
    await engine.dispose()
    logger.info("数据库连接已关闭")
    
    logger.info("应用已关闭")


# ============================================================
# 创建FastAPI应用
# ============================================================

# 创建应用实例
# title: API文档标题
# description: API文档描述
# version: API版本
# docs_url: API文档路径
# redoc_url: ReDoc文档路径
app = FastAPI(
    title=settings.APP_NAME,
    description="""
## CoolAI 智能业务平台 API

这是一个综合性的AI业务平台，提供以下核心能力：

### 核心功能
- 🤖 **AI Agent** - 智能代理，支持多种推理模式
- 📚 **RAG知识库** - 检索增强生成，支持文档问答
- 🔊 **TTS语音合成** - 文字转语音，多种音色可选
- 🎤 **声音克隆** - 个性化声音定制

### 技术栈
- FastAPI - 高性能异步Web框架
- SQLAlchemy - 数据库ORM
- LangChain - AI应用开发框架
- PostgreSQL - 关系型数据库
- Milvus - 向量数据库

### 认证方式
所有需要认证的接口，请在请求头中携带JWT令牌：
```
Authorization: Bearer <your_token>
```
    """,
    version="1.0.0",
    docs_url="/docs",           # Swagger UI
    redoc_url="/redoc",         # ReDoc文档
    openapi_url="/openapi.json",  # OpenAPI Schema
    lifespan=lifespan,          # 生命周期管理
)


# ============================================================
# CORS跨域配置
# ============================================================

# 添加CORS中间件
# 允许前端跨域访问API
app.add_middleware(
    CORSMiddleware,
    # 允许的来源列表
    allow_origins=settings.CORS_ORIGINS,
    # 是否允许携带凭证（cookies）
    allow_credentials=True,
    # 允许的HTTP方法
    allow_methods=settings.CORS_ALLOW_METHODS,
    # 允许的HTTP头
    allow_headers=settings.CORS_ALLOW_HEADERS,
)


# ============================================================
# Prometheus监控
# ============================================================

# 添加Prometheus指标中间件
# 自动收集请求数量、延迟等指标
if settings.ENABLE_METRICS:
    Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        should_respect_env_var=True,
        should_instrument_requests_inprogress=True,
        excluded_handlers=["/metrics", "/health"],
        inprogress_name="http_requests_inprogress",
        inprogress_labels=True,
    ).instrument(app).expose(app, endpoint=settings.METRICS_PATH)


# ============================================================
# 全局异常处理
# ============================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    全局异常处理器
    
    捕获所有未处理的异常，返回统一的错误响应
    
    Args:
        request: 请求对象
        exc: 异常对象
        
    Returns:
        JSONResponse: 错误响应
    """
    logger.error(f"未处理的异常: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "服务器内部错误",
            "detail": str(exc) if settings.DEBUG else None,
        }
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """
    值错误异常处理器
    
    处理参数验证失败等错误
    
    Args:
        request: 请求对象
        exc: 异常对象
        
    Returns:
        JSONResponse: 错误响应
    """
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "success": False,
            "error": "参数错误",
            "detail": str(exc),
        }
    )


# ============================================================
# 注册路由
# ============================================================

# 注册API v1路由
# 所有API将以 /api/v1 开头
app.include_router(
    api_router,
    prefix=settings.API_V1_PREFIX,
)


# ============================================================
# 根路径
# ============================================================

@app.get("/", tags=["首页"])
async def root():
    """
    根路径
    
    返回欢迎信息和API基本信息
    """
    return {
        "name": settings.APP_NAME,
        "version": "1.0.0",
        "description": "综合性的AI业务平台",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
    }


# ============================================================
# 健康检查（不需认证）
# ============================================================

@app.get("/health", tags=["系统"])
async def health_check():
    """
    健康检查端点
    
    用于负载均衡器和容器编排探针
    返回简单的状态信息
    """
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
    }


# ============================================================
# 应用入口（仅用于本地测试）
# ============================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
