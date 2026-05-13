# ============================================================
# TTS语音合成API路由 - 完整实现
# ============================================================
#
# 本模块处理TTS语音合成相关的API接口
#
# 主要功能：
# 1. 获取可用语音列表
# 2. 语音合成
# 3. 流式合成
# 4. 任务管理
#
# Author: CoolAI Team
# Date: 2026-05-13
# ============================================================

import os
import uuid
import base64
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.config import settings
from app.models import User, TTSTask
from app.schemas import (
    TTSRequest,
    VoiceInfo,
    TTSTaskResponse,
)
from app.services.tts_service import (
    TTSService,
    TTSConfig,
    TTSEngineType,
    AudioFormat,
    get_tts_service,
)


# ============================================================
# 路由配置
# ============================================================

router = APIRouter(
    prefix="/tts",
    tags=["TTS语音合成"],
    summary="TTS语音合成接口",
)


# ============================================================
# 辅助函数
# ============================================================

def get_tts() -> TTSService:
    """获取TTS服务"""
    return get_tts_service()


# ============================================================
# 语音管理
# ============================================================

@router.get(
    "/voices",
    response_model=List[dict],
    summary="获取可用语音列表",
    description="获取所有可用的TTS语音",
)
async def list_voices(
    engine: Optional[str] = Query(None, description="引擎类型(edge/openai)")
):
    """
    获取可用的语音列表
    
    可以获取所有引擎的语音，或指定引擎的语音
    
    Args:
        engine: 引擎类型（可选）
    
    Returns:
        List[dict]: 语音列表
    """
    tts = get_tts()
    
    if engine:
        try:
            engine_type = TTSEngineType(engine)
            voices = tts.list_voices_by_engine(engine_type)
        except ValueError:
            raise HTTPException(status_code=400, detail="不支持的引擎类型")
    else:
        voices = tts.list_all_voices()
    
    return [
        {
            "voice_id": v.voice_id,
            "name": v.name,
            "language": v.language,
            "gender": v.gender,
            "preview_url": v.preview_url,
            "is_custom": v.is_custom
        }
        for v in voices
    ]


# ============================================================
# 语音合成
# ============================================================

