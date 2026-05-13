# ============================================================
# TTS (Text-to-Speech) 语音合成服务 - 完整实现
# ============================================================
#
# 本模块实现文字转语音(TTS)功能，支持：
# 1. Edge-TTS：微软Edge在线TTS，免费高质量
# 2. CosyVoice：阿里开源中文TTS
# 3. 声音克隆集成
# 4. 丰富的参数控制（语速、音调、停顿）
# 5. 多种音频格式输出
#
# 使用方法：
# from app.services.tts_service import TTSService, initialize_tts_service
#
# tts = initialize_tts_service()
# result = await tts.synthesize("你好，世界！")
#
# Author: CoolAI Team
# Date: 2026-05-13
# ============================================================

import os
import uuid
import asyncio
import base64
import json
import hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any, AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import tempfile

# HTTP客户端
import httpx

# 配置文件
from app.core.config import settings


# ============================================================
# 枚举定义
# ============================================================

class TTSEngineType(str, Enum):
    """
    TTS引擎类型枚举
    
    定义支持的TTS引擎
    """
    # Edge TTS：微软Edge浏览器的在线TTS服务
    EDGE = "edge"
    # CosyVoice：阿里开源中文TTS
    COSY_VOICE = "cosyvoice"
    # OpenAI TTS
    OPENAI = "openai"
    # 克隆声音引擎
    VOICE_CLONE = "voice_clone"


class AudioFormat(str, Enum):
    """音频格式枚举"""
    MP3 = "mp3"
    WAV = "wav"
    OGG = "ogg"
    WEBM = "webm"


# ============================================================
# 数据类定义
# ============================================================

@dataclass
class TTSConfig:
    """
    TTS配置数据类
    
    包含语音合成的所有配置参数
    
    Attributes:
        engine: 使用的TTS引擎
        voice: 语音名称/ID
        speed: 语速倍率 (0.5-2.0)
        pitch: 音调调整 (-50到50)
        volume: 音量调整 (0-100)
        format: 输出音频格式
        sample_rate: 采样率
    """
    engine: TTSEngineType = TTSEngineType.EDGE
    voice: str = "zh-CN-XiaoxiaoNeural"
    speed: float = 1.0
    pitch: int = 0
    volume: int = 100
    format: AudioFormat = AudioFormat.MP3
    sample_rate: int = 24000
    
    def validate(self):
        """验证配置参数"""
        if not 0.5 <= self.speed <= 2.0:
            raise ValueError("语速必须在0.5-2.0之间")
        if not -50 <= self.pitch <= 50:
            raise ValueError("音调必须在-50到50之间")
        if not 0 <= self.volume <= 100:
            raise ValueError("音量必须在0-100之间")


@dataclass
class VoiceInfo:
    """
    语音信息数据类
    
    描述一个可用的语音
    
    Attributes:
        voice_id: 语音唯一标识
        name: 显示名称
        language: 支持的语言
        gender: 性别
        preview_url: 预览音频URL
        is_custom: 是否为自定义（克隆）声音
    """
    voice_id: str
    name: str
    language: str
    gender: str
    preview_url: Optional[str] = None
    is_custom: bool = False


@dataclass
class TTSTask:
    """
    TTS任务数据类
    
    表示一个语音合成任务
    
    Attributes:
        task_id: 任务唯一ID
        text: 待合成的文本
        config: 合成配置
        status: 任务状态
        output_path: 输出文件路径
        error: 错误信息
    """
    task_id: str
    text: str
    config: TTSConfig
    status: str = "pending"
    output_path: Optional[str] = None
    error: Optional[str] = None


@dataclass
class SynthesisResult:
    """
    合成结果数据类
    
    包含合成结果的音频数据和元信息
    """
    success: bool
    audio_data: Optional[bytes] = None
    audio_base64: Optional[str] = None
    output_path: Optional[str] = None
    duration: Optional[float] = None
    size: int = 0
    error: Optional[str] = None


# ============================================================
# TTS引擎基类
# ============================================================

