# ============================================================
# AI聊天API路由
# ============================================================
#
# 本模块处理AI聊天相关的API接口
# 已集成LLM Gateway和AgentService
#
# 主要功能：
# 1. 创建对话会话
# 2. 获取会话列表
# 3. 发送聊天消息（支持普通模式和Agent模式）
# 4. 流式对话响应（SSE）
# 5. 删除会话
# 6. 获取消息历史
#
# Author: CoolAI Team
# Date: 2026-05-13
# ============================================================

import json
import asyncio
from datetime import datetime
from typing import Optional, List, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import User, Conversation, Message
from app.schemas import (
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    MessageResponse,
    ChatRequest,
    ChatResponse,
)


# ============================================================
# 路由配置
# ============================================================

router = APIRouter(
    prefix="/chat",
    tags=["AI聊天"],
    summary="AI对话接口",
)


# ============================================================
# 对话会话管理
# ============================================================

@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建对话会话",
    description="创建一个新的AI对话会话",
)
async def create_conversation(
    conv_data: ConversationCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    创建新的对话会话
    
    Args:
        conv_data: 会话创建数据
        current_user: 当前用户信息
        db: 数据库会话
        
    Returns:
        ConversationResponse: 创建的会话信息
    """
    new_conversation = Conversation(
        user_id=current_user["user_id"],
        title=conv_data.title or f"新对话 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        model=conv_data.model,
        system_prompt=conv_data.system_prompt,
        config=conv_data.config,
    )
    
    db.add(new_conversation)
    await db.commit()
    await db.refresh(new_conversation)
    
    return new_conversation


@router.get(
    "/conversations",
    response_model=List[ConversationResponse],
    summary="获取会话列表",
    description="获取当前用户的所有对话会话",
)
async def list_conversations(
    skip: int = Query(default=0, ge=0, description="跳过的数量"),
    limit: int = Query(default=20, ge=1, le=100, description="返回数量"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取用户的会话列表
    """
    # 查询会话列表
    stmt = (
        select(Conversation)
        .where(
            Conversation.user_id == current_user["user_id"],
            Conversation.is_deleted == False
        )
        .options(selectinload(Conversation.messages))
        .order_by(desc(Conversation.updated_at))
        .offset(skip)
        .limit(limit)
    )
    
    result = await db.execute(stmt)
    conversations = result.scalars().all()
    
    # 转换为响应格式
    response_list = []
    for conv in conversations:
        response_list.append(ConversationResponse(
            id=str(conv.id),
            user_id=str(conv.user_id),
            title=conv.title,
            model=conv.model,
            system_prompt=conv.system_prompt,
            config=conv.config,
            message_count=len(conv.messages),
            is_deleted=conv.is_deleted,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
        ))
    
    return response_list


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    summary="获取会话详情",
    description="获取指定会话的详细信息和消息",
)
async def get_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取会话详情
    """
    stmt = (
        select(Conversation)
        .where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user["user_id"]
        )
        .options(selectinload(Conversation.messages))
    )
    
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )
    
    return ConversationResponse(
        id=str(conversation.id),
        user_id=str(conversation.user_id),
        title=conversation.title,
        model=conversation.model,
        system_prompt=conversation.system_prompt,
        config=conversation.config,
        message_count=len(conversation.messages),
        is_deleted=conversation.is_deleted,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除会话",
    description="软删除指定的对话会话",
)
async def delete_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除会话（软删除）
    """
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user["user_id"]
    )
    
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )
    
    # 软删除
    conversation.is_deleted = True
    await db.commit()


# ============================================================
# 辅助函数：获取或创建会话
# ============================================================

async def _get_or_create_conversation(
    request: ChatRequest,
    user_id: str,
    db: AsyncSession
) -> Conversation:
    """获取已有会话或创建新会话"""
    if request.conversation_id:
        stmt = select(Conversation).where(
            Conversation.id == request.conversation_id,
            Conversation.user_id == user_id
        )
        result = await db.execute(stmt)
        conversation = result.scalar_one_or_none()
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在"
            )
    else:
        # 创建新会话
        conversation = Conversation(
            user_id=user_id,
            model=request.model or "gpt-4-turbo-preview",
            system_prompt=request.system_prompt,
        )
        db.add(conversation)
        await db.flush()
    
    return conversation


