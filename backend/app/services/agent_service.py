# ============================================================
# AI Agent 编排器 - Plan-and-Execute 模式
# ============================================================
#
# 实现"先规划后执行"的Agent模式
# 支持：Plan -> Execute -> Re-plan -> Summarize
# 集成：LLMGateway + MCPRegistry + RAGPipeline
#
# Author: CoolAI Team
# Date: 2026-05-13
# ============================================================

import json
import logging
import time
import uuid
from typing import Optional, List, Dict, Any, AsyncIterator
from dataclasses import dataclass, field
from enum import Enum

from app.services.llm_gateway import Message, get_llm_gateway
from app.services.mcp_service import get_mcp_registry

logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PlanStep:
    """计划步骤"""
    step_id: str
    description: str
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    depends_on: List[str] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class ExecutionPlan:
    """执行计划"""
    plan_id: str
    goal: str
    steps: List[PlanStep] = field(default_factory=list)
    status: AgentStatus = AgentStatus.PLANNING
    
    def get_pending_steps(self) -> List[PlanStep]:
        """获取可执行步骤（依赖已完成）"""
        completed_ids = {s.step_id for s in self.steps if s.status == StepStatus.COMPLETED}
        return [
            s for s in self.steps
            if s.status == StepStatus.PENDING
            and all(d in completed_ids for d in s.depends_on)
        ]


@dataclass
class AgentResponse:
    """Agent响应"""
    conversation_id: str
    content: str
    plan: Optional[ExecutionPlan] = None
    steps_result: List[Dict[str, Any]] = field(default_factory=list)
    total_tokens: int = 0
    total_time: float = 0.0
    model: str = ""


