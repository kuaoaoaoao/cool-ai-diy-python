# ============================================================
# 知识库API路由 - 完整实现
# ============================================================
#
# 本模块处理RAG知识库相关的API接口
#
# 主要功能：
# 1. 知识库CRUD
# 2. 文档上传和处理
# 3. 知识检索
# 4. RAG问答
#
# Author: CoolAI Team
# Date: 2026-05-13
# ============================================================

import os
import uuid
from datetime import datetime
from typing import Optional, List, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.config import settings
from app.models import User, KnowledgeBase, Document, Chunk
from app.schemas import (
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseResponse,
    DocumentResponse,
    KnowledgeQueryRequest,
    KnowledgeQueryResponse,
    KnowledgeQueryResult,
    SuccessResponse,
)
from app.services.rag_service_impl import (
    RAGPipeline,
    DocumentParserFactory,
    initialize_rag_pipeline,
    get_rag_pipeline,
)


# ============================================================
# 路由配置
# ============================================================

router = APIRouter(
    prefix="/knowledge",
    tags=["知识库管理"],
    summary="RAG知识库接口",
)


# ============================================================
# 辅助函数
# ============================================================

def get_rag() -> RAGPipeline:
    """获取RAG Pipeline"""
    return get_rag_pipeline()


def ensure_upload_dir():
    """确保上传目录存在"""
    upload_dir = settings.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


# ============================================================
# 知识库管理
# ============================================================

