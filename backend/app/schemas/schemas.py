# ============================================================
# Pydantic模式定义模块
# ============================================================
#
# 本模块定义API请求和响应的数据验证模式
# 使用Pydantic进行数据验证和序列化
#
# 为什么要用Pydantic？
# 1. 自动数据验证
# 2. 自动生成API文档
# 3. JSON序列化/反序列化
# 4. 字段文档和默认值
#
# Author: CoolAI Team
# Date: 2026-05-13
# ============================================================

from datetime import datetime
from typing import Optional, List, Any, Dict
from enum import Enum

from pydantic import BaseModel, Field, EmailStr, ConfigDict


# ============================================================
# 枚举定义
# ============================================================

class UserRole(str, Enum):
    """
    用户角色枚举
    
    用于权限控制
    """
    ADMIN = "admin"    # 管理员
    USER = "user"     # 普通用户


class MessageRole(str, Enum):
    """
    消息角色枚举
    """
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class TaskStatus(str, Enum):
    """
    任务状态枚举
    """
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentStatus(str, Enum):
    """
    文档处理状态枚举
    """
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class VoiceModelStatus(str, Enum):
    """
    声音模型训练状态枚举
    """
    TRAINING = "training"
    READY = "ready"
    FAILED = "failed"


# ============================================================
# 用户相关模式
# ============================================================

class UserBase(BaseModel):
    """
    用户基础模式
    
    包含用户的基本信息字段
    """
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱地址")
    full_name: Optional[str] = Field(None, max_length=100, description="真实姓名")


class UserCreate(UserBase):
    """
    用户创建模式
    
    用于用户注册
    """
    password: str = Field(..., min_length=6, max_length=100, description="密码")


class UserUpdate(BaseModel):
    """
    用户更新模式
    
    用于更新用户信息（可选字段）
    """
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserResponse(UserBase):
    """
    用户响应模式
    
    用于API返回用户信息
    """
    model_config = ConfigDict(from_attributes=True)
    
    id: str = Field(..., description="用户ID")
    role: UserRole = Field(..., description="用户角色")
    is_active: bool = Field(..., description="是否激活")
    created_at: datetime = Field(..., description="创建时间")


class UserLogin(BaseModel):
    """
    用户登录模式
    """
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class TokenResponse(BaseModel):
    """
    Token响应模式
    """
    access_token: str = Field(..., description="访问令牌")
    refresh_token: str = Field(..., description="刷新令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(..., description="过期时间(秒)")


# ============================================================
# 对话相关模式
# ============================================================

class ConversationBase(BaseModel):
    """
    对话基础模式
    """
    title: Optional[str] = Field(None, max_length=255, description="会话标题")
    model: str = Field(default="gpt-4-turbo-preview", description="AI模型")
    system_prompt: Optional[str] = Field(None, description="系统提示词")
    config: Optional[Dict[str, Any]] = Field(None, description="配置参数")


class ConversationCreate(ConversationBase):
    """
    创建对话模式
    """
    pass


class ConversationUpdate(BaseModel):
    """
    更新对话模式
    """
    title: Optional[str] = None
    system_prompt: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class ConversationResponse(ConversationBase):
    """
    对话响应模式
    """
    model_config = ConfigDict(from_attributes=True)
    
    id: str = Field(..., description="会话ID")
    user_id: str = Field(..., description="用户ID")
    message_count: int = Field(default=0, description="消息数量")
    is_deleted: bool = Field(..., description="是否已删除")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


# ============================================================
# 消息相关模式
# ============================================================

class MessageBase(BaseModel):
    """
    消息基础模式
    """
    content: str = Field(..., min_length=1, description="消息内容")
    role: MessageRole = Field(..., description="消息角色")


class MessageCreate(MessageBase):
    """
    创建消息模式
    """
    conversation_id: str = Field(..., description="会话ID")


class MessageResponse(MessageBase):
    """
    消息响应模式
    """
    model_config = ConfigDict(from_attributes=True)
    
    id: str = Field(..., description="消息ID")
    conversation_id: str = Field(..., description="会话ID")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")
    tokens: Optional[int] = Field(None, description="Token消耗")
    created_at: datetime = Field(..., description="创建时间")


class ChatRequest(BaseModel):
    """
    聊天请求模式
    
    用于发送聊天消息
    """
    conversation_id: Optional[str] = Field(None, description="会话ID，为空则创建新会话")
    message: str = Field(..., min_length=1, description="用户消息")
    model: Optional[str] = Field(None, description="AI模型")
    system_prompt: Optional[str] = Field(None, description="系统提示词")
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0, description="温度参数")
    max_tokens: Optional[int] = Field(default=4096, ge=1, le=32000, description="最大Token数")
    use_knowledge: bool = Field(default=False, description="是否使用知识库")
    knowledge_base_id: Optional[str] = Field(None, description="知识库ID")
    stream: bool = Field(default=True, description="是否流式输出")