async def _load_context_messages(
    conversation_id: str,
    db: AsyncSession,
    limit: int = 20
) -> list:
    """从数据库加载历史消息作为上下文"""
    from app.services.llm_gateway import Message as LLMMessage
    
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(desc(Message.created_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()
    
    # 按时间正序排列
    messages = list(reversed(messages))
    
    context = []
    for msg in messages:
        context.append(LLMMessage(role=msg.role, content=msg.content))
    
    return context


# ============================================================
# 聊天消息 - 普通模式
# ============================================================

@router.post(
    "/",
    response_model=ChatResponse,
    summary="发送消息",
    description="向AI发送消息并获取回复（非流式），支持Agent模式和普通模式",
)
async def chat(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    处理用户聊天请求
    
    根据use_agent参数选择：
    - use_agent=True: 使用AgentService（Plan-Execute模式）
    - use_agent=False: 直接调用LLM Gateway
    
    Args:
        request: 聊天请求数据
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        ChatResponse: AI回复
    """
    # 获取或创建会话
    conversation = await _get_or_create_conversation(request, current_user["user_id"], db)
    
    # 保存用户消息
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=request.message,
    )
    db.add(user_message)
    await db.flush()
    
    # 根据模式选择不同的AI服务
    if request.use_agent:
        # ========== Agent模式 ==========
        from app.services.agent_service import get_agent_service
        
        agent_service = get_agent_service()
        
        # 加载历史上下文
        context_messages = await _load_context_messages(conversation.id, db)
        
        # 调用Agent
        agent_response = await agent_service.chat(
            query=request.message,
            conversation_id=str(conversation.id),
            model_name=request.model,
            use_knowledge=request.use_knowledge,
            context_messages=context_messages,
        )
        
        ai_response_content = agent_response.content
        model_used = agent_response.model or request.model or "agent"
        total_tokens = agent_response.total_tokens
        
    else:
        # ========== 普通LLM模式 ==========
        from app.services.llm_gateway import get_llm_gateway, Message as LLMMessage
        
        llm = get_llm_gateway()
        model_name = request.model or "gpt-4-turbo-preview"
        
        # 构建消息列表
        messages = []
        if request.system_prompt:
            messages.append(LLMMessage(role="system", content=request.system_prompt))
        elif conversation.system_prompt:
            messages.append(LLMMessage(role="system", content=conversation.system_prompt))
        
        # 加载历史上下文
        context = await _load_context_messages(conversation.id, db)
        messages.extend(context)
        
        # 添加当前用户消息
        messages.append(LLMMessage(role="user", content=request.message))
        
        # 知识库检索增强
        if request.use_knowledge and request.knowledge_base_id:
            try:
                from app.services.rag_service_impl import get_rag_pipeline
                rag = get_rag_pipeline()
                results = await rag.retrieve(request.message, top_k=5)
                if results:
                    context_text = "\n".join(
                        f"[参考{i+1}] {r.chunk.content}" 
                        for i, r in enumerate(results)
                    )
                    messages.append(LLMMessage(
                        role="system",
                        content=f"知识库检索结果：\n{context_text}"
                    ))
            except Exception:
                pass  # 知识库检索失败不影响主流程
        
        # 调用LLM Gateway
        llm_response = await llm.chat(
            messages=messages,
            model_name=model_name,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        
        ai_response_content = llm_response.content or ""
        model_used = llm_response.model or model_name
        total_tokens = llm_response.usage.get("total_tokens", 0)
    
    # 保存AI回复
    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=ai_response_content,
        metadata={
            "model": model_used,
            "use_agent": request.use_agent,
            "use_knowledge": request.use_knowledge,
        },
        tokens=total_tokens,
    )
    db.add(assistant_message)
    
    # 更新会话时间
    conversation.updated_at = datetime.now()
    await db.commit()
    await db.refresh(assistant_message)
    
    return ChatResponse(
        conversation_id=str(conversation.id),
        message_id=str(assistant_message.id),
        content=ai_response_content,
        model=model_used,
        usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": total_tokens},
        created_at=assistant_message.created_at,
    )


# ============================================================
# 聊天消息 - 流式模式
# ============================================================

@router.post(
    "/stream",
    summary="流式对话",
    description="向AI发送消息并获取流式回复（SSE），支持Agent模式和普通模式",
)
async def chat_stream(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    流式聊天响应
    
    使用Server-Sent Events (SSE) 实现流式输出
    支持 use_agent 参数切换Agent模式
    """
    # 获取或创建会话
    conversation = await _get_or_create_conversation(request, current_user["user_id"], db)
    
    # 保存用户消息
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=request.message,
    )
    db.add(user_message)
    await db.commit()
    
    async def generate_stream():
        """生成SSE流"""
        full_content = ""  # 收集完整内容用于保存
        total_tokens = 0
        model_used = request.model or "gpt-4-turbo-preview"
        
        try:
            if request.use_agent:
                # ========== Agent流式模式 ==========
                from app.services.agent_service import get_agent_service
                from app.services.llm_gateway import Message as LLMMessage
                
                agent_service = get_agent_service()
                context_messages = await _load_context_messages(conversation.id, db)
                
                # Agent流式输出
                async for chunk in agent_service.chat_stream(
                    query=request.message,
                    conversation_id=str(conversation.id),
                    model_name=request.model,
                    use_knowledge=request.use_knowledge,
                    context_messages=context_messages,
                ):
                    full_content += chunk
                    data = {
                        "type": "token",
                        "content": chunk,
                    }
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                
                model_used = "agent"
                
            else:
                # ========== 普通LLM流式模式 ==========
                from app.services.llm_gateway import get_llm_gateway, Message as LLMMessage
                
                llm = get_llm_gateway()
                model_name = request.model or "gpt-4-turbo-preview"
                
                # 构建消息列表
                messages = []
                if request.system_prompt:
                    messages.append(LLMMessage(role="system", content=request.system_prompt))
                elif conversation.system_prompt:
                    messages.append(LLMMessage(role="system", content=conversation.system_prompt))
                
                # 加载历史上下文
                context = await _load_context_messages(conversation.id, db)
                messages.extend(context)
                
                # 添加当前用户消息
                messages.append(LLMMessage(role="user", content=request.message))
                
                # 知识库检索增强
                if request.use_knowledge and request.knowledge_base_id:
                    try:
                        from app.services.rag_service_impl import get_rag_pipeline
                        rag = get_rag_pipeline()
                        results = await rag.retrieve(request.message, top_k=5)
                        if results:
                            context_text = "\n".join(
                                f"[参考{i+1}] {r.chunk.content}" 
                                for i, r in enumerate(results)
                            )
                            messages.append(LLMMessage(
                                role="system",
                                content=f"知识库检索结果：\n{context_text}"
                            ))
                    except Exception:
                        pass
                
                # 调用LLM Gateway流式接口
                async for chunk in llm.chat_stream(
                    messages=messages,
                    model_name=model_name,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                ):
                    full_content += chunk
                    data = {
                        "type": "token",
                        "content": chunk,
                    }
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                
                model_used = model_name
            
        except Exception as e:
            # 错误处理：发送错误事件
            error_data = {
                "type": "error",
                "content": str(e),
            }
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
        
        # 保存AI回复到数据库（在流结束后）
        try:
            from app.core.database import async_session_maker
            
            async with async_session_maker() as save_db:
                assistant_message = Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=full_content,
                    metadata={
                        "model": model_used,
                        "use_agent": request.use_agent,
                        "use_knowledge": request.use_knowledge,
                    },
                    tokens=len(full_content),
                )
                save_db.add(assistant_message)
                
                # 更新会话时间
                conversation.updated_at = datetime.now()
                await save_db.commit()
        except Exception:
            pass  # 保存失败不影响流式输出
        
        # 发送完成信号
        done_data = {
            "type": "done",
            "usage": {"total_tokens": len(full_content)},
            "model": model_used,
        }
        yield f"data: {json.dumps(done_data, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# ============================================================
# 获取消息历史
# ============================================================

@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=List[MessageResponse],
    summary="获取消息历史",
    description="获取指定会话的所有消息",
)
async def get_messages(
    conversation_id: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取会话的消息历史
    """
    # 验证会话所有权
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user["user_id"]
    )
    result = await db.execute(stmt)
    
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )
    
    # 获取消息
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
        .offset(skip)
        .limit(limit)
    )
    
    result = await db.execute(stmt)
    messages = result.scalars().all()
    
    return [
        MessageResponse(
            id=str(msg.id),
            conversation_id=str(msg.conversation_id),
            role=msg.role,
            content=msg.content,
            metadata=msg.metadata,
            tokens=msg.tokens,
            created_at=msg.created_at,
        )
        for msg in messages
    ]
