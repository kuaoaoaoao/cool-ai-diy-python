# ============================================================
# AI聊天API路由
# ============================================================
#
# 本模块处理AI聊天相关的API接口
#
# 主要功能：
# 1. 创建对话会话
# 2. 获取会话列表
# 3. 发送聊天消息
# 4. 流式对话响应
# 5. 删除会话
#
# Author: CoolAI Team
# Date: 2026-05-13
# ============================================================

import json
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
    
    Args:
        skip: 分页偏移
        limit: 返回数量限制
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        List[ConversationResponse]: 会话列表
    """
    # 查询会话列表
    stmt = (
        select(Conversation)
        .where(
            Conversation.user_id == current_user["user_id"],
            Conversation.is_deleted == False
        )
        .options(selectinload(Conversation.messages))  # 预加载消息
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
    
    Args:
        conversation_id: 会话ID
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        ConversationResponse: 会话详情
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
    
    Args:
        conversation_id: 会话ID
        current_user: 当前用户
        db: 数据库会话
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
# 聊天消息
# ============================================================

@router.post(
    "/",
    response_model=ChatResponse,
    summary="发送消息",
    description="向AI发送消息并获取回复（非流式）",
)
async def chat(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    处理用户聊天请求
    
    这是一个简化的实现，实际项目中应该调用AI服务
    
    Args:
        request: 聊天请求数据
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        ChatResponse: AI回复
    """
    # 获取或创建会话
    if request.conversation_id:
        stmt = select(Conversation).where(
            Conversation.id == request.conversation_id,
            Conversation.user_id == current_user["user_id"]
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
            user_id=current_user["user_id"],
            model=request.model or "gpt-4-turbo-preview",
            system_prompt=request.system_prompt,
        )
        db.add(conversation)
        await db.flush()  # 获取ID
    
    # 保存用户消息
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=request.message,
    )
    db.add(user_message)
    await db.flush()
    
    # TODO: 调用AI服务获取回复
    # 这里使用模拟回复，实际项目中应该接入LangChain或其他AI服务
    ai_response_content = f"【模拟回复】您发送了: {request.message}"
    
    # 保存AI回复
    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=ai_response_content,
        metadata={"model": request.model or "gpt-4-turbo-preview"},
        tokens=len(ai_response_content),  # 简化的token计算
    )
    db.add(assistant_message)
    await db.commit()
    
    # 更新会话时间
    conversation.updated_at = datetime.now()
    
    return ChatResponse(
        conversation_id=str(conversation.id),
        message_id=str(assistant_message.id),
        content=ai_response_content,
        model=request.model or "gpt-4-turbo-preview",
        usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        created_at=assistant_message.created_at,
    )


@router.post(
    "/stream",
    summary="流式对话",
    description="向AI发送消息并获取流式回复（SSE）",
)
async def chat_stream(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    流式聊天响应
    
    使用Server-Sent Events (SSE) 实现流式输出
    
    Args:
        request: 聊天请求数据
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        StreamingResponse: SSE流
    """
    # 获取或创建会话（与上面类似）
    if request.conversation_id:
        stmt = select(Conversation).where(
            Conversation.id == request.conversation_id,
            Conversation.user_id == current_user["user_id"]
        )
        result = await db.execute(stmt)
        conversation = result.scalar_one_or_none()
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在"
            )
    else:
        conversation = Conversation(
            user_id=current_user["user_id"],
            model=request.model or "gpt-4-turbo-preview",
            system_prompt=request.system_prompt,
        )
        db.add(conversation)
        await db.flush()
    
    # 保存用户消息
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=request.message,
    )
    db.add(user_message)
    await db.commit()
    
    async def generate_stream():
        """
        生成SSE流
        
        每次发送一小段文本，模拟打字机效果
        """
        # TODO: 调用AI服务进行流式生成
        response_text = f"【模拟流式回复】您发送了: {request.message}\n\n"
        
        # 模拟逐字输出
        for i, char in enumerate(response_text):
            # 发送SSE格式的数据
            data = {
                "type": "token",
                "content": char,
                "index": i,
            }
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            
            # 模拟延迟
            import asyncio
            await asyncio.sleep(0.05)
        
        # 发送完成信号
        yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
    
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
    
    Args:
        conversation_id: 会话ID
        skip: 分页偏移
        limit: 返回数量
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        List[MessageResponse]: 消息列表
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
