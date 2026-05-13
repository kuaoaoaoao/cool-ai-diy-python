# ============================================================
# 系统管理API路由
# ============================================================
#
# 本模块处理系统管理和监控相关的API接口
#
# 主要功能：
# 1. 健康检查
# 2. 系统统计
# 3. 模型列表
# 4. 系统配置
#
# Author: CoolAI Team
# Date: 2026-05-13
# ============================================================

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.config import settings
from app.models import User, Conversation, Message, KnowledgeBase, Document
from app.schemas import (
    HealthResponse,
    StatsResponse,
    ModelInfo,
    ModelListResponse,
)


# ============================================================
# 路由配置
# ============================================================

router = APIRouter(
    prefix="/system",
    tags=["系统管理"],
    summary="系统管理与监控接口",
)


# ============================================================
# 健康检查
# ============================================================

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="健康检查",
    description="检查系统各组件的健康状态",
)
async def health_check(
    db: AsyncSession = Depends(get_db)
):
    """
    系统健康检查
    
    检查数据库、Redis、Milvus等组件的连接状态
    
    Args:
        db: 数据库会话
        
    Returns:
        HealthResponse: 健康状态
    """
    # 检查数据库
    db_status = "healthy"
    try:
        await db.execute("SELECT 1")
    except Exception:
        db_status = "unhealthy"
    
    # Redis和Milvus状态（简化版，实际应该真正检查）
    redis_status = "unknown"
    milvus_status = "unknown"
    
    return HealthResponse(
        status="healthy" if db_status == "healthy" else "degraded",
        version="1.0.0",
        database=db_status,
        redis=redis_status,
        milvus=milvus_status,
    )


# ============================================================
# 统计数据
# ============================================================

@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="系统统计",
    description="获取系统的使用统计数据",
)
async def get_stats(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取系统统计数据
    
    返回用户相关的统计数据
    
    Args:
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        StatsResponse: 统计数据
    """
    # 只统计当前用户的数据
    user_id = current_user["user_id"]
    
    # 用户数量（管理员可以看到所有用户）
    if current_user.get("role") == "admin":
        stmt = select(func.count(User.id))
        result = await db.execute(stmt)
        total_users = result.scalar() or 0
    else:
        total_users = 1
    
    # 会话数量
    stmt = select(func.count(Conversation.id)).where(
        Conversation.user_id == user_id
    )
    result = await db.execute(stmt)
    total_conversations = result.scalar() or 0
    
    # 消息数量
    stmt = (
        select(func.count(Message.id))
        .join(Conversation)
        .where(Conversation.user_id == user_id)
    )
    result = await db.execute(stmt)
    total_messages = result.scalar() or 0
    
    # 知识库数量
    stmt = select(func.count(KnowledgeBase.id)).where(
        KnowledgeBase.user_id == user_id
    )
    result = await db.execute(stmt)
    total_knowledge_bases = result.scalar() or 0
    
    # 文档数量
    stmt = (
        select(func.count(Document.id))
        .join(KnowledgeBase)
        .where(KnowledgeBase.user_id == user_id)
    )
    result = await db.execute(stmt)
    total_documents = result.scalar() or 0
    
    return StatsResponse(
        total_users=total_users,
        total_conversations=total_conversations,
        total_messages=total_messages,
        total_knowledge_bases=total_knowledge_bases,
        total_documents=total_documents,
    )


# ============================================================
# 模型列表
# ============================================================

@router.get(
    "/models",
    response_model=ModelListResponse,
    summary="获取模型列表",
    description="获取所有可用的AI模型",
)
async def list_models(
    current_user: dict = Depends(get_current_user)
):
    """
    获取可用的AI模型列表
    
    返回系统中配置的所有AI模型信息
    
    Args:
        current_user: 当前用户
        
    Returns:
        ModelListResponse: 模型列表
    """
    # 定义可用的模型
    models = [
        ModelInfo(
            name="gpt-4-turbo-preview",
            display_name="GPT-4 Turbo",
            provider="OpenAI",
            description="最新的GPT-4模型，支持128K上下文",
            is_available=bool(settings.OPENAI_API_KEY),
        ),
        ModelInfo(
            name="gpt-3.5-turbo",
            display_name="GPT-3.5 Turbo",
            provider="OpenAI",
            description="快速、经济的对话模型",
            is_available=bool(settings.OPENAI_API_KEY),
        ),
        ModelInfo(
            name="claude-3-opus-20240229",
            display_name="Claude 3 Opus",
            provider="Anthropic",
            description="最强大的Claude模型",
            is_available=bool(settings.ANTHROPIC_API_KEY),
        ),
        ModelInfo(
            name="claude-3-sonnet-20240229",
            display_name="Claude 3 Sonnet",
            provider="Anthropic",
            description="平衡性能与成本的模型",
            is_available=bool(settings.ANTHROPIC_API_KEY),
        ),
        ModelInfo(
            name="chatglm3-6b",
            display_name="ChatGLM3-6B",
            provider="Zhipu AI",
            description="开源中文对话模型",
            is_available=True,  # 本地模型总是可用
        ),
        ModelInfo(
            name="qwen2-7b",
            display_name="Qwen2-7B",
            provider="Alibaba",
            description="阿里通义千问开源模型",
            is_available=True,
        ),
    ]
    
    return ModelListResponse(models=models)


# ============================================================
# 获取配置
# ============================================================

@router.get(
    "/config",
    summary="获取系统配置",
    description="获取系统的公开配置信息",
)
async def get_config():
    """
    获取系统配置
    
    返回公开的配置信息（不包含敏感数据）
    
    Returns:
        dict: 配置字典
    """
    return {
        "app_name": settings.APP_NAME,
        "version": "1.0.0",
        "debug": settings.DEBUG,
        "supported_file_types": settings.ALLOWED_DOCUMENT_TYPES,
        "max_file_size_mb": settings.MAX_FILE_SIZE // (1024 * 1024),
        "default_model": settings.OPENAI_MODEL,
        "embedding_model": settings.EMBEDDING_MODEL,
        "rag_chunk_size": settings.RAG_CHUNK_SIZE,
        "rag_top_k": settings.RAG_TOP_K,
    }
