# ============================================================
# Schemas模块导出
# ============================================================
"""
导出所有Pydantic模式定义
"""

from app.schemas.schemas import (
    # 枚举
    UserRole,
    MessageRole,
    TaskStatus,
    DocumentStatus,
    VoiceModelStatus,
    # 用户相关
    UserBase,
    UserCreate,
    UserUpdate,
    UserResponse,
    UserLogin,
    TokenResponse,
    # 对话相关
    ConversationBase,
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    MessageBase,
    MessageCreate,
    MessageResponse,
    ChatRequest,
    ChatResponse,
    # 知识库相关
    KnowledgeBaseBase,
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseResponse,
    DocumentResponse,
    KnowledgeQueryRequest,
    KnowledgeQueryResult,
    KnowledgeQueryResponse,
    # TTS相关
    TTSRequest,
    VoiceInfo,
    TTSTaskResponse,
    # 声音克隆相关
    VoiceModelBase,
    VoiceModelCreate,
    VoiceModelResponse,
    # 系统相关
    HealthResponse,
    StatsResponse,
    ModelInfo,
    ModelListResponse,
    # 通用响应
    SuccessResponse,
    ErrorResponse,
    PaginatedResponse,
)

__all__ = [
    # 枚举
    "UserRole",
    "MessageRole",
    "TaskStatus",
    "DocumentStatus",
    "VoiceModelStatus",
    # 用户相关
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserLogin",
    "TokenResponse",
    # 对话相关
    "ConversationBase",
    "ConversationCreate",
    "ConversationUpdate",
    "ConversationResponse",
    "MessageBase",
    "MessageCreate",
    "MessageResponse",
    "ChatRequest",
    "ChatResponse",
    # 知识库相关
    "KnowledgeBaseBase",
    "KnowledgeBaseCreate",
    "KnowledgeBaseUpdate",
    "KnowledgeBaseResponse",
    "DocumentResponse",
    "KnowledgeQueryRequest",
    "KnowledgeQueryResult",
    "KnowledgeQueryResponse",
    # TTS相关
    "TTSRequest",
    "VoiceInfo",
    "TTSTaskResponse",
    # 声音克隆相关
    "VoiceModelBase",
    "VoiceModelCreate",
    "VoiceModelResponse",
    # 系统相关
    "HealthResponse",
    "StatsResponse",
    "ModelInfo",
    "ModelListResponse",
    # 通用响应
    "SuccessResponse",
    "ErrorResponse",
    "PaginatedResponse",
]
