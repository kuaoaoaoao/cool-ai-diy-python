# ============================================================
# 数据库模型模块
# ============================================================
#
# 本模块定义了所有的数据库表结构（ORM模型）
# 使用SQLAlchemy ORM进行数据库操作
#
# 模型列表：
# 1. User - 用户表
# 2. Conversation - 对话会话表
# 3. Message - 消息记录表
# 4. KnowledgeBase - 知识库表
# 5. Document - 文档表
# 6. Chunk - 文本块表
# 7. VoiceModel - 声音模型表
# 8. TTSTask - TTS任务表
#
# Author: CoolAI Team
# Date: 2026-05-13
# ============================================================

import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    Column, String, Text, Boolean, DateTime, Integer, 
    BigInteger, ForeignKey, JSON, Index, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


# ============================================================
# 用户模型
# ============================================================

class User(Base):
    """
    用户模型
    
    存储系统用户的基本信息
    
    Attributes:
        id: 用户唯一标识符(UUID)
        username: 用户名，唯一
        email: 邮箱地址，唯一
        password_hash: 密码哈希值
        full_name: 真实姓名
        avatar_url: 头像URL
        role: 用户角色 (admin/user)
        is_active: 账户是否激活
        created_at: 创建时间
        updated_at: 更新时间
    """
    __tablename__ = "users"
    
    # 主键 - 使用UUID
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 用户名 - 唯一约束
    username = Column(String(50), unique=True, nullable=False, index=True)
    
    # 邮箱 - 唯一约束
    email = Column(String(255), unique=True, nullable=False, index=True)
    
    # 密码哈希 - 不存储明文密码
    password_hash = Column(String(255), nullable=False)
    
    # 真实姓名（可选）
    full_name = Column(String(100))
    
    # 头像URL（可选）
    avatar_url = Column(String(500))
    
    # 用户角色 - 默认普通用户
    role = Column(String(20), default="user")
    
    # 账户激活状态
    is_active = Column(Boolean, default=True)
    
    # 时间戳
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # ============================================================
    # 关系定义
    # ============================================================
    
    # 用户拥有的对话会话（一对多）
    conversations: Mapped[List["Conversation"]] = relationship(
        "Conversation",
        back_populates="user",
        cascade="all, delete-orphan"  # 删除用户时级联删除会话
    )
    
    # 用户管理的知识库（一对多）
    knowledge_bases: Mapped[List["KnowledgeBase"]] = relationship(
        "KnowledgeBase",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    # 用户克隆的声音模型（一对多）
    voice_models: Mapped[List["VoiceModel"]] = relationship(
        "VoiceModel",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    # 用户的TTS任务（一对多）
    tts_tasks: Mapped[List["TTSTask"]] = relationship(
        "TTSTask",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, role={self.role})>"


# ============================================================
# 对话会话模型
# ============================================================

class Conversation(Base):
    """
    对话会话模型
    
    表示用户与AI的一次完整对话会话
    
    Attributes:
        id: 会话唯一标识符
        user_id: 所属用户ID
        title: 会话标题（可自动生成）
        model: 使用的AI模型
        system_prompt: 系统提示词
        config: 会话配置(JSON)
        is_deleted: 是否已删除（软删除）
        created_at: 创建时间
        updated_at: 更新时间
    """
    __tablename__ = "conversations"
    
    # 主键
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 外键 - 关联用户
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # 会话标题
    title = Column(String(255))
    
    # 使用的AI模型
    model = Column(String(50), default="gpt-4-turbo-preview")
    
    # 系统提示词
    system_prompt = Column(Text)
    
    # 会话配置 - 存储为JSON
    # 可以包含temperature、top_p等参数
    config = Column(JSON)
    
    # 软删除标记
    is_deleted = Column(Boolean, default=False)
    
    # 时间戳
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # ============================================================
    # 关系定义
    # ============================================================
    
    # 所属用户
    user: Mapped["User"] = relationship("User", back_populates="conversations")
    
    # 会话中的消息（一对多）
    messages: Mapped[List["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at"  # 按时间排序
    )
    
    # ============================================================
    # 索引
    # ============================================================
    
    # 用户-删除状态复合索引
    __table_args__ = (
        Index("idx_conv_user_deleted", "user_id", "is_deleted"),
    )
    
    def __repr__(self):
        return f"<Conversation(id={self.id}, title={self.title})>"


# ============================================================
# 消息记录模型
# ============================================================

class Message(Base):
    """
    消息记录模型
    
    存储对话中的每一条消息
    
    Attributes:
        id: 消息唯一标识符
        conversation_id: 所属会话ID
        role: 消息角色 (user/assistant/system/tool)
        content: 消息内容
        metadata: 附加信息(JSON)
        tokens: 消耗的token数量
        created_at: 创建时间
    """
    __tablename__ = "messages"
    
    # 主键
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 外键 - 关联会话
    conversation_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("conversations.id"), 
        nullable=False
    )
    
    # 消息角色
    role = Column(String(20), nullable=False)
    # role 可选值: "user", "assistant", "system", "tool"
    
    # 消息内容
    content = Column(Text, nullable=False)
    
    # 附加元数据 - 存储为JSON
    # 可以包含工具调用结果、模型响应参数等
    metadata = Column(JSON)
    
    # token消耗数量（用于计费）
    tokens = Column(Integer)
    
    # 创建时间
    created_at = Column(DateTime, server_default=func.now())
    
    # ============================================================
    # 关系定义
    # ============================================================
    
    # 所属会话
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", 
        back_populates="messages"
    )
    
    # ============================================================
    # 索引
    # ============================================================
    
    __table_args__ = (
        # 会话-时间复合索引
        Index("idx_msg_conv_time", "conversation_id", "created_at"),
    )
    
    def __repr__(self):
        return f"<Message(id={self.id}, role={self.role}, content={self.content[:50]}...)>"


# ============================================================
# 知识库模型
# ============================================================

class KnowledgeBase(Base):
    """
    知识库模型
    
    用户创建的知识库，用于RAG检索增强
    
    Attributes:
        id: 知识库唯一标识符
        user_id: 所属用户ID
        name: 知识库名称
        description: 知识库描述
        config: 配置信息(JSON)
        chunk_count: 文本块数量
        doc_count: 文档数量
        is_public: 是否公开
        created_at: 创建时间
        updated_at: 更新时间
    """
    __tablename__ = "knowledge_bases"
    
    # 主键
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 外键 - 关联用户
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # 知识库名称
    name = Column(String(255), nullable=False)
    
    # 描述
    description = Column(Text)
    
    # 配置信息 - 存储为JSON
    # 可以包含分块策略、检索参数等
    config = Column(JSON)
    
    # 统计字段
    chunk_count = Column(Integer, default=0)  # 文本块数量
    doc_count = Column(Integer, default=0)    # 文档数量
    
    # 是否公开
    is_public = Column(Boolean, default=False)
    
    # 时间戳
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # ============================================================
    # 关系定义
    # ============================================================
    
    # 所属用户
    user: Mapped["User"] = relationship("User", back_populates="knowledge_bases")
    
    # 知识库中的文档（一对多）
    documents: Mapped[List["Document"]] = relationship(
        "Document",
        back_populates="knowledge_base",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"<KnowledgeBase(id={self.id}, name={self.name})>"


# ============================================================
# 文档模型
# ============================================================

class Document(Base):
    """
    文档模型
    
    存储上传到知识库的原始文档
    
    Attributes:
        id: 文档唯一标识符
        knowledge_base_id: 所属知识库ID
        filename: 原始文件名
        file_path: 存储路径(MinIO)
        file_size: 文件大小(字节)
        file_type: 文件类型
        status: 处理状态
        error_message: 错误信息
        created_at: 上传时间
        processed_at: 处理完成时间
    """
    __tablename__ = "documents"
    
    # 主键
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 外键 - 关联知识库
    knowledge_base_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("knowledge_bases.id"), 
        nullable=False
    )
    
    # 文件信息
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500))  # MinIO存储路径
    file_size = Column(BigInteger)   # 文件大小
    file_type = Column(String(20))    # 文件类型
    
    # 处理状态
    status = Column(String(20), default="pending")
    # status 可选值:
    # - pending: 等待处理
    # - processing: 处理中
    # - completed: 处理完成
    # - failed: 处理失败
    
    # 错误信息
    error_message = Column(Text)
    
    # 时间戳
    created_at = Column(DateTime, server_default=func.now())
    processed_at = Column(DateTime)
    
    # ============================================================
    # 关系定义
    # ============================================================
    
    # 所属知识库
    knowledge_base: Mapped["KnowledgeBase"] = relationship(
        "KnowledgeBase", 
        back_populates="documents"
    )
    
    # 文档分块（一对多）
    chunks: Mapped[List["Chunk"]] = relationship(
        "Chunk",
        back_populates="document",
        cascade="all, delete-orphan"
    )
    
    # ============================================================
    # 索引
    # ============================================================
    
    __table_args__ = (
        Index("idx_doc_kb_status", "knowledge_base_id", "status"),
    )
    
    def __repr__(self):
        return f"<Document(id={self.id}, filename={self.filename})>"


