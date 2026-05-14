# ============================================================
# 单元测试 - TTS语音合成服务测试
# ============================================================
#
# 测试TTS引擎、配置验证、服务层等
#
# Author: CoolAI Team
# Date: 2026-05-13
# ============================================================

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.tts_service import (
    TTSService, EdgeTTSEngine, TTSConfig, VoiceInfo,
    TTSEngineType, AudioFormat, SynthesisResult,
)


# ============================================================
# TTSConfig 测试
# ============================================================

class TestTTSConfig:
    """TTS配置测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = TTSConfig()
        assert config.engine == TTSEngineType.EDGE
        assert config.voice == "zh-CN-XiaoxiaoNeural"
        assert config.speed == 1.0
        assert config.pitch == 0
        assert config.volume == 100
        assert config.format == AudioFormat.MP3

    def test_custom_config(self):
        """测试自定义配置"""
        config = TTSConfig(
            engine=TTSEngineType.OPENAI,
            voice="alloy",
            speed=1.5,
            pitch=10,
            volume=80,
            format=AudioFormat.WAV,
        )
        assert config.engine == TTSEngineType.OPENAI
        assert config.voice == "alloy"
        assert config.speed == 1.5
        assert config.format == AudioFormat.WAV

    def test_validate_speed_too_low(self):
        """测试语速过低"""
        config = TTSConfig(speed=0.1)
        with pytest.raises(ValueError, match="语速必须在0.5-2.0之间"):
            config.validate()

    def test_validate_speed_too_high(self):
        """测试语速过高"""
        config = TTSConfig(speed=3.0)
        with pytest.raises(ValueError, match="语速必须在0.5-2.0之间"):
            config.validate()

    def test_validate_pitch_out_of_range(self):
        """测试音调超出范围"""
        config = TTSConfig(pitch=100)
        with pytest.raises(ValueError, match="音调必须在-50到50之间"):
            config.validate()

    def test_validate_volume_out_of_range(self):
        """测试音量超出范围"""
        config = TTSConfig(volume=150)
        with pytest.raises(ValueError, match="音量必须在0-100之间"):
            config.validate()

    def test_validate_valid_config(self):
        """测试有效配置不抛异常"""
        config = TTSConfig(speed=1.0, pitch=0, volume=50)
        config.validate()  # 不应抛异常


# ============================================================
# EdgeTTSEngine 测试
# ============================================================

class TestEdgeTTSEngine:
    """Edge-TTS引擎测试"""

    def test_list_voices(self):
        """测试语音列表"""
        engine = EdgeTTSEngine()
        voices = engine.list_voices()
        assert isinstance(voices, list)
        assert len(voices) > 0
        # 检查语音对象结构
        voice = voices[0]
        assert isinstance(voice, VoiceInfo)
        assert voice.voice_id
        assert voice.name

    def test_list_voices_contains_chinese(self):
        """测试语音列表包含中文语音"""
        engine = EdgeTTSEngine()
        voices = engine.list_voices()
        zh_voices = [v for v in voices if v.language == "zh-CN"]
        assert len(zh_voices) > 0


# ============================================================
# TTSService 测试
# ============================================================

class TestTTSService:
    """TTS服务层测试"""

    def test_service_initialization(self):
        """测试服务初始化"""
        service = TTSService()
        assert isinstance(service.engines, dict)
        assert service.default_engine is not None

    def test_register_engine(self):
        """测试注册引擎"""
        service = TTSService()
        engine = EdgeTTSEngine()
        service.register_engine(TTSEngineType.EDGE, engine)
        assert TTSEngineType.EDGE in service.engines

    def test_get_engine_default(self):
        """测试获取默认引擎"""
        service = TTSService()
        engine = service.get_engine()
        assert engine is not None

    def test_get_engine_by_type(self):
        """测试按类型获取引擎"""
        service = TTSService()
        if TTSEngineType.EDGE in service.engines:
            engine = service.get_engine(TTSEngineType.EDGE)
            assert isinstance(engine, EdgeTTSEngine)

    def test_get_nonexistent_engine(self):
        """测试获取不存在的引擎"""
        service = TTSService()
        with pytest.raises(ValueError, match="TTS引擎不存在"):
            service.get_engine(TTSEngineType.COSY_VOICE)

    def test_list_all_voices(self):
        """测试列出所有语音"""
        service = TTSService()
        voices = service.list_all_voices()
        assert isinstance(voices, list)
        # 至少有Edge-TTS的语音
        assert len(voices) > 0


# ============================================================
# 枚举测试
# ============================================================

class TestEnums:
    """枚举类型测试"""

    def test_tts_engine_type(self):
        """测试TTS引擎类型枚举"""
        assert TTSEngineType.EDGE.value == "edge"
        assert TTSEngineType.COSY_VOICE.value == "cosyvoice"
        assert TTSEngineType.OPENAI.value == "openai"
        assert TTSEngineType.VOICE_CLONE.value == "voice_clone"

    def test_audio_format(self):
        """测试音频格式枚举"""
        assert AudioFormat.MP3.value == "mp3"
        assert AudioFormat.WAV.value == "wav"
        assert AudioFormat.OGG.value == "ogg"

    def test_engine_type_from_string(self):
        """测试从字符串创建引擎类型"""
        assert TTSEngineType("edge") == TTSEngineType.EDGE
        assert TTSEngineType("openai") == TTSEngineType.OPENAI


# ============================================================
# SynthesisResult 测试
# ============================================================

class TestSynthesisResult:
    """合成结果测试"""

    def test_success_result(self):
        """测试成功结果"""
        result = SynthesisResult(
            success=True,
            audio_data=b"fake_audio_data",
            size=16,
        )
        assert result.success is True
        assert result.audio_data == b"fake_audio_data"
        assert result.size == 16
        assert result.error is None

    def test_error_result(self):
        """测试错误结果"""
        result = SynthesisResult(
            success=False,
            error="合成失败",
        )
        assert result.success is False
        assert result.error == "合成失败"
        assert result.audio_data is None