class ChatResponse(BaseModel):
    """
    聊天响应模式
    """
    conversation_id: str = Field(..., description="会话ID")
    message_id: str = Field(..., description="消息ID")
    content: str = Field(..., description="回复内容")
    model: str = Field(..., description="使用的模型")
    usage: Dict[str, int] = Field(..., description="Token使用统计")
    created_at: datetime = Field(..., description="创建时间")


# ============================================================
# 知识库相关模式
# ============================================================

class KnowledgeBaseBase(BaseModel):
    """
    知识库基础模式
    """
    name: str = Field(..., min_length=1, max_length=255, description="知识库名称")
    description: Optional[str] = Field(None, description="知识库描述")
    config: Optional[Dict[str, Any]] = Field(None, description="配置参数")


class KnowledgeBaseCreate(KnowledgeBaseBase):
    """
    创建知识库模式
    """
    pass


class KnowledgeBaseUpdate(BaseModel):
    """
    更新知识库模式
    """
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class KnowledgeBaseResponse(KnowledgeBaseBase):
    """
    知识库响应模式
    """
    model_config = ConfigDict(from_attributes=True)
    
    id: str = Field(..., description="知识库ID")
    user_id: str = Field(..., description="用户ID")
    chunk_count: int = Field(default=0, description="文本块数量")
    doc_count: int = Field(default=0, description="文档数量")
    is_public: bool = Field(..., description="是否公开")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class DocumentResponse(BaseModel):
    """
    文档响应模式
    """
    model_config = ConfigDict(from_attributes=True)
    
    id: str = Field(..., description="文档ID")
    knowledge_base_id: str = Field(..., description="知识库ID")
    filename: str = Field(..., description="文件名")
    file_size: Optional[int] = Field(None, description="文件大小")
    file_type: Optional[str] = Field(None, description="文件类型")
    status: DocumentStatus = Field(..., description="处理状态")
    error_message: Optional[str] = Field(None, description="错误信息")
    created_at: datetime = Field(..., description="上传时间")
    processed_at: Optional[datetime] = Field(None, description="处理完成时间")


class KnowledgeQueryRequest(BaseModel):
    """
    知识库查询请求模式
    """
    query: str = Field(..., min_length=1, description="查询文本")
    top_k: int = Field(default=5, ge=1, le=20, description="返回结果数量")
    similarity_threshold: Optional[float] = Field(
        default=0.5, ge=0.0, le=1.0, description="相似度阈值"
    )


class KnowledgeQueryResult(BaseModel):
    """
    知识库查询结果模式
    """
    content: str = Field(..., description="匹配的文本内容")
    score: float = Field(..., description="相似度得分")
    source: Optional[str] = Field(None, description="来源文档")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


class KnowledgeQueryResponse(BaseModel):
    """
    知识库查询响应模式
    """
    query: str = Field(..., description="原始查询")
    results: List[KnowledgeQueryResult] = Field(..., description="查询结果")
    total_count: int = Field(..., description="结果总数")


# ============================================================
# TTS相关模式
# ============================================================