class TTSEngineBase(ABC):
    """
    TTS引擎抽象基类
    
    定义TTS引擎的接口规范
    不同的TTS引擎需要实现此接口
    
    设计模式：策略模式（Strategy Pattern）
    """
    
    @abstractmethod
    async def synthesize(
        self,
        text: str,
        config: TTSConfig
    ) -> SynthesisResult:
        """
        合成语音
        
        将文本转换为语音并返回音频数据
        
        Args:
            text: 待合成的文本
            config: 合成配置
        
        Returns:
            SynthesisResult: 合成结果
        """
        pass
    
    @abstractmethod
    async def synthesize_to_file(
        self,
        text: str,
        config: TTSConfig,
        output_path: str
    ) -> SynthesisResult:
        """
        合成语音并保存到文件
        
        Args:
            text: 待合成的文本
            config: 合成配置
            output_path: 输出文件路径
        
        Returns:
            SynthesisResult: 合成结果
        """
        pass
    
    @abstractmethod
    async def synthesize_stream(
        self,
        text: str,
        config: TTSConfig
    ) -> AsyncIterator[bytes]:
        """
        流式合成语音
        
        支持边合成边返回音频流
        
        Args:
            text: 待合成的文本
            config: 合成配置
        
        Yields:
            bytes: 音频数据块
        """
        pass
    
    @abstractmethod
    def list_voices(self) -> List[VoiceInfo]:
        """
        列出可用的语音
        
        Returns:
            List[VoiceInfo]: 语音信息列表
        """
        pass


# ============================================================
# Edge TTS 引擎
# ============================================================