# ============================================================
# 文本块模型
# ============================================================

class Chunk(Base):
    """
    文本块模型
    
    存储文档分块后的文本片段及其向量信息
    
    Attributes:
        id: 块唯一标识符
        document_id: 所属文档ID
        content: 文本内容
        chunk_index: 块索引号
        vector_id: 向量数据库中的ID
        metadata: 元数据(JSON)
        created_at: 创建时间
    """
    __tablename__ = "chunks"
    
    # 主键
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 外键 - 关联文档
    document_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("documents.id"), 
        nullable=False
    )
    
    # 文本内容
    content = Column(Text, nullable=False)
    
    # 块索引
    chunk_index = Column(Integer)
    
    # 向量数据库中的ID（用于关联Milvus等）
    vector_id = Column(String(100))
    
    # 元数据 - 存储为JSON
    # 可以包含来源页码、标题等信息
    metadata = Column(JSON)
    
    # 创建时间
    created_at = Column(DateTime, server_default=func.now())
    
    # ============================================================
    # 关系定义
    # ============================================================
    
    # 所属文档
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")
    
    # ============================================================
    # 索引
    # ============================================================
    
    __table_args__ = (
        Index("idx_chunk_doc", "document_id"),
        Index("idx_chunk_vector", "vector_id"),
    )
    
    def __repr__(self):
        return f"<Chunk(id={self.id}, content={self.content[:30]}...)>"