class PlanExecuteAgent:
    """
    Plan-and-Execute Agent
    
    工作流程：
    1. Plan: LLM分析问题，制定执行计划
    2. Execute: 逐步执行计划，调用工具
    3. Re-plan: 根据结果动态调整
    4. Summarize: 汇总结果生成最终回答
    """
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        max_iterations: int = 10,
        use_knowledge: bool = True,
        use_tools: bool = True,
    ):
        self.model_name = model_name
        self.max_iterations = max_iterations
        self.use_knowledge = use_knowledge
        self.use_tools = use_tools
    
    def _get_tools_description(self) -> str:
        """获取工具描述"""
        try:
            registry = get_mcp_registry()
            tools = registry.get_all_tools()
            if not tools:
                return "（暂无可用工具）"
            descs = []
            for t in tools:
                params = ", ".join(f"{p.name}: {p.description}" for p in t.parameters)
                descs.append(f"- **{t.name}**: {t.description} (参数: {params})")
            return "\n".join(descs)
        except:
            return "（工具服务暂未初始化）"
    
    async def run(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        context_messages: Optional[List[Message]] = None,
    ) -> AgentResponse:
        """
        运行Agent - 完整的Plan-Execute流程
        """
        start_time = time.time()
        conversation_id = conversation_id or str(uuid.uuid4())
        
        llm = get_llm_gateway()
        mcp = get_mcp_registry()
        
        # 构建消息
        system_prompt = f"""你是一个智能AI助手，采用Plan-and-Execute模式工作。

你的工作方式：
1. 分析问题，制定执行计划
2. 按计划逐步执行，可使用工具获取信息
3. 汇总结果生成回答

可用工具：
{self._get_tools_description()}

当你需要制定计划时，使用以下JSON格式：
```json
{{
    "thinking": "思考过程",
    "plan": [
        {{
            "step_id": "1",
            "description": "步骤描述",
            "tool": "工具名称",
            "tool_args": {{"参数名": "参数值"}},
            "depends_on": []
        }}
    ]
}}
```
直接回答时正常回复即可。"""
        
        messages = [Message(role="system", content=system_prompt)]
        
        if context_messages:
            messages.extend(context_messages)
        
        # 知识库检索
        if self.use_knowledge:
            try:
                from app.services.rag_service_impl import get_rag_pipeline
                rag = get_rag_pipeline()
                results = await rag.retrieve(query, top_k=5)
                if results:
                    context = "\n".join(f"[参考{i+1}] {r.chunk.content}" for i, r in enumerate(results))
                    messages.append(Message(role="system", content=f"知识库检索结果：\n{context}"))
            except Exception as e:
                logger.warning(f"知识库检索失败: {e}")
        
        messages.append(Message(role="user", content=query))
        
        total_tokens = 0
        plan = None
        steps_result = []
        
        # 阶段1：规划
        logger.info(f"[Agent] 开始规划: {query[:50]}...")
        plan_response = await llm.chat(messages=messages, model_name=self.model_name, temperature=0.3)
        total_tokens += plan_response.usage.get("total_tokens", 0)
        
        plan = self._parse_plan(plan_response.content or "", query)
        
        # 阶段2：执行
        if plan and plan.steps:
            logger.info(f"[Agent] 执行计划，共{len(plan.steps)}个步骤")
            
            for _ in range(self.max_iterations):
                pending = plan.get_pending_steps()
                if not pending:
                    break
                
                for step in pending:
                    logger.info(f"[Agent] 执行步骤 {step.step_id}: {step.description}")
                    step.status = StepStatus.RUNNING
                    
                    result = await self._execute_step(step, llm, mcp, messages)
                    
                    if result.get("success"):
                        step.status = StepStatus.COMPLETED
                        step.result = result.get("result")
                    else:
                        step.status = StepStatus.FAILED
                        step.error = result.get("error", "执行失败")
                    
                    steps_result.append({
                        "step_id": step.step_id,
                        "description": step.description,
                        "status": step.status.value,
                        "result": step.result,
                        "error": step.error,
                    })
            
            plan.status = AgentStatus.COMPLETED
        
        # 阶段3：总结
        logger.info("[Agent] 生成最终回答")
        summary_prompt = self._build_summary_prompt(query, plan, steps_result)
        messages.append(Message(role="user", content=summary_prompt))
        
        final_response = await llm.chat(messages=messages, model_name=self.model_name, temperature=0.7)
        total_tokens += final_response.usage.get("total_tokens", 0)
        
        return AgentResponse(
            conversation_id=conversation_id,
            content=final_response.content or "",
            plan=plan,
            steps_result=steps_result,
            total_tokens=total_tokens,
            total_time=time.time() - start_time,
            model=final_response.model,
        )
    
    async def run_stream(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        context_messages: Optional[List[Message]] = None,
    ) -> AsyncIterator[str]:
        """流式运行Agent"""
        # 先执行完整流程
        response = await self.run(query, conversation_id, context_messages)
        
        # 流式输出最终回答
        llm = get_llm_gateway()
        messages = [
            Message(role="system", content="你是一个AI助手。"),
            Message(role="user", content=query),
            Message(role="assistant", content=response.content),
            Message(role="user", content="请用更详细流畅的方式重新组织回答："),
        ]
        
        async for chunk in llm.chat_stream(messages=messages, model_name=self.model_name):
            yield chunk
    
    def _parse_plan(self, response: str, goal: str) -> Optional[ExecutionPlan]:
        """解析LLM响应中的执行计划"""
        plan = ExecutionPlan(plan_id=str(uuid.uuid4()), goal=goal)
        
        try:
            json_text = None
            if "```json" in response:
                start = response.index("```json") + 7
                end = response.index("```", start)
                json_text = response[start:end].strip()
            elif "{" in response and "plan" in response:
                start = response.index("{")
                end = response.rindex("}") + 1
                json_text = response[start:end]
            
            if json_text:
                data = json.loads(json_text)
                for sd in data.get("plan", []):
                    plan.steps.append(PlanStep(
                        step_id=str(sd.get("step_id", len(plan.steps) + 1)),
                        description=sd.get("description", ""),
                        tool_name=sd.get("tool"),
                        tool_args=sd.get("tool_args", {}),
                        depends_on=sd.get("depends_on", []),
                    ))
                if plan.steps:
                    return plan
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"计划解析失败: {e}")
        
        # 无法解析时创建单步计划
        plan.steps.append(PlanStep(step_id="1", description="直接回答用户问题"))
        return plan
    
    async def _execute_step(
        self,
        step: PlanStep,
        llm,
        mcp,
        messages: List[Message],
    ) -> Dict[str, Any]:
        """执行单个步骤"""
        if step.tool_name:
            try:
                tool = mcp.get_tool(step.tool_name)
                if tool:
                    result = await mcp.call_tool(step.tool_name, step.tool_args or {})
                    return {"success": True, "result": result}
                return {"success": False, "error": f"工具不存在: {step.tool_name}"}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        # 无工具，LLM直接处理
        try:
            step_msgs = messages + [Message(role="user", content=f"请执行：{step.description}")]
            response = await llm.chat(messages=step_msgs, model_name=self.model_name, temperature=0.5)
            return {"success": True, "result": response.content}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _build_summary_prompt(
        self,
        query: str,
        plan: Optional[ExecutionPlan],
        steps_result: List[Dict[str, Any]],
    ) -> str:
        """构建总结提示词"""
        result_text = ""
        for sr in steps_result:
            result_text += f"\n步骤{sr['step_id']}: {sr['description']}\n状态: {sr['status']}\n"
            if sr.get('result'):
                result_text += f"结果: {json.dumps(sr['result'], ensure_ascii=False, default=str)[:500]}\n"
            if sr.get('error'):
                result_text += f"错误: {sr['error']}\n"
        
        return f"""原始问题：{query}

执行结果：
{result_text or '（无执行步骤）'}

请根据以上信息，用清晰完整的语言回答原始问题。"""


# ============================================================
# Agent服务层
# ============================================================

class AgentService:
    """Agent业务服务层"""
    
    def __init__(self):
        self.default_model = None
    
    async def chat(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        model_name: Optional[str] = None,
        use_knowledge: bool = False,
        use_tools: bool = True,
        context_messages: Optional[List[Message]] = None,
    ) -> AgentResponse:
        agent = PlanExecuteAgent(
            model_name=model_name or self.default_model,
            use_knowledge=use_knowledge,
            use_tools=use_tools,
        )
        return await agent.run(query, conversation_id, context_messages)
    
    async def chat_stream(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        model_name: Optional[str] = None,
        use_knowledge: bool = False,
        use_tools: bool = True,
        context_messages: Optional[List[Message]] = None,
    ) -> AsyncIterator[str]:
        agent = PlanExecuteAgent(
            model_name=model_name or self.default_model,
            use_knowledge=use_knowledge,
            use_tools=use_tools,
        )
        async for chunk in agent.run_stream(query, conversation_id, context_messages):
            yield chunk


# 全局实例
_agent_service: Optional[AgentService] = None

def get_agent_service() -> AgentService:
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service

def initialize_agent_service() -> AgentService:
    return get_agent_service()