class EdgeTTSEngine(TTSEngineBase):
    """
    Edge TTS 引擎实现
    
    使用Microsoft Edge浏览器的在线TTS服务
    优点：
    - 免费使用
    - 语音质量高
    - 支持中文
    - 响应速度快
    
    缺点：
    - 需要网络连接
    - 有速率限制
    
    安装：pip install edge-tts
    """
    
    def __init__(self):
        """初始化Edge TTS引擎"""
        self._edge_tts = None
        self._available_voices = self._load_default_voices()
    
    def _get_edge_tts(self):
        """懒加载edge-tts"""
        if self._edge_tts is None:
            try:
                import edge_tts
                self._edge_tts = edge_tts
            except ImportError:
                raise ImportError(
                    "请安装edge-tts: pip install edge-tts\n"
                    "或者使用: pip install coolai[tts]"
                )
        return self._edge_tts
    
    def _load_default_voices(self) -> List[VoiceInfo]:
        """
        加载默认语音列表
        
        Edge TTS提供的中文语音
        
        Returns:
            List[VoiceInfo]: 语音信息列表
        """
        return [
            # ============================================================
            # 中文女声
            # ============================================================
            VoiceInfo(
                voice_id="zh-CN-XiaoxiaoNeural",
                name="晓晓（女声）",
                language="zh-CN",
                gender="Female",
                preview_url=None
            ),
            VoiceInfo(
                voice_id="zh-CN-XiaoyiNeural",
                name="小艺（女声）",
                language="zh-CN",
                gender="Female"
            ),
            VoiceInfo(
                voice_id="zh-CN-YunxiNeural",
                name="云希（女声）",
                language="zh-CN",
                gender="Female"
            ),
            VoiceInfo(
                voice_id="zh-CN-YunyangNeural",
                name="云扬（女声）",
                language="zh-CN",
                gender="Female"
            ),
            # ============================================================
            # 中文男声
            # ============================================================
            VoiceInfo(
                voice_id="zh-CN-YunfeiNeural",
                name="云飞（男声）",
                language="zh-CN",
                gender="Male"
            ),
            VoiceInfo(
                voice_id="zh-CN-YunyangNeural",
                name="云扬（男声）",
                language="zh-CN",
                gender="Male"
            ),
            # ============================================================
            # 粤语
            # ============================================================
            VoiceInfo(
                voice_id="zh-CN-XiaoxiaoNeural",
                name="晓晓（粤语）",
                language="zh-CN",
                gender="Female"
            ),
            # ============================================================
            # 英文（备用）
            # ============================================================
            VoiceInfo(
                voice_id="en-US-JennyNeural",
                name="Jenny（英文女声）",
                language="en-US",
                gender="Female"
            ),
            VoiceInfo(
                voice_id="en-US-GuyNeural",
                name="Guy（英文男声）",
                language="en-US",
                gender="Male"
            ),
        ]
    
    async def synthesize(
        self,
        text: str,
        config: TTSConfig
    ) -> SynthesisResult:
        """
        合成语音
        
        使用edge-tts库进行语音合成
        
        Args:
            text: 待合成的文本
            config: 合成配置
        
        Returns:
            SynthesisResult: 合成结果
        """
        try:
            edge_tts = self._get_edge_tts()
            
            # 创建 Communicate 对象
            communicate = edge_tts.Communicate(
                text=text,
                voice=config.voice,
                rate=f"{int((config.speed - 1) * 100):+d}%",
                pitch=f"{config.pitch}Hz"
            )
            
            # 合成到内存
            audio_data = await communicate.presynthesize()
            
            # 如果需要转换格式
            if config.format != AudioFormat.MP3:
                audio_data = await self._convert_format(audio_data, config.format)
            
            # 计算时长（估算）
            duration = len(text) / (config.speed * 5)  # 粗略估算
            
            return SynthesisResult(
                success=True,
                audio_data=audio_data,
                audio_base64=base64.b64encode(audio_data).decode('utf-8'),
                duration=duration,
                size=len(audio_data)
            )
        
        except Exception as e:
            return SynthesisResult(
                success=False,
                error=str(e)
            )
    
    async def synthesize_to_file(
        self,
        text: str,
        config: TTSConfig,
        output_path: str
    ) -> SynthesisResult:
        """
        合成语音并保存到文件
        
        Args:
            text: 待合成的文本
            config: 合成配置
            output_path: 输出文件路径
        
        Returns:
            SynthesisResult: 合成结果
        """
        try:
            edge_tts = self._get_edge_tts()
            
            # 确保目录存在
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # 创建 Communicate 对象
            communicate = edge_tts.Communicate(
                text=text,
                voice=config.voice,
                rate=f"{int((config.speed - 1) * 100):+d}%",
                pitch=f"{config.pitch}Hz"
            )
            
            # 合成到文件
            await communicate.save(output_path)
            
            # 获取文件大小
            file_size = Path(output_path).stat().st_size
            
            return SynthesisResult(
                success=True,
                output_path=output_path,
                size=file_size
            )
        
        except Exception as e:
            return SynthesisResult(
                success=False,
                error=str(e)
            )
    
    async def synthesize_stream(
        self,
        text: str,
        config: TTSConfig
    ) -> AsyncIterator[bytes]:
        """
        流式合成语音
        
        Args:
            text: 待合成的文本
            config: 合成配置
        
        Yields:
            bytes: 音频数据块
        """
        edge_tts = self._get_edge_tts()
        
        communicate = edge_tts.Communicate(
            text=text,
            voice=config.voice,
            rate=f"{int((config.speed - 1) * 100):+d}%",
            pitch=f"{config.pitch}Hz"
        )
        
        # 流式返回
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]
    
    async def _convert_format(
        self,
        audio_data: bytes,
        target_format: AudioFormat
    ) -> bytes:
        """
        转换音频格式
        
        注意：需要系统安装ffmpeg
        
        Args:
            audio_data: 原始音频数据
            target_format: 目标格式
        
        Returns:
            bytes: 转换后的音频数据
        """
        # 临时保存为MP3
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as mp3_file:
            mp3_file.write(audio_data)
            mp3_path = mp3_file.name
        
        try:
            # 调用ffmpeg转换
            output_path = mp3_path.replace('.mp3', f'.{target_format.value}')
            
            process = await asyncio.create_subprocess_exec(
                'ffmpeg',
                '-i', mp3_path,
                '-y',  # 覆盖输出文件
                output_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await process.communicate()
            
            with open(output_path, 'rb') as f:
                result = f.read()
            
            # 清理临时文件
            os.unlink(output_path)
            
            return result
        
        finally:
            os.unlink(mp3_path)
    
    def list_voices(self) -> List[VoiceInfo]:
        """
        列出可用的语音
        
        Returns:
            List[VoiceInfo]: 语音信息列表
        """
        return self._available_voices.copy()


# ============================================================
# CosyVoice 引擎（阿里开源TTS）
# ============================================================

class CosyVoiceEngine(TTSEngineBase):
    """
    CosyVoice 引擎实现
    
    阿里巴巴开源的中文TTS引擎
    优点：
    - 开源免费，可本地部署
    - 支持声音克隆
    - 中文效果好
    
    缺点：
    - 需要GPU支持
    - 部署相对复杂
    
    模型下载：
    https://www.modelscope.cn/models/iic/CosyVoice-300M
    
    安装：
    pip install cosyvoice
    """
    
    def __init__(
        self,
        model_path: str = "./models/CosyVoice-300M",
        device: str = "cuda"
    ):
        """
        初始化CosyVoice引擎
        
        Args:
            model_path: 模型文件路径
            device: 运行设备 (cuda/cpu)
        """
        self.model_path = model_path
        self.device = device
        self._model = None
        self._loaded = False
    
    def _ensure_loaded(self):
        """确保模型已加载"""
        if self._loaded:
            return
        
        try:
            from cosyvoice.cli import CosyVoice
            from cosyvoice.utils.file_utils import load_wav
            
            self._model = CosyVoice(self.model_path)
            self._loaded = True
        except ImportError:
            raise ImportError(
                "请安装CosyVoice: pip install cosyvoice\n"
                "详细安装说明请参考: https://github.com/modelscope/CosyVoice"
            )
    
    async def synthesize(
        self,
        text: str,
        config: TTSConfig
    ) -> SynthesisResult:
        """
        合成语音
        
        Args:
            text: 待合成的文本
            config: 合成配置
        
        Returns:
            SynthesisResult: 合成结果
        """
        try:
            self._ensure_loaded()
            
            # TODO: 实现CosyVoice合成逻辑
            # result = self._model.inference_sft(
            #     text,
            #     config.voice,
            #     speed=config.speed
            # )
            # audio_data = result['audio']
            
            # 临时返回模拟结果
            return SynthesisResult(
                success=False,
                error="CosyVoice尚未配置，请先下载模型并配置model_path"
            )
        
        except Exception as e:
            return SynthesisResult(
                success=False,
                error=str(e)
            )
    
    async def synthesize_to_file(
        self,
        text: str,
        config: TTSConfig,
        output_path: str
    ) -> SynthesisResult:
        """合成并保存到文件"""
        result = await self.synthesize(text, config)
        
        if result.success and result.audio_data:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(result.audio_data)
            result.output_path = output_path
        
        return result
    
    async def synthesize_stream(
        self,
        text: str,
        config: TTSConfig
    ) -> AsyncIterator[bytes]:
        """流式合成"""
        # CosyVoice可能需要特殊处理
        audio_data = await self.synthesize(text, config)
        if audio_data.success:
            yield audio_data.audio_data
    
    def list_voices(self) -> List[VoiceInfo]:
        """
        列出可用的语音
        
        Returns:
            List[VoiceInfo]: 语音信息列表
        """
        return [
            VoiceInfo(
                voice_id="default_female",
                name="默认女声",
                language="zh-CN",
                gender="Female"
            ),
            VoiceInfo(
                voice_id="default_male",
                name="默认男声",
                language="zh-CN",
                gender="Male"
            ),
            VoiceInfo(
                voice_id="assistant",
                name="助手音色",
                language="zh-CN",
                gender="Female"
            ),
            VoiceInfo(
                voice_id="narrator",
                name="旁白音色",
                language="zh-CN",
                gender="Male"
            ),
        ]


# ============================================================
# OpenAI TTS 引擎
# ============================================================

class OpenAITTSEngine(TTSEngineBase):
    """
    OpenAI TTS 引擎实现
    
    使用OpenAI的TTS API进行语音合成
    优点：
    - 语音质量高
    - 支持多种语音
    - 稳定性好
    
    缺点：
    - 需要API Key
    - 有使用成本
    
    安装：pip install openai
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        初始化OpenAI TTS引擎
        
        Args:
            api_key: OpenAI API Key
        """
        self.api_key = api_key or settings.OPENAI_API_KEY
        self._client = None
    
    def _get_client(self):
        """获取OpenAI客户端"""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "请安装openai: pip install openai"
                )
        return self._client
    
    async def synthesize(
        self,
        text: str,
        config: TTSConfig
    ) -> SynthesisResult:
        """
        合成语音
        
        Args:
            text: 待合成的文本
            config: 合成配置
        
        Returns:
            SynthesisResult: 合成结果
        """
        if not self.api_key:
            return SynthesisResult(
                success=False,
                error="请配置OpenAI API Key"
            )
        
        try:
            client = self._get_client()
            
            # OpenAI TTS语音映射
            voice_map = {
                "alloy": "alloy",
                "echo": "echo", 
                "fable": "fable",
                "onyx": "onyx",
                "nova": "nova",
                "shimmer": "shimmer"
            }
            voice = voice_map.get(config.voice, "alloy")
            
            # 同步调用（OpenAI SDK不支持异步）
            response = client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text,
                speed=config.speed
            )
            
            audio_data = response.content
            
            return SynthesisResult(
                success=True,
                audio_data=audio_data,
                audio_base64=base64.b64encode(audio_data).decode('utf-8'),
                size=len(audio_data)
            )
        
        except Exception as e:
            return SynthesisResult(
                success=False,
                error=str(e)
            )
    
    async def synthesize_to_file(
        self,
        text: str,
        config: TTSConfig,
        output_path: str
    ) -> SynthesisResult:
        """合成并保存到文件"""
        result = await self.synthesize(text, config)
        
        if result.success and result.audio_data:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(result.audio_data)
            result.output_path = output_path
        
        return result
    
    async def synthesize_stream(
        self,
        text: str,
        config: TTSConfig
    ) -> AsyncIterator[bytes]:
        """流式合成"""
        # OpenAI支持流式输出
        if not self.api_key:
            return
        
        client = self._get_client()
        
        voice_map = {
            "alloy": "alloy",
            "echo": "echo",
            "fable": "fable",
            "onyx": "onyx",
            "nova": "nova",
            "shimmer": "shimmer"
        }
        voice = voice_map.get(config.voice, "alloy")
        
        with client.audio.speech.with_streaming_response.create(
            model="tts-1",
            voice=voice,
            input=text,
            speed=config.speed
        ) as response:
            for chunk in response.iter_bytes():
                yield chunk
    
    def list_voices(self) -> List[VoiceInfo]:
        """
        列出可用的语音
        
        Returns:
            List[VoiceInfo]: 语音信息列表
        """
        return [
            VoiceInfo(
                voice_id="alloy",
                name="Alloy（中性）",
                language="multilingual",
                gender="Neutral"
            ),
            VoiceInfo(
                voice_id="echo",
                name="Echo（男声）",
                language="multilingual",
                gender="Male"
            ),
            VoiceInfo(
                voice_id="fable",
                name="Fable（英式）",
                language="multilingual",
                gender="Male"
            ),
            VoiceInfo(
                voice_id="onyx",
                name="Onyx（男声）",
                language="multilingual",
                gender="Male"
            ),
            VoiceInfo(
                voice_id="nova",
                name="Nova（女声）",
                language="multilingual",
                gender="Female"
            ),
            VoiceInfo(
                voice_id="shimmer",
                name="Shimmer（女声）",
                language="multilingual",
                gender="Female"
            ),
        ]


