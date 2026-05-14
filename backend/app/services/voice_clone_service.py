# ============================================================
# 声音克隆服务
# ============================================================
#
# 提供声音克隆功能：
# 1. 参考音频上传与管理
# 2. 声音模型训练（XTTS-v2 / So-VITS-SVC）
# 3. 克隆语音合成
#
# 设计说明：
# - 优先使用 XTTS-v2 (Coqui TTS)，支持零样本克隆
# - GPU不可用时降级为 Edge-TTS + 音色调整模拟
# - 训练任务异步执行，支持进度查询
#
# 外部依赖：
# - Coqui TTS (pip install TTS) - 需要GPU
# - soundfile - 音频文件处理
#
# Author: CoolAI Team
# Date: 2026-05-13
# ============================================================

import os
import json
import uuid
import logging
import asyncio
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)


# ============================================================
# 数据类定义
# ============================================================

class CloneEngine(str, Enum):
    """克隆引擎类型"""
    XTTS_V2 = "xtts_v2"           # Coqui XTTS-v2，零样本克隆（推荐）
    SO_VITS_SVC = "so_vits_svc"   # So-VITS-SVC，需要训练
    EDGE_SIMULATE = "edge_simulate"  # Edge-TTS模拟（降级方案）


@dataclass
class CloneConfig:
    """克隆配置"""
    engine: CloneEngine = CloneEngine.XTTS_V2
    language: str = "zh"           # 语言
    speed: float = 1.0             # 语速
    reference_audio_path: str = ""  # 参考音频路径


@dataclass
class CloneTask:
    """克隆训练任务"""
    task_id: str
    model_id: str
    status: str = "pending"       # pending/training/ready/failed
    progress: float = 0.0         # 0.0 ~ 1.0
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None


# ============================================================
# XTTS-v2 引擎 (零样本克隆)
# ============================================================

class XTTSv2Engine:
    """
    XTTS-v2 声音克隆引擎
    
    使用 Coqui TTS 的 XTTS-v2 模型
    支持：零样本语音克隆（仅需3秒参考音频）
    
    安装：pip install TTS
    要求：GPU（推荐显存 >= 4GB）
    """
    
    def __init__(self):
        self._model = None
        self._device = None
        self._available = False
        self._initialized = False
    
    def _try_init(self) -> bool:
        """尝试初始化模型"""
        if self._initialized:
            return self._available
        
        self._initialized = True
        
        try:
            import torch
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"XTTS-v2 使用设备: {self._device}")
            
            # 尝试加载模型
            from TTS.api import TTS
            self._model = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(self._device)
            self._available = True
            logger.info("XTTS-v2 模型加载成功")
            return True
        except ImportError:
            logger.warning("TTS库未安装，请执行: pip install TTS")
            return False
        except Exception as e:
            logger.warning(f"XTTS-v2 初始化失败: {e}")
            return False
    
    @property
    def is_available(self) -> bool:
        """检查引擎是否可用"""
        return self._try_init()
    
    async def clone_synthesize(
        self,
        text: str,
        reference_audio: str,
        output_path: str,
        language: str = "zh-cn",
        speed: float = 1.0,
    ) -> Dict[str, Any]:
        """
        使用参考音频克隆合成语音
        
        Args:
            text: 要合成的文本
            reference_audio: 参考音频文件路径
            output_path: 输出文件路径
            language: 语言代码
            speed: 语速
        
        Returns:
            合成结果字典
        """
        if not self.is_available:
            return {"success": False, "error": "XTTS-v2引擎不可用"}
        
        try:
            # XTTS-v2 合成（在线程池中执行避免阻塞）
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._model.tts_to_file(
                    text=text,
                    speaker_wav=reference_audio,
                    language=language.split("-")[0],  # zh-cn -> zh
                    file_path=output_path,
                )
            )
            
            file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
            return {
                "success": True,
                "output_path": output_path,
                "size": file_size,
                "engine": "xtts_v2",
            }
        except Exception as e:
            logger.error(f"XTTS-v2合成失败: {e}")
            return {"success": False, "error": str(e)}


# ============================================================
# Edge-TTS 模拟克隆引擎（降级方案）
# ============================================================

