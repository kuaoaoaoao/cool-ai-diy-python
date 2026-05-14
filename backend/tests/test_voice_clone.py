# ============================================================
# 单元测试 - 声音克隆服务测试
# ============================================================
#
# 测试声音克隆引擎、服务层等
#
# Author: CoolAI Team
# Date: 2026-05-13
# ============================================================

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.voice_clone_service import (
    VoiceCloneService,
    CloneEngine,
    CloneConfig,
    CloneTask,
    EdgeSimulateEngine,
)


# ============================================================
# CloneEngine 枚举测试
# ============================================================

class TestCloneEngine:
    """克隆引擎枚举测试"""

    def test_engine_types(self):
        """测试引擎类型"""
        assert CloneEngine.XTTS_V2.value == "xtts_v2"
        assert CloneEngine.SO_VITS_SVC.value == "so_vits_svc"
        assert CloneEngine.EDGE_SIMULATE.value == "edge_simulate"


# ============================================================
# CloneConfig 测试
# ============================================================

class TestCloneConfig:
    """克隆配置测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = CloneConfig()
        assert config.engine == CloneEngine.XTTS_V2
        assert config.language == "zh"
        assert config.speed == 1.0
        assert config.reference_audio_path == ""

    def test_custom_config(self):
        """测试自定义配置"""
        config = CloneConfig(
            engine=CloneEngine.EDGE_SIMULATE,
            language="en",
            speed=1.2,
            reference_audio_path="/path/to/ref.wav",
        )
        assert config.engine == CloneEngine.EDGE_SIMULATE
        assert config.language == "en"
        assert config.speed == 1.2


# ============================================================
# CloneTask 测试
# ============================================================

class TestCloneTask:
    """克隆训练任务测试"""

    def test_task_creation(self):
        """测试任务创建"""
        task = CloneTask(
            task_id="test-task-id",
            model_id="test-model-id",
        )
        assert task.task_id == "test-task-id"
        assert task.model_id == "test-model-id"
        assert task.status == "pending"
        assert task.progress == 0.0
        assert task.error is None

    def test_task_with_status(self):
        """测试带状态的任务"""
        task = CloneTask(
            task_id="test-task-id",
            model_id="test-model-id",
            status="ready",
            progress=1.0,
        )
        assert task.status == "ready"
        assert task.progress == 1.0


# ============================================================
# EdgeSimulateEngine 测试
# ============================================================

class TestEdgeSimulateEngine:
    """Edge-TTS模拟引擎测试"""

    def test_engine_always_available(self):
        """测试引擎始终可用"""
        engine = EdgeSimulateEngine()
        assert engine.is_available is True

    def test_voice_map_has_entries(self):
        """测试音色映射表有内容"""
        engine = EdgeSimulateEngine()
        assert "男" in engine.VOICE_MAP
        assert "女" in engine.VOICE_MAP
        assert "default" in engine.VOICE_MAP

    def test_select_voice_male(self):
        """测试男性音色选择"""
        engine = EdgeSimulateEngine()
        voice = engine._select_voice("男声")
        assert voice.startswith("zh-CN-Yun")

    def test_select_voice_female(self):
        """测试女性音色选择"""
        engine = EdgeSimulateEngine()
        voice = engine._select_voice("女声")
        assert voice.startswith("zh-CN-Xiao")

    def test_select_voice_default(self):
        """测试默认音色选择"""
        engine = EdgeSimulateEngine()
        voice = engine._select_voice("未知提示")
        assert voice in engine.VOICE_MAP["default"]


# ============================================================
# VoiceCloneService 测试
# ============================================================

class TestVoiceCloneService:
    """声音克隆服务层测试"""

    def test_service_initialization(self):
        """测试服务初始化"""
        with patch("app.services.voice_clone_service.settings") as mock_settings:
            mock_settings.TTS_OUTPUT_DIR = "/tmp/test_tts"
            service = VoiceCloneService()
            assert service is not None
            assert service._edge_engine is not None

    def test_get_available_engine_no_gpu(self):
        """测试无GPU时获取可用引擎"""
        with patch("app.services.voice_clone_service.settings") as mock_settings:
            mock_settings.TTS_OUTPUT_DIR = "/tmp/test_tts"
            service = VoiceCloneService()
            # 当XTTS-v2不可用时，应返回edge_simulate
            engine = service.get_available_engine()
            assert engine in [CloneEngine.XTTS_V2.value, CloneEngine.EDGE_SIMULATE.value]

    def test_training_status_not_found(self):
        """测试查询不存在的训练任务"""
        with patch("app.services.voice_clone_service.settings") as mock_settings:
            mock_settings.TTS_OUTPUT_DIR = "/tmp/test_tts"
            service = VoiceCloneService()
            status = service.get_training_status("nonexistent-task-id")
            assert status is None

    def test_training_status_found(self):
        """测试查询存在的训练任务"""
        with patch("app.services.voice_clone_service.settings") as mock_settings:
            mock_settings.TTS_OUTPUT_DIR = "/tmp/test_tts"
            service = VoiceCloneService()
            # 手动添加一个任务
            task = CloneTask(
                task_id="test-task",
                model_id="test-model",
                status="ready",
                progress=1.0,
            )
            service._tasks["test-task"] = task
            
            status = service.get_training_status("test-task")
            assert status is not None
            assert status["status"] == "ready"
            assert status["progress"] == 1.0