# ============================================================
# TTS 业务服务层
# ============================================================

class TTSService:
    """
    TTS 业务服务层
    
    封装TTS引擎，提供完整的语音合成服务
    负责：
    - 引擎选择和配置
    - 任务队列管理
    - 结果存储
    - API限流
    
    Attributes:
        engines: 已注册的TTS引擎
        default_engine: 默认引擎
    """
    
    def __init__(self):
        """初始化TTS服务"""
        # 引擎字典
        self.engines: Dict[TTSEngineType, TTSEngineBase] = {}
        self.default_engine: TTSEngineType = TTSEngineType.EDGE
        
        # 任务队列
        self._task_queue: Dict[str, TTSTask] = {}
        
        # 输出目录
        self.output_dir = settings.TTS_OUTPUT_DIR
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 注册默认引擎
        self._register_default_engines()
    
    def _register_default_engines(self):
        """注册默认的TTS引擎"""
        # 注册Edge-TTS
        try:
            self.register_engine(TTSEngineType.EDGE, EdgeTTSEngine())
        except ImportError:
            pass
        
        # 注册OpenAI TTS
        try:
            self.register_engine(TTSEngineType.OPENAI, OpenAITTSEngine())
        except ImportError:
            pass
    
    def register_engine(
        self,
        engine_type: TTSEngineType,
        engine: TTSEngineBase
    ):
        """
        注册TTS引擎
        
        Args:
            engine_type: 引擎类型
            engine: 引擎实例
        """
        self.engines[engine_type] = engine
        
        # 如果是第一个注册的引擎，设为默认
        if len(self.engines) == 1:
            self.default_engine = engine_type
    
    def get_engine(self, engine_type: Optional[TTSEngineType] = None) -> TTSEngineBase:
        """
        获取TTS引擎
        
        Args:
            engine_type: 引擎类型，None则使用默认
        
        Returns:
            TTSEngineBase: TTS引擎实例
        
        Raises:
            ValueError: 引擎不存在
        """
        if engine_type is None:
            engine_type = self.default_engine
        
        if engine_type not in self.engines:
            raise ValueError(f"TTS引擎不存在: {engine_type}")
        
        return self.engines[engine_type]
    
    def list_all_voices(self) -> List[VoiceInfo]:
        """
        列出所有可用的语音
        
        聚合所有引擎的语音
        
        Returns:
            List[VoiceInfo]: VoiceInfo列表
        """
        all_voices = []
        seen_ids = set()
        
        for engine_type, engine in self.engines.items():
            try:
                for voice in engine.list_voices():
                    if voice.voice_id not in seen_ids:
                        all_voices.append(voice)
                        seen_ids.add(voice.voice_id)
            except:
                pass
        
        return all_voices
    
    def list_voices_by_engine(self, engine_type: TTSEngineType) -> List[VoiceInfo]:
        """
        获取指定引擎的语音列表
        
        Args:
            engine_type: 引擎类型
        
        Returns:
            List[VoiceInfo]: 语音列表
        """
        engine = self.get_engine(engine_type)
        return engine.list_voices()
    
    async def synthesize(
        self,
        text: str,
        config: Optional[TTSConfig] = None,
        output_path: Optional[str] = None,
        return_base64: bool = False
    ) -> SynthesisResult:
        """
        合成语音
        
        主入口方法，处理语音合成请求
        
        Args:
            text: 待合成的文本
            config: 合成配置（可选）
            output_path: 输出文件路径（可选）
            return_base64: 是否返回Base64编码
        
        Returns:
            SynthesisResult: 合成结果
        """
        # 使用默认配置
        if config is None:
            config = TTSConfig(
                engine=TTSEngineType.EDGE,
                voice=settings.TTS_DEFAULT_VOICE,
                speed=settings.TTS_DEFAULT_SPEED
            )
        
        # 验证配置
        config.validate()
        
        # 获取引擎
        engine = self.get_engine(config.engine)
        
        # 确定输出路径
        if output_path is None:
            file_id = hashlib.md5(text.encode()).hexdigest()[:16]
            extension = config.format.value
            output_path = os.path.join(self.output_dir, f"{file_id}.{extension}")
        
        # 合成音频
        if output_path:
            result = await engine.synthesize_to_file(text, config, output_path)
        else:
            result = await engine.synthesize(text, config)
        
        # 返回Base64编码
        if return_base64 and result.success and result.audio_data is None:
            # 如果没有内存数据但有文件，读取文件
            if result.output_path:
                with open(result.output_path, 'rb') as f:
                    result.audio_data = f.read()
                result.audio_base64 = base64.b64encode(result.audio_data).decode('utf-8')
        
        return result
    
    async def synthesize_batch(
        self,
        tasks: List[Dict[str, Any]]
    ) -> List[SynthesisResult]:
        """
        批量合成语音
        
        并行处理多个合成任务
        
        Args:
            tasks: 任务列表
        
        Returns:
            List[SynthesisResult]: 结果列表
        """
        results = []
        
        for task in tasks:
            config = TTSConfig(
                engine=TTSEngineType(task.get("engine", "edge")),
                voice=task.get("voice", settings.TTS_DEFAULT_VOICE),
                speed=task.get("speed", settings.TTS_DEFAULT_SPEED),
                pitch=task.get("pitch", 0),
                format=AudioFormat(task.get("format", "mp3"))
            )
            
            result = await self.synthesize(
                text=task["text"],
                config=config,
                output_path=task.get("output_path")
            )
            results.append(result)
        
        return results
    
    async def synthesize_stream(
        self,
        text: str,
        config: Optional[TTSConfig] = None
    ) -> AsyncIterator[bytes]:
        """
        流式合成语音
        
        适用于长文本的实时合成
        
        Args:
            text: 待合成的文本
            config: 合成配置
        
        Yields:
            bytes: 音频数据块
        """
        if config is None:
            config = TTSConfig(
                engine=TTSEngineType.EDGE,
                voice=settings.TTS_DEFAULT_VOICE
            )
        
        config.validate()
        engine = self.get_engine(config.engine)
        
        async for chunk in engine.synthesize_stream(text, config):
            yield chunk


# ============================================================
# 全局TTS Service实例
# ============================================================

_tts_service: Optional[TTSService] = None


def get_tts_service() -> TTSService:
    """
    获取TTS Service单例
    
    Returns:
        TTSService: TTS服务实例
    """
    global _tts_service
    
    if _tts_service is None:
        _tts_service = TTSService()
    
    return _tts_service


def initialize_tts_service() -> TTSService:
    """
    初始化TTS服务
    
    用于应用启动时调用
    
    Returns:
        TTSService: 初始化的服务实例
    """
    return get_tts_service()
