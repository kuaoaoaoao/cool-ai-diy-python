# ============================================================
# 声音克隆API路由
# ============================================================
#
# 声音克隆功能接口：
# 1. 声音模型CRUD
# 2. 参考音频上传
# 3. 启动克隆训练
# 4. 克隆语音合成
#
# Author: CoolAI Team
# Date: 2026-05-13
# ============================================================

import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import User, VoiceModel
from app.schemas import (
    VoiceModelCreate,
    VoiceModelResponse,
)
from app.services.voice_clone_service import get_voice_clone_service


router = APIRouter(
    prefix="/voice",
    tags=["声音克隆"],
    summary="声音克隆接口",
)


# ============================================================
# 声音模型CRUD
# ============================================================

@router.get(
    "/models",
    summary="获取声音模型列表",
    description="获取当前用户的所有声音模型",
)
async def list_voice_models(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户的声音模型列表"""
    stmt = select(VoiceModel).where(
        VoiceModel.user_id == current_user["user_id"]
    ).order_by(VoiceModel.created_at.desc())
    
    result = await db.execute(stmt)
    models = result.scalars().all()
    
    # 获取可用引擎
    clone_service = get_voice_clone_service()
    available_engine = clone_service.get_available_engine()
    
    return {
        "models": [
            {
                "id": str(m.id),
                "name": m.name,
                "description": m.description,
                "model_path": m.model_path,
                "reference_audio": m.reference_audio,
                "status": m.status,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "updated_at": m.updated_at.isoformat() if m.updated_at else None,
            }
            for m in models
        ],
        "available_engine": available_engine,
    }


@router.post(
    "/models",
    summary="创建声音模型",
    description="创建一个新的声音克隆模型",
)
async def create_voice_model(
    data: VoiceModelCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建声音模型"""
    model = VoiceModel(
        user_id=current_user["user_id"],
        name=data.name,
        description=data.description,
        status="pending",  # 等待上传参考音频
    )
    
    db.add(model)
    await db.commit()
    await db.refresh(model)
    
    return {
        "id": str(model.id),
        "name": model.name,
        "description": model.description,
        "status": model.status,
        "created_at": model.created_at.isoformat() if model.created_at else None,
    }


@router.get(
    "/models/{model_id}",
    summary="获取声音模型详情",
)
async def get_voice_model(
    model_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取声音模型详情"""
    stmt = select(VoiceModel).where(
        VoiceModel.id == model_id,
        VoiceModel.user_id == current_user["user_id"]
    )
    result = await db.execute(stmt)
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="声音模型不存在")
    
    return {
        "id": str(model.id),
        "name": model.name,
        "description": model.description,
        "model_path": model.model_path,
        "reference_audio": model.reference_audio,
        "status": model.status,
        "created_at": model.created_at.isoformat() if model.created_at else None,
        "updated_at": model.updated_at.isoformat() if model.updated_at else None,
    }


@router.delete(
    "/models/{model_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除声音模型",
)
async def delete_voice_model(
    model_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除声音模型"""
    stmt = select(VoiceModel).where(
        VoiceModel.id == model_id,
        VoiceModel.user_id == current_user["user_id"]
    )
    result = await db.execute(stmt)
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="声音模型不存在")
    
    # 清理模型文件
    if model.model_path and os.path.exists(model.model_path):
        try:
            os.remove(model.model_path)
        except OSError:
            pass
    
    if model.reference_audio and os.path.exists(model.reference_audio):
        try:
            os.remove(model.reference_audio)
        except OSError:
            pass
    
    await db.delete(model)
    await db.commit()


# ============================================================
# 参考音频上传
# ============================================================

@router.post(
    "/models/{model_id}/reference",
    summary="上传参考音频",
    description="为声音模型上传参考音频（支持wav/mp3格式，建议3-30秒）",
)
async def upload_reference_audio(
    model_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """上传参考音频"""
    # 验证模型归属
    stmt = select(VoiceModel).where(
        VoiceModel.id == model_id,
        VoiceModel.user_id == current_user["user_id"]
    )
    result = await db.execute(stmt)
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="声音模型不存在")
    
    # 验证文件格式
    allowed_types = ["audio/wav", "audio/mpeg", "audio/mp3", "audio/x-wav"]
    if file.content_type not in allowed_types:
        # 也通过扩展名检查
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in [".wav", ".mp3"]:
            raise HTTPException(status_code=400, detail="仅支持WAV和MP3格式")
    
    # 读取音频数据
    audio_data = await file.read()
    if len(audio_data) > 50 * 1024 * 1024:  # 50MB限制
        raise HTTPException(status_code=400, detail="音频文件不能超过50MB")
    
    # 上传到克隆服务
    clone_service = get_voice_clone_service()
    upload_result = await clone_service.upload_reference_audio(
        user_id=current_user["user_id"],
        model_id=model_id,
        audio_data=audio_data,
        filename=file.filename or "audio.wav",
    )
    
    if not upload_result.get("success"):
        raise HTTPException(status_code=500, detail="音频上传失败")
    
    # 更新模型记录
    model.reference_audio = upload_result["reference_path"]
    model.status = "ready" if clone_service.get_available_engine() != "edge_simulate" else "ready"
    await db.commit()
    
    return {
        "success": True,
        "reference_path": upload_result["reference_path"],
        "duration": upload_result.get("duration", 0),
        "size": upload_result.get("size", 0),
    }


# ============================================================
# 克隆训练
# ============================================================

@router.post(
    "/models/{model_id}/train",
    summary="启动克隆训练",
    description="启动声音克隆训练（XTTS-v2零样本克隆无需等待）",
)
async def train_voice_model(
    model_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """启动声音克隆训练"""
    stmt = select(VoiceModel).where(
        VoiceModel.id == model_id,
        VoiceModel.user_id == current_user["user_id"]
    )
    result = await db.execute(stmt)
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="声音模型不存在")
    
    if not model.reference_audio:
        raise HTTPException(status_code=400, detail="请先上传参考音频")
    
    # 启动训练
    clone_service = get_voice_clone_service()
    train_result = await clone_service.start_training(
        model_id=model_id,
        reference_audio_path=model.reference_audio,
    )
    
    # 更新模型状态
    model.status = train_result.get("status", "training")
    model.model_path = model.reference_audio  # XTTS-v2直接使用参考音频
    await db.commit()
    
    return train_result


# ============================================================
# 克隆语音合成
# ============================================================

from pydantic import BaseModel as PydanticModel, Field

class CloneSynthesizeRequest(PydanticModel):
    """克隆合成请求"""
    text: str = Field(..., min_length=1, max_length=5000, description="待合成文本")
    model_id: str = Field(..., description="声音模型ID")
    speed: float = Field(default=1.0, ge=0.5, le=2.0, description="语速")
    format: str = Field(default="mp3", description="输出格式")


@router.post(
    "/synthesize",
    summary="克隆语音合成",
    description="使用克隆的声音模型合成语音",
)
async def clone_synthesize(
    request: CloneSynthesizeRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """使用克隆声音合成语音"""
    # 验证模型
    stmt = select(VoiceModel).where(
        VoiceModel.id == request.model_id,
        VoiceModel.user_id == current_user["user_id"]
    )
    result = await db.execute(stmt)
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="声音模型不存在")
    
    if model.status not in ("ready", "training"):
        raise HTTPException(status_code=400, detail=f"模型状态为{model.status}，无法合成")
    
    if not model.reference_audio:
        raise HTTPException(status_code=400, detail="模型缺少参考音频")
    
    # 合成
    clone_service = get_voice_clone_service()
    synth_result = await clone_service.synthesize(
        text=request.text,
        model_id=request.model_id,
        reference_audio_path=model.reference_audio,
        output_format=request.format,
        speed=request.speed,
    )
    
    if not synth_result.get("success"):
        raise HTTPException(status_code=500, detail=synth_result.get("error", "合成失败"))
    
    return {
        "success": True,
        "output_path": synth_result.get("output_path"),
        "size": synth_result.get("size", 0),
        "engine": synth_result.get("engine", "unknown"),
    }


# ============================================================
# 获取可用引擎信息
# ============================================================

@router.get(
    "/engines",
    summary="获取可用克隆引擎",
)
async def get_available_engines():
    """获取当前可用的声音克隆引擎"""
    clone_service = get_voice_clone_service()
    engine = clone_service.get_available_engine()
    
    engines_info = [
        {
            "name": "xtts_v2",
            "display_name": "XTTS-v2 零样本克隆",
            "available": engine == "xtts_v2",
            "description": "Coqui XTTS-v2，仅需3秒参考音频即可克隆，需要GPU",
            "requires_gpu": True,
        },
        {
            "name": "edge_simulate",
            "display_name": "Edge-TTS 音色模拟",
            "available": True,
            "description": "使用Edge-TTS模拟不同音色，无需GPU，非真实克隆",
            "requires_gpu": False,
        },
    ]
    
    return {
        "current_engine": engine,
        "engines": engines_info,
    }