class EdgeSimulateEngine:
    """
    Edge-TTS 模拟克隆引擎
    
    当GPU不可用时使用Edge-TTS进行模拟：
    - 不需要GPU
    - 使用Edge-TTS的多种音色模拟不同声音
    - 音色选择基于参考音频的元数据（如性别、年龄等）
    
    这不是一个真正的声音克隆，但提供了可用的降级体验
    """
    
    # 音色映射表：根据描述关键词选择Edge-TTS音色
    VOICE_MAP = {
        "男": ["zh-CN-YunxiNeural", "zh-CN-YunyangNeural", "zh-CN-YunjianNeural"],
        "女": ["zh-CN-XiaoxiaoNeural", "zh-CN-XiaoyiNeural", "zh-CN-XiaohanNeural"],
        "default": ["zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural"],
    }
    
    def __init__(self):
        self._available = True  # Edge-TTS始终可用
    
    @property
    def is_available(self) -> bool:
        return True
    
    async def clone_synthesize(
        self,
        text: str,
        reference_audio: str,
        output_path: str,
        language: str = "zh-CN",
        speed: float = 1.0,
        voice_hint: str = "",  # 声音提示（男/女/等）
    ) -> Dict[str, Any]:
        """
        使用Edge-TTS模拟克隆合成
        
        Args:
            text: 合成文本
            reference_audio: 参考音频路径（此方案中用于提取元数据）
            output_path: 输出路径
            language: 语言
            speed: 语速
            voice_hint: 声音提示
        """
        try:
            import edge_tts
            
            # 根据提示选择音色
            voice = self._select_voice(voice_hint)
            
            communicate = edge_tts.Communicate(text, voice, rate=f"+{int((speed - 1) * 100)}%")
            await communicate.save(output_path)
            
            file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
            return {
                "success": True,
                "output_path": output_path,
                "size": file_size,
                "engine": "edge_simulate",
                "note": "使用Edge-TTS模拟克隆，非真实声音克隆",
            }
        except Exception as e:
            logger.error(f"Edge模拟合成失败: {e}")
            return {"success": False, "error": str(e)}
    
    def _select_voice(self, hint: str) -> str:
        """根据提示选择音色"""
        for key, voices in self.VOICE_MAP.items():
            if key in hint:
                return voices[hash(hint) % len(voices)]
        # 默认返回第一个
        return self.VOICE_MAP["default"][0]


# ============================================================
# 声音克隆服务
# ============================================================

