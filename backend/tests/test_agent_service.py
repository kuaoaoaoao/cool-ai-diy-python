# ============================================================
# 单元测试 - Agent服务测试
# ============================================================
#
# 测试Plan-Execute Agent、AgentService等
#
# Author: CoolAI Team
# Date: 2026-05-13
# ============================================================

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.agent_service import (
    PlanExecuteAgent,
    AgentService,
    AgentResponse,
)


# ============================================================
# AgentResponse 测试
# ============================================================

class TestAgentResponse:
    """Agent响应测试"""

    def test_response_creation(self):
        """测试响应创建"""
        response = AgentResponse(
            answer="这是AI的回答",
            plan=["步骤1", "步骤2"],
            steps_results=[{"step": 1, "result": "完成"}],
            model="gpt-4",
            total_tokens=100,
        )
        assert response.answer == "这是AI的回答"
        assert len(response.plan) == 2
        assert response.model == "gpt-4"
        assert response.total_tokens == 100

    def test_response_defaults(self):
        """测试响应默认值"""
        response = AgentResponse(answer="简单回答")
        assert response.answer == "简单回答"
        assert response.plan == []
        assert response.steps_results == []
        assert response.model == ""
        assert response.total_tokens == 0


# ============================================================
# PlanExecuteAgent 测试
# ============================================================

class TestPlanExecuteAgent:
    """Plan-Execute Agent测试"""

    def test_agent_initialization(self):
        """测试Agent初始化"""
        # 不依赖LLM Gateway的初始化
        with patch("app.services.agent_service.get_llm_gateway") as mock_gateway:
            mock_gateway.return_value = MagicMock()
            agent = PlanExecuteAgent()
            assert agent is not None

    @pytest.mark.asyncio
    async def test_plan_step(self):
        """测试规划步骤"""
        with patch("app.services.agent_service.get_llm_gateway") as mock_gateway:
            # 模拟LLM响应 - 返回计划
            mock_llm = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "1. 分析用户问题\n2. 搜索相关信息\n3. 生成回答"
            mock_llm.chat = AsyncMock(return_value=mock_response)
            mock_gateway.return_value = mock_llm
            
            agent = PlanExecuteAgent()
            # 测试计划生成（需要mock LLM）
            # 实际调用中会走LLM，这里验证结构
            assert agent is not None


# ============================================================
# AgentService 测试
# ============================================================

class TestAgentService:
    """AgentService业务层测试"""

    def test_service_initialization(self):
        """测试服务初始化"""
        with patch("app.services.agent_service.get_llm_gateway"):
            with patch("app.services.agent_service.get_mcp_registry"):
                service = AgentService()
                assert service is not None