@router.post(
    "/bases",
    response_model=KnowledgeBaseResponse,
    status_code=201,
    summary="创建知识库",
    description="创建一个新的RAG知识库",
)
async def create_knowledge_base(
    kb_data: KnowledgeBaseCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    创建新的知识库
    
    Args:
        kb_data: 知识库创建数据
        current_user: 当前用户
        db: 数据库会话
    
    Returns:
        KnowledgeBaseResponse: 创建的知识库信息
    """
    # 创建知识库记录
    knowledge_base = KnowledgeBase(
        user_id=current_user["user_id"],
        name=kb_data.name,
        description=kb_data.description,
        config=kb_data.config or {
            "chunk_size": settings.RAG_CHUNK_SIZE,
            "chunk_overlap": settings.RAG_CHUNK_OVERLAP,
            "chunk_strategy": "recursive",
        }
    )
    
    db.add(knowledge_base)
    await db.commit()
    await db.refresh(knowledge_base)
    
    return knowledge_base


@router.get(
    "/bases",
    response_model=List[KnowledgeBaseResponse],
    summary="获取知识库列表",
    description="获取当前用户的所有知识库",
)
async def list_knowledge_bases(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取知识库列表
    
    Args:
        skip: 分页偏移
        limit: 返回数量
        current_user: 当前用户
        db: 数据库会话
    
    Returns:
        List[KnowledgeBaseResponse]: 知识库列表
    """
    stmt = (
        select(KnowledgeBase)
        .where(KnowledgeBase.user_id == current_user["user_id"])
        .order_by(desc(KnowledgeBase.updated_at))
        .offset(skip)
        .limit(limit)
    )
    
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get(
    "/bases/{kb_id}",
    response_model=KnowledgeBaseResponse,
    summary="获取知识库详情",
    description="获取指定知识库的详细信息",
)
async def get_knowledge_base(
    kb_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取知识库详情
    
    Args:
        kb_id: 知识库ID
        current_user: 当前用户
        db: 数据库会话
    
    Returns:
        KnowledgeBaseResponse: 知识库详情
    """
    stmt = select(KnowledgeBase).where(
        KnowledgeBase.id == kb_id,
        KnowledgeBase.user_id == current_user["user_id"]
    )
    
    result = await db.execute(stmt)
    kb = result.scalar_one_or_none()
    
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    
    return kb


@router.put(
    "/bases/{kb_id}",
    response_model=KnowledgeBaseResponse,
    summary="更新知识库",
    description="更新知识库的名称、描述或配置",
)
async def update_knowledge_base(
    kb_id: str,
    kb_data: KnowledgeBaseUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    更新知识库
    
    Args:
        kb_id: 知识库ID
        kb_data: 更新数据
        current_user: 当前用户
        db: 数据库会话
    
    Returns:
        KnowledgeBaseResponse: 更新后的知识库
    """
    stmt = select(KnowledgeBase).where(
        KnowledgeBase.id == kb_id,
        KnowledgeBase.user_id == current_user["user_id"]
    )
    
    result = await db.execute(stmt)
    kb = result.scalar_one_or_none()
    
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    
    # 更新字段
    if kb_data.name is not None:
        kb.name = kb_data.name
    if kb_data.description is not None:
        kb.description = kb_data.description
    if kb_data.config is not None:
        kb.config = kb_data.config
    
    kb.updated_at = datetime.now()
    
    await db.commit()
    await db.refresh(kb)
    
    return kb


@router.delete(
    "/bases/{kb_id}",
    status_code=204,
    summary="删除知识库",
    description="删除指定的知识库及其所有文档",
)
async def delete_knowledge_base(
    kb_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除知识库
    
    Args:
        kb_id: 知识库ID
        current_user: 当前用户
        db: 数据库会话
    """
    stmt = select(KnowledgeBase).where(
        KnowledgeBase.id == kb_id,
        KnowledgeBase.user_id == current_user["user_id"]
    )
    
    result = await db.execute(stmt)
    kb = result.scalar_one_or_none()
    
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    
    # 删除关联的文档
    doc_stmt = select(Document).where(Document.knowledge_base_id == kb_id)
    doc_result = await db.execute(doc_stmt)
    documents = doc_result.scalars().all()
    
    for doc in documents:
        # 删除向量数据（如果RAG已初始化）
        try:
            rag = get_rag()
            await rag.delete_document(str(doc.id))
        except:
            pass
        
        await db.delete(doc)
    
    await db.delete(kb)
    await db.commit()


# ============================================================
# 文档管理
# ============================================================

@router.post(
    "/bases/{kb_id}/documents",
    response_model=DocumentResponse,
    status_code=201,
    summary="上传文档",
    description="上传文档到知识库，支持PDF、Word、TXT、Markdown等格式",
)
async def upload_document(
    kb_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    上传文档到知识库
    
    文档将保存到服务器，并触发异步处理流程：
    1. 解析文档
    2. 分块
    3. 向量化
    4. 存储到向量数据库
    
    Args:
        kb_id: 知识库ID
        background_tasks: 后台任务
        file: 上传的文件
        current_user: 当前用户
        db: 数据库会话
    
    Returns:
        DocumentResponse: 文档信息
    """
    # 验证知识库所有权
    stmt = select(KnowledgeBase).where(
        KnowledgeBase.id == kb_id,
        KnowledgeBase.user_id == current_user["user_id"]
    )
    result = await db.execute(stmt)
    kb = result.scalar_one_or_none()
    
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    
    # 验证文件类型
    allowed_types = settings.ALLOWED_DOCUMENT_TYPES
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型，仅支持: {', '.join(allowed_types)}"
        )
    
    # 检查文件大小
    if file.size and file.size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"文件大小超过限制，最大{settings.MAX_FILE_SIZE // (1024*1024)}MB"
        )
    
    # 保存文件
    upload_dir = ensure_upload_dir()
    file_id = str(uuid.uuid4())
    file_path = os.path.join(upload_dir, f"{file_id}{file_ext}")
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # 创建文档记录
    document = Document(
        knowledge_base_id=kb_id,
        filename=file.filename,
        file_path=file_path,
        file_size=len(content),
        file_type=file_ext[1:],  # 去掉点
        status="pending"
    )
    
    db.add(document)
    await db.flush()
    
    # 更新知识库统计
    kb.doc_count = (kb.doc_count or 0) + 1
    kb.updated_at = datetime.now()
    
    await db.commit()
    await db.refresh(document)
    
    # 触发后台处理任务
    background_tasks.add_task(
        process_document_task,
        document_id=str(document.id),
        file_path=file_path,
        kb_id=kb_id
    )
    
    return document


@router.get(
    "/bases/{kb_id}/documents",
    response_model=List[DocumentResponse],
    summary="获取文档列表",
    description="获取知识库中的所有文档",
)
async def list_documents(
    kb_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取文档列表
    
    Args:
        kb_id: 知识库ID
        skip: 分页偏移
        limit: 返回数量
        current_user: 当前用户
        db: 数据库会话
    
    Returns:
        List[DocumentResponse]: 文档列表
    """
    # 验证知识库所有权
    stmt = select(KnowledgeBase).where(
        KnowledgeBase.id == kb_id,
        KnowledgeBase.user_id == current_user["user_id"]
    )
    result = await db.execute(stmt)
    
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="知识库不存在")
    
    # 获取文档列表
    stmt = (
        select(Document)
        .where(Document.knowledge_base_id == kb_id)
        .order_by(desc(Document.created_at))
        .offset(skip)
        .limit(limit)
    )
    
    result = await db.execute(stmt)
    return result.scalars().all()


@router.delete(
    "/bases/{kb_id}/documents/{doc_id}",
    status_code=204,
    summary="删除文档",
    description="删除指定的文档及其关联的向量数据",
)
async def delete_document(
    kb_id: str,
    doc_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除文档
    
    Args:
        kb_id: 知识库ID
        doc_id: 文档ID
        current_user: 当前用户
        db: 数据库会话
    """
    # 验证知识库所有权
    stmt = select(KnowledgeBase).where(
        KnowledgeBase.id == kb_id,
        KnowledgeBase.user_id == current_user["user_id"]
    )
    result = await db.execute(stmt)
    
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="知识库不存在")
    
    # 获取文档
    stmt = select(Document).where(
        Document.id == doc_id,
        Document.knowledge_base_id == kb_id
    )
    result = await db.execute(stmt)
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    # 删除向量数据
    try:
        rag = get_rag()
        await rag.delete_document(str(document.id))
    except:
        pass
    
    # 删除关联的块
    chunk_stmt = select(Chunk).where(Chunk.document_id == doc_id)
    chunk_result = await db.execute(chunk_stmt)
    chunks = chunk_result.scalars().all()
    
    for chunk in chunks:
        await db.delete(chunk)
    
    # 更新知识库统计
    kb_stmt = select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
    kb_result = await db.execute(kb_stmt)
    kb = kb_result.scalar_one()
    kb.doc_count = max(0, (kb.doc_count or 1) - 1)
    kb.chunk_count = max(0, (kb.chunk_count or 0) - len(chunks))
    kb.updated_at = datetime.now()
    
    # 删除文档记录
    await db.delete(document)
    await db.commit()


# ============================================================
# 知识检索与问答
# ============================================================

@router.post(
    "/bases/{kb_id}/query",
    response_model=KnowledgeQueryResponse,
    summary="知识库检索",
    description="在知识库中检索相关内容",
)
async def query_knowledge(
    kb_id: str,
    request: KnowledgeQueryRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    知识库检索
    
    在指定知识库中检索与查询相关的内容
    
    Args:
        kb_id: 知识库ID
        request: 查询请求
        current_user: 当前用户
        db: 数据库会话
    
    Returns:
        KnowledgeQueryResponse: 检索结果
    """
    # 验证知识库所有权
    stmt = select(KnowledgeBase).where(
        KnowledgeBase.id == kb_id,
        KnowledgeBase.user_id == current_user["user_id"]
    )
    result = await db.execute(stmt)
    
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="知识库不存在")
    
    # 执行检索
    rag = get_rag()
    
    # 如果请求生成答案（RAG问答模式），调用完整Pipeline
    if request.generate_answer:
        rag_result = await rag.query(
            query=request.query,
            use_knowledge=True,
            doc_ids=[kb_id],
            return_context=request.return_context,
            top_k=request.top_k,
        )
        
        # 构建检索结果列表
        retrieval_results = rag_result.get("retrieval_results", [])
        result_items = [
            KnowledgeQueryResult(
                content=r.get("content", ""),
                score=r.get("score", 0.0),
                source=r.get("source", ""),
                metadata=r.get("metadata", {})
            )
            for r in retrieval_results
        ]
        
        # 构建响应，包含AI生成的答案
        return KnowledgeQueryResponse(
            query=request.query,
            results=result_items,
            total_count=len(result_items),
            answer=rag_result.get("answer", ""),
            model=rag_result.get("model", ""),
        )
    
    # 仅检索模式（原逻辑）
    results = await rag.retrieve(
        query=request.query,
        top_k=request.top_k,
        doc_ids=[kb_id],
        use_knowledge=True
    )
    
    # 过滤低于阈值的结果
    filtered_results = [
        r for r in results
        if r.score >= request.similarity_threshold
    ]
    
    return KnowledgeQueryResponse(
        query=request.query,
        results=[
            KnowledgeQueryResult(
                content=r.chunk.content,
                score=r.score,
                source=r.chunk.metadata.get("title", ""),
                metadata=r.chunk.metadata
            )
            for r in filtered_results
        ],
        total_count=len(filtered_results)
    )


@router.post(
    "/bases/{kb_id}/chat",
    summary="知识库问答",
    description="基于知识库内容进行RAG问答",
)
async def rag_chat(
    kb_id: str,
    request: KnowledgeQueryRequest,
    system_prompt: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    RAG知识库问答
    
    结合知识库检索和大语言模型生成答案
    
    Args:
        kb_id: 知识库ID
        request: 问题请求
        system_prompt: 自定义系统提示词
        current_user: 当前用户
        db: 数据库会话
    
    Returns:
        dict: 包含答案和检索上下文
    
    Note:
        LLM生成部分需要接入实际的LLM服务
    """
    # 验证知识库所有权
    stmt = select(KnowledgeBase).where(
        KnowledgeBase.id == kb_id,
        KnowledgeBase.user_id == current_user["user_id"]
    )
    result = await db.execute(stmt)
    
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="知识库不存在")
    
    # 执行RAG查询
    rag = get_rag()
    
    result_data = await rag.query(
        query=request.query,
        use_knowledge=True,
        doc_ids=[kb_id],
        system_prompt=system_prompt,
        return_context=True,
        top_k=request.top_k
    )
    
    # TODO: 调用LLM生成最终答案
    # 当前返回模拟答案
    
    return {
        "answer": result_data["answer"],
        "prompt": result_data["prompt"],  # 用于调试
        "context": result_data.get("retrieval_results", []),
        "model": "mock",
        "query": request.query
    }


# ============================================================
# 后台任务
# ============================================================

async def process_document_task(document_id: str, file_path: str, kb_id: str):
    """
    文档处理后台任务
    
    处理流程：
    1. 解析文档
    2. 分块
    3. 向量化
    4. 存储到向量数据库
    
    Args:
        document_id: 文档ID
        file_path: 文件路径
        kb_id: 知识库ID
    """
    from app.core.database import get_db_context
    
    async with get_db_context() as db:
        try:
            # 获取文档记录
            stmt = select(Document).where(Document.id == document_id)
            result = await db.execute(stmt)
            document = result.scalar_one_or_none()
            
            if not document:
                return
            
            # 更新状态为处理中
            document.status = "processing"
            await db.commit()
            
            # 初始化RAG Pipeline（如果尚未初始化）
            rag = await initialize_rag_pipeline(use_milvus=True)
            
            # 添加文档到RAG
            result = await rag.add_document(
                file_path=file_path,
                document_id=str(document_id),
                metadata={
                    "kb_id": kb_id,
                    "filename": document.filename,
                    "source": file_path
                }
            )
            
            if result["success"]:
                # 更新文档状态为完成
                document.status = "completed"
                document.processed_at = datetime.now()
                
                # 更新知识库统计
                kb_stmt = select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
                kb_result = await db.execute(kb_stmt)
                kb = kb_result.scalar_one()
                kb.chunk_count = (kb.chunk_count or 0) + result["chunk_count"]
                kb.updated_at = datetime.now()
            else:
                # 处理失败
                document.status = "failed"
                document.error_message = result.get("error", "未知错误")
            
            await db.commit()
        
        except Exception as e:
            # 发生异常
            try:
                stmt = select(Document).where(Document.id == document_id)
                result = await db.execute(stmt)
                document = result.scalar_one_or_none()
                
                if document:
                    document.status = "failed"
                    document.error_message = str(e)
                    await db.commit()
            except:
                pass