class VoiceCloneService:
    """
    声音克隆业务服务层
    
    管理声音克隆的完整生命周期：
    1. 参考音频上传
    2. 声音模型创建与训练
    3. 克隆语音合成
    4. 模型管理
    
    引擎选择策略：
    - 优先 XTTS-v2（零样本，高质量）
    - 降级 Edge-TTS模拟（无需GPU）
    """
    
    def __init__(self):
        self._xtts_engine = XTTSv2Engine()
        self._edge_engine = EdgeSimulateEngine()
        self._tasks: Dict[str, CloneTask] = {}  # 训练任务缓存
        self._output_dir = os.path.join(settings.TTS_OUTPUT_DIR, "clone")
        os.makedirs(self._output_dir, exist_ok=True)
    
    def get_available_engine(self) -> str:
        """获取当前可用的克隆引擎"""
        if self._xtts_engine.is_available:
            return CloneEngine.XTTS_V2.value
        return CloneEngine.EDGE_SIMULATE.value
    
    async def upload_reference_audio(
        self,
        user_id: str,
        model_id: str,
        audio_data: bytes,
        filename: str,
    ) -> Dict[str, Any]:
        """
        上传参考音频
        
        Args:
            user_id: 用户ID
            model_id: 声音模型ID
            audio_data: 音频二进制数据
            filename: 原始文件名
        
        Returns:
            上传结果
        """
        # 创建存储目录
        ref_dir = os.path.join(self._output_dir, user_id, "references")
        os.makedirs(ref_dir, exist_ok=True)
        
        # 生成唯一文件名
        ext = Path(filename).suffix or ".wav"
        ref_filename = f"{model_id}_ref{ext}"
        ref_path = os.path.join(ref_dir, ref_filename)
        
        # 保存文件
        with open(ref_path, "wb") as f:
            f.write(audio_data)
        
        # 验证音频文件
        duration = await self._get_audio_duration(ref_path)
        
        return {
            "success": True,
            "reference_path": ref_path,
            "filename": ref_filename,
            "size": len(audio_data),
            "duration": duration,
        }
    
    async def start_training(
        self,
        model_id: str,
        reference_audio_path: str,
        engine: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        启动声音克隆训练
        
        对于XTTS-v2：零样本，无需训练，直接可用
        对于So-VITS-SVC：需要训练过程
        
        Args:
            model_id: 声音模型ID
            reference_audio_path: 参考音频路径
            engine: 指定引擎
        
        Returns:
            训练任务信息
        """
        task_id = str(uuid.uuid4())
        
        # 确定使用的引擎
        if engine == CloneEngine.XTTS_V2.value and self._xtts_engine.is_available:
            # XTTS-v2 零样本：直接标记为就绪
            task = CloneTask(
                task_id=task_id,
                model_id=model_id,
                status="ready",
                progress=1.0,
            )
            self._tasks[task_id] = task
            return {
                "task_id": task_id,
                "model_id": model_id,
                "status": "ready",
                "progress": 1.0,
                "engine": "xtts_v2",
                "message": "XTTS-v2零样本克隆，无需训练",
            }
        
        # 降级方案：使用Edge-TTS模拟
        task = CloneTask(
            task_id=task_id,
            model_id=model_id,
            status="ready",
            progress=1.0,
        )
        self._tasks[task_id] = task
        
        return {
            "task_id": task_id,
            "model_id": model_id,
            "status": "ready",
            "progress": 1.0,
            "engine": "edge_simulate",
            "message": "GPU不可用，使用Edge-TTS模拟克隆",
        }
    
    async def synthesize(
        self,
        text: str,
        model_id: str,
        reference_audio_path: str,
        language: str = "zh",
        speed: float = 1.0,
        output_format: str = "mp3",
    ) -> Dict[str, Any]:
        """
        使用克隆的声音合成语音
        
        Args:
            text: 待合成文本
            model_id: 声音模型ID
            reference_audio_path: 参考音频路径
            language: 语言
            speed: 语速
            output_format: 输出格式
        
        Returns:
            合成结果
        """
        output_filename = f"clone_{model_id}_{uuid.uuid4().hex[:8]}.{output_format}"
        output_path = os.path.join(self._output_dir, output_filename)
        
        # 优先尝试XTTS-v2
        if self._xtts_engine.is_available:
            result = await self._xtts_engine.clone_synthesize(
                text=text,
                reference_audio=reference_audio_path,
                output_path=output_path,
                language=language,
                speed=speed,
            )
            if result.get("success"):
                return result
            logger.warning(f"XTTS-v2合成失败，降级为Edge模拟: {result.get('error')}")
        
        # 降级为Edge-TTS模拟
        result = await self._edge_engine.clone_synthesize(
            text=text,
            reference_audio=reference_audio_path,
            output_path=output_path,
            language=language,
            speed=speed,
        )
        return result
    
    def get_training_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取训练任务状态"""
        task = self._tasks.get(task_id)
        if not task:
            return None
        return {
            "task_id": task.task_id,
            "model_id": task.model_id,
            "status": task.status,
            "progress": task.progress,
            "error": task.error,
        }
    
    async def _get_audio_duration(self, filepath: str) -> float:
        """获取音频文件时长（秒）"""
        try:
            import soundfile as sf
            info = sf.info(filepath)
            return info.duration
        except ImportError:
            pass
        try:
            # 尝试使用wave模块
            import wave
            with wave.open(filepath, 'rb') as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                return frames / float(rate)
        except Exception:
            return 0.0


# ============================================================
# 全局实例
# ============================================================

_voice_clone_service: Optional[VoiceCloneService] = None

def get_voice_clone_service() -> VoiceCloneService:
    """获取声音克隆服务实例"""
    global _voice_clone_service
    if _voice_clone_service is None:
        _voice_clone_service = VoiceCloneService()
    return _voice_clone_service

def initialize_voice_clone_service() -> VoiceCloneService:
    """初始化声音克隆服务"""
    return get_voice_clone_service()