@router.post(
    "/synthesize",
    summary="语音合成",
    description="将文本转换为语音",
)
async def synthesize(
    request: TTSRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    语音合成
    
    将文本转换为语音，支持多种语音和参数调节
    
    Args:
        request: 合成请求
        current_user: 当前用户
    
    Returns:
        dict: 包含音频数据的响应
    
    Note:
        返回Base64编码的音频数据
        格式: data:audio/mp3;base64,<编码数据>
    """
    tts = get_tts()
    
    # 创建配置
    try:
        config = TTSConfig(
            engine=TTSEngineType(settings.TTS_ENGINE),
            voice=request.voice or settings.TTS_DEFAULT_VOICE,
            speed=request.speed or settings.TTS_DEFAULT_SPEED,
            pitch=request.pitch or 0,
            format=AudioFormat(request.format or "mp3")
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # 验证文本长度
    if len(request.text) > 10000:
        raise HTTPException(status_code=400, detail="文本长度不能超过10000字")
    
    if len(request.text) == 0:
        raise HTTPException(status_code=400, detail="文本不能为空")
    
    # 执行合成
    result = await tts.synthesize(
        text=request.text,
        config=config,
        return_base64=True
    )
    
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)
    
    return {
        "success": True,
        "audio_data": f"data:audio/{config.format.value};base64,{result.audio_base64}",
        "size": result.size,
        "duration": result.duration,
        "format": config.format.value
    }


@router.post(
    "/synthesize/stream",
    summary="流式语音合成",
    description="流式合成语音（SSE格式）",
)
async def synthesize_stream(
    request: TTSRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    流式语音合成
    
    使用Server-Sent Events (SSE) 流式返回音频数据
    
    Args:
        request: 合成请求
        current_user: 当前用户
    
    Returns:
        StreamingResponse: SSE流
    """
    tts = get_tts()
    
    # 创建配置
    try:
        config = TTSConfig(
            engine=TTSEngineType(settings.TTS_ENGINE),
            voice=request.voice or settings.TTS_DEFAULT_VOICE,
            speed=request.speed or settings.TTS_DEFAULT_SPEED,
            pitch=request.pitch or 0,
            format=AudioFormat(request.format or "mp3")
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # 验证文本
    if not request.text or len(request.text) > 10000:
        raise HTTPException(status_code=400, detail="文本长度必须在1-10000字之间")
    
    async def generate_stream():
        """生成SSE流"""
        try:
            async for chunk in tts.synthesize_stream(request.text, config):
                # 发送音频数据块
                chunk_b64 = base64.b64encode(chunk).decode('utf-8')
                yield f"data: {json.dumps({'type': 'audio', 'data': chunk_b64})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        
        # 发送完成信号
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# ============================================================
# 批量合成
# ============================================================

@router.post(
    "/batch",
    summary="批量语音合成",
    description="批量合成多条语音",
)
async def batch_synthesize(
    tasks: List[TTSRequest],
    current_user: dict = Depends(get_current_user)
):
    """
    批量语音合成
    
    一次性合成多条语音
    
    Args:
        tasks: 任务列表
        current_user: 当前用户
    
    Returns:
        dict: 批量任务结果
    """
    tts = get_tts()
    
    if len(tasks) > 10:
        raise HTTPException(status_code=400, detail="单次最多支持10条任务")
    
    results = []
    
    for i, task in enumerate(tasks):
        try:
            config = TTSConfig(
                engine=TTSEngineType(settings.TTS_ENGINE),
                voice=task.voice or settings.TTS_DEFAULT_VOICE,
                speed=task.speed or settings.TTS_DEFAULT_SPEED,
                pitch=task.pitch or 0,
                format=AudioFormat(task.format or "mp3")
            )
            
            result = await tts.synthesize(
                text=task.text,
                config=config,
                return_base64=True
            )
            
            results.append({
                "index": i,
                "success": result.success,
                "audio_data": f"data:audio/{config.format.value};base64,{result.audio_base64}" if result.success else None,
                "error": result.error
            })
        
        except Exception as e:
            results.append({
                "index": i,
                "success": False,
                "error": str(e)
            })
    
    return {
        "total": len(tasks),
        "success_count": sum(1 for r in results if r["success"]),
        "results": results
    }


# ============================================================
# 任务管理
# ============================================================

@router.get(
    "/tasks",
    response_model=List[TTSTaskResponse],
    summary="获取任务列表",
    description="获取当前用户的历史合成任务",
)
async def list_tasks(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取TTS任务列表
    
    Args:
        skip: 分页偏移
        limit: 返回数量
        current_user: 当前用户
        db: 数据库会话
    
    Returns:
        List[TTSTaskResponse]: 任务列表
    """
    stmt = (
        select(TTSTask)
        .where(TTSTask.user_id == current_user["user_id"])
        .order_by(desc(TTSTask.created_at))
        .offset(skip)
        .limit(limit)
    )
    
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get(
    "/tasks/{task_id}",
    summary="获取任务详情",
    description="获取指定任务的详细信息",
)
async def get_task(
    task_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取任务详情
    
    Args:
        task_id: 任务ID
        current_user: 当前用户
        db: 数据库会话
    
    Returns:
        dict: 任务详情
    """
    stmt = select(TTSTask).where(
        TTSTask.id == task_id,
        TTSTask.user_id == current_user["user_id"]
    )
    
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return task


@router.get(
    "/tasks/{task_id}/audio",
    summary="下载音频",
    description="下载任务合成的音频文件",
)
async def download_audio(
    task_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    下载合成的音频文件
    
    Args:
        task_id: 任务ID
        current_user: 当前用户
        db: 数据库会话
    
    Returns:
        FileResponse: 音频文件
    """
    stmt = select(TTSTask).where(
        TTSTask.id == task_id,
        TTSTask.user_id == current_user["user_id"]
    )
    
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task.status != "completed" or not task.output_path:
        raise HTTPException(status_code=400, detail="音频尚未生成")
    
    if not os.path.exists(task.output_path):
        raise HTTPException(status_code=404, detail="音频文件不存在")
    
    return FileResponse(
        path=task.output_path,
        filename=f"tts_{task_id}.mp3",
        media_type="audio/mpeg"
    )


@router.delete(
    "/tasks/{task_id}",
    status_code=204,
    summary="删除任务",
    description="删除指定的合成任务",
)
async def delete_task(
    task_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除TTS任务
    
    Args:
        task_id: 任务ID
        current_user: 当前用户
        db: 数据库会话
    """
    stmt = select(TTSTask).where(
        TTSTask.id == task_id,
        TTSTask.user_id == current_user["user_id"]
    )
    
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 删除音频文件
    if task.output_path and os.path.exists(task.output_path):
        os.remove(task.output_path)
    
    await db.delete(task)
    await db.commit()


# ============================================================
# 后台任务处理
# ============================================================

async def process_tts_task(
    task_id: str,
    text: str,
    config_dict: dict,
    output_path: str
):
    """
    TTS后台处理任务
    
    Args:
        task_id: 任务ID
        text: 待合成文本
        config_dict: 配置字典
        output_path: 输出路径
    """
    from app.core.database import get_db_context
    
    tts = get_tts()
    
    async with get_db_context() as db:
        try:
            # 获取任务
            stmt = select(TTSTask).where(TTSTask.id == task_id)
            result = await db.execute(stmt)
            task = result.scalar_one_or_none()
            
            if not task:
                return
            
            # 更新状态
            task.status = "processing"
            await db.commit()
            
            # 创建配置
            config = TTSConfig(
                engine=TTSEngineType(config_dict.get("engine", "edge")),
                voice=config_dict.get("voice", "zh-CN-XiaoxiaoNeural"),
                speed=config_dict.get("speed", 1.0),
                pitch=config_dict.get("pitch", 0),
                format=AudioFormat(config_dict.get("format", "mp3"))
            )
            
            # 执行合成
            result = await tts.synthesize(
                text=text,
                config=config,
                output_path=output_path
            )
            
            if result.success:
                task.status = "completed"
                task.output_path = output_path
                task.completed_at = datetime.now()
            else:
                task.status = "failed"
                task.error_message = result.error
            
            await db.commit()
        
        except Exception as e:
            try:
                stmt = select(TTSTask).where(TTSTask.id == task_id)
                result = await db.execute(stmt)
                task = result.scalar_one_or_none()
                
                if task:
                    task.status = "failed"
                    task.error_message = str(e)
                    await db.commit()
            except:
                pass


# ============================================================
# 辅助函数 - JSON序列化
# ============================================================

import json

def json_default(obj):
    """JSON序列化辅助函数"""
    if hasattr(obj, '__dict__'):
        return obj.__dict__
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
