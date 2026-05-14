# ============================================================
# API v1 路由汇总
# ============================================================
"""
导出所有v1版本的API路由
"""

from fastapi import APIRouter

from app.api.v1 import auth, chat, system, knowledge, tts, voice

# 创建主API路由
api_router = APIRouter()

# 注册子路由
api_router.include_router(auth.router)
api_router.include_router(chat.router)
api_router.include_router(knowledge.router)
api_router.include_router(tts.router)
api_router.include_router(voice.router)
api_router.include_router(system.router)

__all__ = ["api_router"]