class TTSRequest(BaseModel):
    """
    TTS请求模式
    """
    text: str = Field(..., min_length=1, max_length=10000, description="待合成的文本")
    voice: str = Field(default="zh-CN-XiaoxiaoNeural", description="语音ID")
    speed: float = Field(default=1.0, ge=0.5, le=2.0, description="语速倍率")
    pitch: int = Field(default=0, ge=-50, le=50, description="音调调整")
    format: str = Field(default="mp3", description="输出格式(mp3/wav/ogg)")


class VoiceInfo(BaseModel):
    """
    语音信息模式
    """
    voice_id: str = Field(..., description="语音ID")
    name: str = Field(..., description="语音名称")
    language: str = Field(..., description="支持的语言")
    gender: str = Field(..., description="性别")
    preview_url: Optional[str] = Field(None, description="预览URL")
    is_custom: bool = Field(default=False, description="是否自定义")


class TTSTaskResponse(BaseModel):
    """
    TTS任务响应模式
    """
    model_config = ConfigDict(from_attributes=True)
    
    id: str = Field(..., description="任务ID")
    user_id: str = Field(..., description="用户ID")
    text: str = Field(..., description="待合成文本")
    voice_id: Optional[str] = Field(None, description="语音ID")
    status: TaskStatus = Field(..., description="任务状态")
    output_path: Optional[str] = Field(None, description="输出文件路径")
    error_message: Optional[str] = Field(None, description="错误信息")
    created_at: datetime = Field(..., description="创建时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")


# ============================================================
# 声音克隆相关模式
# ============================================================

class VoiceModelBase(BaseModel):
    """
    声音模型基础模式
    """
    name: str = Field(..., min_length=1, max_length=255, description="声音名称")
    description: Optional[str] = Field(None, description="声音描述")


class VoiceModelCreate(VoiceModelBase):
    """
    创建声音模型模式
    """
    pass


class VoiceModelResponse(VoiceModelBase):
    """
    声音模型响应模式
    """
    model_config = ConfigDict(from_attributes=True)
    
    id: str = Field(..., description="模型ID")
    user_id: str = Field(..., description="用户ID")
    model_path: Optional[str] = Field(None, description="模型文件路径")
    reference_audio: Optional[str] = Field(None, description="参考音频路径")
    status: VoiceModelStatus = Field(..., description="训练状态")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


# ============================================================
# 系统相关模式
# ============================================================

class HealthResponse(BaseModel):
    """
    健康检查响应模式
    """
    status: str = Field(..., description="服务状态")
    version: str = Field(..., description="版本号")
    database: str = Field(..., description="数据库状态")
    redis: str = Field(..., description="Redis状态")
    milvus: str = Field(..., description="Milvus状态")


class StatsResponse(BaseModel):
    """
    统计数据响应模式
    """
    total_users: int = Field(..., description="总用户数")
    total_conversations: int = Field(..., description="总会话数")
    total_messages: int = Field(..., description="总消息数")
    total_knowledge_bases: int = Field(..., description="总知识库数")
    total_documents: int = Field(..., description="总文档数")


class ModelInfo(BaseModel):
    """
    模型信息模式
    """
    name: str = Field(..., description="模型名称")
    display_name: str = Field(..., description="显示名称")
    provider: str = Field(..., description="提供商")
    description: str = Field(..., description="模型描述")
    is_available: bool = Field(..., description="是否可用")


class ModelListResponse(BaseModel):
    """
    模型列表响应模式
    """
    models: List[ModelInfo] = Field(..., description="模型列表")


# ============================================================
# 通用响应模式
# ============================================================

class SuccessResponse(BaseModel):
    """
    通用成功响应模式
    """
    success: bool = Field(default=True, description="是否成功")
    message: str = Field(..., description="消息")
    data: Optional[Any] = Field(None, description="数据")


class ErrorResponse(BaseModel):
    """
    通用错误响应模式
    """
    success: bool = Field(default=False, description="是否成功")
    error: str = Field(..., description="错误信息")
    detail: Optional[str] = Field(None, description="详细信息")


class PaginatedResponse(BaseModel):
    """
    分页响应模式
    """
    items: List[Any] = Field(..., description="数据列表")
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页大小")
    total_pages: int = Field(..., description="总页数")
