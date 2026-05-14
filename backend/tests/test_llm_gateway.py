# ============================================================
# 单元测试 - LLM Gateway 测试
# ============================================================
#
# 测试LLM网关的模型注册、路由、故障转移等
#
# Author: CoolAI Team
# Date: 2026-05-13
# ============================================================

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.llm_gateway import (
    LLMGateway,
    ModelConfig,
    ModelProvider,
    Message,
    LLMResponse,
)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def gateway():
    """创建一个干净的LLM Gateway实例"""
    return LLMGateway()


@pytest.fixture
def sample_model_config():
    """示例模型配置"""
    return ModelConfig(
        name="test-gpt4",
        display_name="GPT-4 Test",
        provider=ModelProvider.OPENAI,
        model_id="gpt-4",
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        is_default=True,
        supports_function_calling=True,
        supports_streaming=True,
    )


# ============================================================
# Message 数据类测试
# ============================================================

class TestMessage:
    """Message数据类测试"""

    def test_message_creation(self):
        """测试消息创建"""
        msg = Message(role="user", content="你好")
        assert msg.role == "user"
        assert msg.content == "你好"
        assert msg.metadata == {}

    def test_message_to_dict(self):
        """测试消息转字典格式"""
        msg = Message(role="user", content="测试")
        d = msg.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "测试"

    def test_system_message_to_dict(self):
        """测试系统消息转字典"""
        msg = Message(role="system", content="你是一个AI助手")
        d = msg.to_dict()
        assert d["role"] == "system"


# ============================================================
# LLM Gateway 测试
# ============================================================

class TestLLMGateway:
    """LLM网关测试"""

    def test_register_model(self, gateway, sample_model_config):
        """测试模型注册"""
        gateway.register_model(sample_model_config)
        
        # 检查模型已注册
        assert "test-gpt4" in gateway._models
        assert gateway._default_model == "test-gpt4"

    def test_register_multiple_models(self, gateway):
        """测试注册多个模型"""
        config1 = ModelConfig(
            name="model-a",
            display_name="Model A",
            provider=ModelProvider.OPENAI,
            model_id="gpt-4",
            api_key="key-a",
            is_default=True,
        )
        config2 = ModelConfig(
            name="model-b",
            display_name="Model B",
            provider=ModelProvider.ANTHROPIC,
            model_id="claude-3",
            api_key="key-b",
        )
        
        gateway.register_model(config1)
        gateway.register_model(config2)
        
        assert len(gateway._models) == 2
        assert gateway._default_model == "model-a"

    def test_set_default_model(self, gateway):
        """测试设置默认模型"""
        config = ModelConfig(
            name="my-model",
            display_name="My Model",
            provider=ModelProvider.OPENAI,
            model_id="gpt-4",
            api_key="key",
        )
        gateway.register_model(config)
        gateway.set_default("my-model")
        
        assert gateway._default_model == "my-model"

    def test_set_default_nonexistent_model(self, gateway):
        """测试设置不存在的默认模型"""
        with pytest.raises(ValueError, match="模型不存在"):
            gateway.set_default("nonexistent")

    def test_get_model_config(self, gateway, sample_model_config):
        """测试获取模型配置"""
        gateway.register_model(sample_model_config)
        config = gateway.get_model_config("test-gpt4")
        
        assert config.name == "test-gpt4"
        assert config.provider == ModelProvider.OPENAI

    def test_list_models(self, gateway):
        """测试列出模型"""
        for i in range(3):
            config = ModelConfig(
                name=f"model-{i}",
                display_name=f"Model {i}",
                provider=ModelProvider.OPENAI,
                model_id=f"gpt-{i}",
                api_key=f"key-{i}",
            )
            gateway.register_model(config)
        
        models = gateway.list_models()
        assert len(models) == 3

    def test_remove_model(self, gateway, sample_model_config):
        """测试删除模型"""
        gateway.register_model(sample_model_config)
        assert "test-gpt4" in gateway._models
        
        gateway.remove_model("test-gpt4")
        assert "test-gpt4" not in gateway._models

    def test_chat_model_not_found(self, gateway):
        """测试调用不存在的模型"""
        with pytest.raises(ValueError, match="模型不存在"):
            import asyncio
            asyncio.get_event_loop().run_until_complete(
                gateway.chat(
                    messages=[Message(role="user", content="test")],
                    model_name="nonexistent",
                )
            )


# ============================================================
# LLMResponse 测试
# ============================================================

class TestLLMResponse:
    """LLM响应测试"""

    def test_response_creation(self):
        """测试响应创建"""
        response = LLMResponse(
            content="你好，我是AI助手",
            model="gpt-4",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        )
        assert response.content == "你好，我是AI助手"
        assert response.model == "gpt-4"
        assert response.usage["total_tokens"] == 30
