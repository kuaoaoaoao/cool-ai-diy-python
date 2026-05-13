# ============================================================
# 模型模块导出
# ============================================================
"""
导出所有数据库模型，方便其他模块导入使用
"""

from app.models.models import (
    Base,                    # SQLAlchemy基类
    User,                    # 用户模型
    Conversation,            # 对话会话模型
    Message,                  # 消息记录模型
    KnowledgeBase,            # 知识库模型
    Document,                 # 文档模型
    Chunk,                    # 文本块模型
    VoiceModel,               # 声音模型
    TTSTask,                  # TTS任务模型
    OperationLog,             # 操作日志模型
)

__all__ = [
    "Base",
    "User",
    "Conversation",
    "Message",
    "KnowledgeBase",
    "Document",
    "Chunk",
    "VoiceModel",
    "TTSTask",
    "OperationLog",
]