# ============================================================
# 声音模型
# ============================================================

class VoiceModel(Base):
    """
    声音模型
    
    存储用户克隆的声音模型信息
    
    Attributes:
        id: 模型唯一标识符
        user_id: 所属用户ID
        name: 声音名称
        description: 声音描述
        model_path: 模型文件路径
        reference_audio: 参考音频路径
        status: 训练状态
        created_at: 创建时间
        updated_at: 更新时间
    """
    __tablename__ = "voice_models"
    
    # 主键
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 外键 - 关联用户
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # 声音名称
    name = Column(String(255), nullable=False)
    
    # 描述
    description = Column(Text)
    
    # 模型文件路径
    model_path = Column(String(500))
    
    # 参考音频路径
    reference_audio = Column(String(500))
    
    # 训练状态
    status = Column(String(20), default="training")
    # status 可选值:
    # - training: 训练中
    # - ready: 就绪可用
    # - failed: 训练失败
    
    # 时间戳
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # ============================================================
    # 关系定义
    # ============================================================
    
    # 所属用户
    user: Mapped["User"] = relationship("User", back_populates="voice_models")
    
    def __repr__(self):
        return f"<VoiceModel(id={self.id}, name={self.name}, status={self.status})>"


# ============================================================
# TTS任务模型
# ============================================================

class TTSTask(Base):
    """
    TTS任务模型
    
    存储语音合成任务的记录
    
    Attributes:
        id: 任务唯一标识符
        user_id: 所属用户ID
        text: 待合成的文本
        voice_id: 使用的语音ID
        status: 任务状态
        output_path: 输出文件路径
        error_message: 错误信息
        created_at: 创建时间
        completed_at: 完成时间
    """
    __tablename__ = "tts_tasks"
    
    # 主键
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 外键 - 关联用户
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # 待合成的文本
    text = Column(Text, nullable=False)
    
    # 使用的语音ID
    voice_id = Column(String(100))
    
    # 任务状态
    status = Column(String(20), default="pending")
    # status 可选值:
    # - pending: 等待处理
    # - processing: 处理中
    # - completed: 处理完成
    # - failed: 处理失败
    
    # 输出文件路径
    output_path = Column(String(500))
    
    # 错误信息
    error_message = Column(Text)
    
    # 时间戳
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime)
    
    # ============================================================
    # 关系定义
    # ============================================================
    
    # 所属用户
    user: Mapped["User"] = relationship("User", back_populates="tts_tasks")
    
    # ============================================================
    # 索引
    # ============================================================
    
    __table_args__ = (
        Index("idx_tts_user_status", "user_id", "status"),
    )
    
    def __repr__(self):
        return f"<TTSTask(id={self.id}, status={self.status})>"


# ============================================================
# 操作日志模型（可选）
# ============================================================

class OperationLog(Base):
    """
    操作日志模型
    
    记录用户的操作行为，用于审计
    
    Attributes:
        id: 日志唯一标识符
        user_id: 操作用户ID
        action: 操作类型
        resource_type: 资源类型
        resource_id: 资源ID
        details: 详细信息(JSON)
        ip_address: IP地址
        user_agent: 用户代理
        created_at: 操作时间
    """
    __tablename__ = "operation_logs"
    
    # 主键
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 外键 - 关联用户（可为空，表示系统操作）
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # 操作信息
    action = Column(String(100), nullable=False)  # 操作类型
    resource_type = Column(String(50))             # 资源类型
    resource_id = Column(UUID(as_uuid=True))      # 资源ID
    
    # 详细信息
    details = Column(JSON)
    
    # 请求信息
    ip_address = Column(String(45))  # IPv6地址
    user_agent = Column(Text)
    
    # 操作时间
    created_at = Column(DateTime, server_default=func.now())
    
    # ============================================================
    # 索引
    # ============================================================
    
    __table_args__ = (
        Index("idx_log_user", "user_id"),
        Index("idx_log_action", "action"),
        Index("idx_log_created", "created_at"),
    )
    
    def __repr__(self):
        return f"<OperationLog(id={self.id}, action={self.action})>"
