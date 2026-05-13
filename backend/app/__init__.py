# ============================================================
# 应用入口模块
# ============================================================
"""
CoolAI 智能业务平台

这是一个综合性的AI业务平台，提供以下核心能力：
- AI Agent 智能代理
- RAG 知识库增强检索
- TTS 文字转语音
- 声音克隆

Author: CoolAI Team
Date: 2026-05-13
"""

# 统一导入，方便外部调用
from app.core.config import settings
from app.core.database import get_db, engine, async_session_maker
from app.core.security import create_access_token, verify_token

__version__ = "1.0.0"
__all__ = [
    "settings",
    "get_db",
    "engine",
    "async_session_maker",
    "create_access_token",
    "verify_token",
]
