# ============================================================
# LLM Gateway - 大模型统一网关
# ============================================================
#
# 本模块实现大语言模型的统一调度网关
# 同时支持：
# 1. OpenAI API（GPT-4、GPT-3.5等）
# 2. 本地部署的开源模型（ChatGLM、Qwen等）
#   - 通过OpenAI兼容API接口访问
#   - 本地模型通常部署为vLLM/Ollama等推理服务
#
# 设计思路：
# - 统一接口：无论底层模型是什么，上层代码使用同一套API
# - 动态路由：根据配置自动选择模型
# - 故障转移：主模型不可用时自动切换备用模型
# - 流式输出：所有模型统一支持SSE流式响应
#
# Author: CoolAI Team
# Date: 2026-05-13
# ============================================================

import json
import logging
import time
from typing import (
    Optional, List, Dict, Any, AsyncIterator, Callable
)
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


# ============================================================
# 数据类定义
# ============================================================

class ModelProvider(str, Enum):
    """模型提供商标识"""
    OPENAI = "openai"             # OpenAI官方API
    ANTHROPIC = "anthropic"       # Anthropic Claude
    LOCAL = "local"               # 本地部署模型
    CUSTOM = "custom"             # 自定义API


@dataclass
class ModelConfig:
    """
    模型配置数据类
    
    定义一个可用的LLM模型
    
    Attributes:
        name: 模型标识名称（唯一）
        display_name: 显示名称
        provider: 提供商标识
        model_id: 模型ID（发送给API的）
        api_key: API密钥
        base_url: API基础URL
        max_tokens: 最大输出token数
        temperature: 默认温度参数
        supports_streaming: 是否支持流式输出
        supports_function_calling: 是否支持函数调用
        cost_per_1k_tokens: 每1K token成本（美元，用于计费）
    """
    name: str
    display_name: str
    provider: ModelProvider
    model_id: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.7
    supports_streaming: bool = True
    supports_function_calling: bool = False
    cost_per_1k_tokens: float = 0.0
    # 额外配置
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Message:
    """
    对话消息数据类
    
    兼容OpenAI消息格式
    
    Attributes:
        role: 消息角色
        content: 消息内容
        name: 发送者名称（可选）
        function_call: 函数调用信息（可选）
        tool_calls: 工具调用列表（可选）
    """
    role: str  # system / user / assistant / function / tool
    content: Optional[str] = None
    name: Optional[str] = None
    function_call: Optional[Dict[str, Any]] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为OpenAI兼容的字典格式"""
        d: Dict[str, Any] = {"role": self.role}
        
        if self.content is not None:
            d["content"] = self.content
        if self.name is not None:
            d["name"] = self.name
        if self.function_call is not None:
            d["function_call"] = self.function_call
        if self.tool_calls is not None:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id is not None:
            d["tool_call_id"] = self.tool_call_id
            
        return d
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """从字典创建Message"""
        return cls(
            role=data.get("role", "user"),
            content=data.get("content"),
            name=data.get("name"),
            function_call=data.get("function_call"),
            tool_calls=data.get("tool_calls"),
            tool_call_id=data.get("tool_call_id"),
        )


@dataclass
class LLMResponse:
    """
    LLM响应数据类
    
    Attributes:
        content: 文本内容
        model: 使用的模型
        usage: Token使用统计
        tool_calls: 工具调用列表
        finish_reason: 结束原因
        latency: 响应延迟（秒）
    """
    content: Optional[str] = None
    model: str = ""
    usage: Dict[str, int] = field(default_factory=dict)
    tool_calls: Optional[List[Dict[str, Any]]] = None
    finish_reason: Optional[str] = None
    latency: float = 0.0


# ============================================================
# LLM Provider 抽象基类
# ============================================================

class LLMProviderBase(ABC):
    """
    LLM提供者抽象基类
    
    定义统一的LLM调用接口
    不同提供商实现此接口
    """
    
    @abstractmethod
    async def chat(
        self,
        messages: List[Message],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """
        同步对话
        
        Args:
            messages: 消息列表
            model: 模型ID
            temperature: 温度参数
            max_tokens: 最大输出token
            tools: 工具定义列表
            **kwargs: 其他参数
        
        Returns:
            LLMResponse: 模型响应
        """
        pass
    
    @abstractmethod
    async def chat_stream(
        self,
        messages: List[Message],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        流式对话
        
        Args:
            messages: 消息列表
            model: 模型ID
            temperature: 温度参数
            max_tokens: 最大输出token
            **kwargs: 其他参数
        
        Yields:
            str: 文本片段
        """
        pass
    
    @abstractmethod
    async def embed(self, texts: List[str], model: str = "") -> List[List[float]]:
        """
        文本嵌入
        
        Args:
            texts: 文本列表
            model: 嵌入模型ID
        
        Returns:
            List[List[float]]: 向量列表
        """
        pass


# ============================================================
# OpenAI 兼容提供者
# ============================================================

class OpenAICompatibleProvider(LLMProviderBase):
    """
    OpenAI兼容API提供者
    
    同时支持：
    1. OpenAI官方API
    2. 本地部署的OpenAI兼容API（如vLLM、Ollama、LocalAI等）
    3. 其他兼容OpenAI API格式的服务
    
    本地模型部署方式：
    - vLLM: python -m vllm.entrypoints.openai.api_server --model chatglm3-6b
    - Ollama: ollama serve
    - LocalAI: local-ai --models-path /models
    
    这些服务都提供OpenAI兼容的API接口
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.openai.com/v1",
        timeout: int = 120
    ):
        """
        初始化OpenAI兼容提供者
        
        Args:
            api_key: API密钥
            base_url: API基础URL
            timeout: 请求超时时间
        """
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            timeout=httpx.Timeout(timeout)
        )
    
    async def chat(
        self,
        messages: List[Message],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """
        同步对话
        
        Args:
            messages: 消息列表
            model: 模型ID
            temperature: 温度参数
            max_tokens: 最大输出token
            tools: 工具定义列表
            **kwargs: 其他参数
        
        Returns:
            LLMResponse: 模型响应
        """
        start_time = time.time()
        
        # 构建请求体
        request_body: Dict[str, Any] = {
            "model": model,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        
        # 添加工具定义（如果模型支持）
        if tools:
            request_body["tools"] = tools
            request_body["tool_choice"] = "auto"
        
        # 合并额外参数
        request_body.update(kwargs)
        
        try:
            response = await self._client.post(
                "/chat/completions",
                json=request_body
            )
            response.raise_for_status()
            
            result = response.json()
            latency = time.time() - start_time
            
            # 解析响应
            choice = result["choices"][0]
            
            # 提取内容
            content = choice["message"].get("content")
            tool_calls = choice["message"].get("tool_calls")
            
            # 解析工具调用
            parsed_tool_calls = None
            if tool_calls:
                parsed_tool_calls = []
                for tc in tool_calls:
                    parsed_tool_calls.append({
                        "id": tc.get("id"),
                        "type": tc.get("type", "function"),
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": tc["function"]["arguments"]
                        }
                    })
            
            return LLMResponse(
                content=content,
                model=result.get("model", model),
                usage=result.get("usage", {}),
                tool_calls=parsed_tool_calls,
                finish_reason=choice.get("finish_reason"),
                latency=latency
            )
        
        except httpx.HTTPStatusError as e:
            logger.error(f"LLM API错误: {e.response.status_code} - {e.response.text}")
            raise Exception(f"LLM API错误: {e.response.status_code}")
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            raise
    
    async def chat_stream(
        self,
        messages: List[Message],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        流式对话
        
        使用SSE（Server-Sent Events）接收流式响应
        
        Args:
            messages: 消息列表
            model: 模型ID
            temperature: 温度参数
            max_tokens: 最大输出token
            **kwargs: 其他参数
        
        Yields:
            str: 文本片段
        """
        request_body: Dict[str, Any] = {
            "model": model,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        request_body.update(kwargs)
        
        async with self._client.stream(
            "POST",
            "/chat/completions",
            json=request_body
        ) as response:
            response.raise_for_status()
            
            async for line in response.aiter_lines():
                # SSE格式: "data: {...}"
                if not line.startswith("data: "):
                    continue
                
                data = line[6:]  # 去掉 "data: " 前缀
                
                if data == "[DONE]":
                    break
                
                try:
                    chunk = json.loads(data)
                    delta = chunk["choices"][0].get("delta", {})
                    
                    content = delta.get("content")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue
    
    async def embed(
        self,
        texts: List[str],
        model: str = "text-embedding-ada-002"
    ) -> List[List[float]]:
        """
        文本嵌入
        
        Args:
            texts: 文本列表
            model: 嵌入模型ID
        
        Returns:
            List[List[float]]: 向量列表
        """
        request_body = {
            "model": model,
            "input": texts
        }
        
        try:
            response = await self._client.post(
                "/embeddings",
                json=request_body
            )
            response.raise_for_status()
            
            result = response.json()
            return [item["embedding"] for item in result["data"]]
        
        except Exception as e:
            logger.error(f"嵌入调用失败: {e}")
            raise
    
    async def close(self):
        """关闭客户端连接"""
        await self._client.aclose()


# ============================================================
# Anthropic Claude 提供者
# ============================================================

class AnthropicProvider(LLMProviderBase):
    """
    Anthropic Claude 提供者
    
    支持Claude系列模型
    使用Anthropic API格式
    
    注意：API密钥需要后期替换为真实值
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.anthropic.com",
        timeout: int = 120
    ):
        """
        初始化Anthropic提供者
        
        Args:
            api_key: Anthropic API密钥
            base_url: API基础URL
            timeout: 请求超时
        """
        # 后期替换：使用真实的API Key
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=f"{self.base_url}/v1",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            },
            timeout=httpx.Timeout(timeout)
        )
    
    async def chat(
        self,
        messages: List[Message],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Claude对话
        
        注意：Claude的消息格式与OpenAI略有不同
        system消息需要单独传递
        """
        start_time = time.time()
        
        # 分离system消息
        system_content = None
        chat_messages = []
        
        for msg in messages:
            if msg.role == "system":
                system_content = msg.content
            else:
                chat_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
        
        request_body: Dict[str, Any] = {
            "model": model,
            "messages": chat_messages,
            "max_tokens": max_tokens,
        }
        
        if system_content:
            request_body["system"] = system_content
        
        if tools:
            request_body["tools"] = self._convert_tools(tools)
        
        try:
            response = await self._client.post(
                "/messages",
                json=request_body
            )
            response.raise_for_status()
            
            result = response.json()
            latency = time.time() - start_time
            
            # 解析Claude响应
            content = ""
            tool_calls = None
            
            for block in result.get("content", []):
                if block["type"] == "text":
                    content += block["text"]
                elif block["type"] == "tool_use":
                    if tool_calls is None:
                        tool_calls = []
                    tool_calls.append({
                        "id": block["id"],
                        "type": "function",
                        "function": {
                            "name": block["name"],
                            "arguments": json.dumps(block["input"])
                        }
                    })
            
            return LLMResponse(
                content=content or None,
                model=result.get("model", model),
                usage={
                    "prompt_tokens": result.get("usage", {}).get("input_tokens", 0),
                    "completion_tokens": result.get("usage", {}).get("output_tokens", 0),
                },
                tool_calls=tool_calls,
                finish_reason=result.get("stop_reason"),
                latency=latency
            )
        
        except Exception as e:
            logger.error(f"Claude调用失败: {e}")
            raise
    
    async def chat_stream(
        self,
        messages: List[Message],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AsyncIterator[str]:
        """Claude流式对话"""
        system_content = None
        chat_messages = []
        
        for msg in messages:
            if msg.role == "system":
                system_content = msg.content
            else:
                chat_messages.append({"role": msg.role, "content": msg.content})
        
        request_body: Dict[str, Any] = {
            "model": model,
            "messages": chat_messages,
            "max_tokens": max_tokens,
            "stream": True,
        }
        
        if system_content:
            request_body["system"] = system_content
        
        async with self._client.stream(
            "POST",
            "/messages",
            json=request_body
        ) as response:
            response.raise_for_status()
            
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    try:
                        event = json.loads(data)
                        if event.get("type") == "content_block_delta":
                            delta = event.get("delta", {})
                            if delta.get("type") == "text_delta":
                                yield delta.get("text", "")
                    except json.JSONDecodeError:
                        continue
    
    async def embed(
        self,
        texts: List[str],
        model: str = ""
    ) -> List[List[float]]:
        """Claude暂不支持嵌入，返回空"""
        raise NotImplementedError("Claude暂不支持嵌入API")
    
    def _convert_tools(self, openai_tools: List[Dict]) -> List[Dict]:
        """将OpenAI格式工具转换为Claude格式"""
        claude_tools = []
        for tool in openai_tools:
            if tool.get("type") == "function":
                func = tool["function"]
                claude_tools.append({
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {})
                })
        return claude_tools
    
    async def close(self):
        """关闭客户端"""
        await self._client.aclose()


# ============================================================
# LLM Gateway 网关
# ============================================================

class LLMGateway:
    """
    LLM网关
    
    统一管理和调度多个大语言模型
    支持：
    1. 多提供商管理（OpenAI、Claude、本地模型）
    2. 动态模型路由
    3. 故障转移
    4. 负载均衡
    5. 用量统计
    
    使用方法：
    gateway = LLMGateway()
    gateway.register_model(ModelConfig(...))
    
    response = await gateway.chat(
        messages=[Message(role="user", content="你好")],
        model_name="gpt-4"
    )
    """
    
    def __init__(self):
        """初始化LLM网关"""
        # 已注册的模型
        self._models: Dict[str, ModelConfig] = {}
        
        # 已创建的提供者实例
        self._providers: Dict[str, LLMProviderBase] = {}
        
        # 默认模型
        self._default_model: Optional[str] = None
        
        # 用量统计
        self._usage_stats: Dict[str, Dict[str, int]] = {}
        
        # 注册默认模型
        self._register_default_models()
    
    def _register_default_models(self):
        """
        注册默认可用的模型
        
        从配置文件读取模型信息
        """
        # ============================================================
        # OpenAI 模型
        # ============================================================
        if settings.OPENAI_API_KEY:
            self.register_model(ModelConfig(
                name="gpt-4-turbo",
                display_name="GPT-4 Turbo",
                provider=ModelProvider.OPENAI,
                model_id="gpt-4-turbo-preview",
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
                max_tokens=128000,
                supports_streaming=True,
                supports_function_calling=True,
                cost_per_1k_tokens=0.01
            ))
            
            self.register_model(ModelConfig(
                name="gpt-3.5-turbo",
                display_name="GPT-3.5 Turbo",
                provider=ModelProvider.OPENAI,
                model_id="gpt-3.5-turbo",
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
                max_tokens=16384,
                supports_streaming=True,
                supports_function_calling=True,
                cost_per_1k_tokens=0.002
            ))
        
        # ============================================================
        # Anthropic Claude 模型
        # ============================================================
        if settings.ANTHROPIC_API_KEY:
            self.register_model(ModelConfig(
                name="claude-3-opus",
                display_name="Claude 3 Opus",
                provider=ModelProvider.ANTHROPIC,
                model_id="claude-3-opus-20240229",
                api_key=settings.ANTHROPIC_API_KEY,
                base_url=settings.ANTHROPIC_BASE_URL,
                max_tokens=200000,
                supports_streaming=True,
                supports_function_calling=True,
                cost_per_1k_tokens=0.015
            ))
        
        # ============================================================
        # 本地部署模型
        # ============================================================
        # 后期替换：修改LOCAL_LLM_BASE_URL为实际的本地模型服务地址
        # 本地模型通常通过vLLM/Ollama部署，提供OpenAI兼容API
        self.register_model(ModelConfig(
            name="chatglm3-6b",
            display_name="ChatGLM3-6B（本地）",
            provider=ModelProvider.LOCAL,
            model_id=settings.LOCAL_LLM_MODEL,
            api_key=settings.LOCAL_LLM_API_KEY,
            base_url=settings.LOCAL_LLM_BASE_URL,
            max_tokens=8192,
            supports_streaming=True,
            supports_function_calling=False,  # 部分本地模型不支持
            cost_per_1k_tokens=0.0  # 本地模型免费
        ))
        
        # 设置默认模型
        if settings.OPENAI_API_KEY:
            self._default_model = "gpt-4-turbo"
        else:
            self._default_model = "chatglm3-6b"
    
    def register_model(self, config: ModelConfig):
        """
        注册一个新模型
        
        Args:
            config: 模型配置
        """
        self._models[config.name] = config
        
        # 初始化用量统计
        if config.name not in self._usage_stats:
            self._usage_stats[config.name] = {
                "total_requests": 0,
                "total_tokens": 0,
                "total_errors": 0,
            }
    
    def get_provider(self, model_name: str) -> LLMProviderBase:
        """
        获取模型对应的提供者
        
        Args:
            model_name: 模型名称
        
        Returns:
            LLMProviderBase: 提供者实例
        """
        config = self._models.get(model_name)
        if not config:
            raise ValueError(f"模型不存在: {model_name}")
        
        # 检查是否已创建提供者实例
        provider_key = f"{config.provider.value}_{config.base_url}"
        
        if provider_key not in self._providers:
            # 创建新的提供者实例
            if config.provider in (ModelProvider.OPENAI, ModelProvider.LOCAL, ModelProvider.CUSTOM):
                self._providers[provider_key] = OpenAICompatibleProvider(
                    api_key=config.api_key,
                    base_url=config.base_url
                )
            elif config.provider == ModelProvider.ANTHROPIC:
                self._providers[provider_key] = AnthropicProvider(
                    api_key=config.api_key,
                    base_url=config.base_url
                )
        
        return self._providers[provider_key]
    
    async def chat(
        self,
        messages: List[Message],
        model_name: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """
        统一对话接口
        
        Args:
            messages: 消息列表
            model_name: 模型名称（None则使用默认）
            temperature: 温度参数
            max_tokens: 最大输出token
            tools: 工具定义
            **kwargs: 其他参数
        
        Returns:
            LLMResponse: 模型响应
        """
        model_name = model_name or self._default_model
        config = self._models.get(model_name)
        
        if not config:
            raise ValueError(f"模型不存在: {model_name}")
        
        # 获取提供者
        provider = self.get_provider(model_name)
        
        # 如果模型不支持函数调用，移除tools
        if tools and not config.supports_function_calling:
            logger.warning(f"模型 {model_name} 不支持函数调用，已移除tools参数")
            tools = None
        
        try:
            response = await provider.chat(
                messages=messages,
                model=config.model_id,
                temperature=temperature,
                max_tokens=max_tokens or config.max_tokens,
                tools=tools,
                **kwargs
            )
            
            # 更新统计
            self._update_usage(model_name, response.usage)
            
            return response
        
        except Exception as e:
            # 更新错误统计
            self._usage_stats[model_name]["total_errors"] += 1
            
            # 尝试故障转移
            fallback_model = self._get_fallback_model(model_name)
            if fallback_model:
                logger.warning(f"模型 {model_name} 调用失败，尝试故障转移到 {fallback_model}")
                return await self.chat(
                    messages=messages,
                    model_name=fallback_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools,
                    **kwargs
                )
            
            raise
    
    async def chat_stream(
        self,
        messages: List[Message],
        model_name: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        流式对话
        
        Args:
            messages: 消息列表
            model_name: 模型名称
            temperature: 温度参数
            max_tokens: 最大输出token
        
        Yields:
            str: 文本片段
        """
        model_name = model_name or self._default_model
        config = self._models.get(model_name)
        
        if not config:
            raise ValueError(f"模型不存在: {model_name}")
        
        provider = self.get_provider(model_name)
        
        async for chunk in provider.chat_stream(
            messages=messages,
            model=config.model_id,
            temperature=temperature,
            max_tokens=max_tokens or config.max_tokens,
            **kwargs
        ):
            yield chunk
    
    def list_models(self) -> List[ModelConfig]:
        """
        列出所有可用模型
        
        Returns:
            List[ModelConfig]: 模型配置列表
        """
        return list(self._models.values())
    
    def get_model_config(self, model_name: str) -> Optional[ModelConfig]:
        """
        获取模型配置
        
        Args:
            model_name: 模型名称
        
        Returns:
            Optional[ModelConfig]: 模型配置
        """
        return self._models.get(model_name)
    
    def _get_fallback_model(self, failed_model: str) -> Optional[str]:
        """
        获取故障转移的备用模型
        
        策略：
        1. 同提供商的更便宜模型
        2. 不同提供商的同类模型
        
        Args:
            failed_model: 失败的模型名称
        
        Returns:
            Optional[str]: 备用模型名称
        """
        config = self._models.get(failed_model)
        if not config:
            return None
        
        # 同提供商的备选
        for name, m in self._models.items():
            if name != failed_model and m.provider == config.provider:
                return name
        
        # 不同提供商的备选
        for name, m in self._models.items():
            if name != failed_model:
                return name
        
        return None
    
    def _update_usage(self, model_name: str, usage: Dict[str, int]):
        """
        更新用量统计
        
        Args:
            model_name: 模型名称
            usage: 使用统计
        """
        if model_name not in self._usage_stats:
            self._usage_stats[model_name] = {
                "total_requests": 0,
                "total_tokens": 0,
                "total_errors": 0,
            }
        
        self._usage_stats[model_name]["total_requests"] += 1
        total_tokens = usage.get("total_tokens", 0)
        if total_tokens == 0:
            total_tokens = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
        self._usage_stats[model_name]["total_tokens"] += total_tokens
    
    def get_usage_stats(self) -> Dict[str, Dict[str, int]]:
        """
        获取用量统计
        
        Returns:
            Dict: 用量统计字典
        """
        return self._usage_stats.copy()
    
    async def close(self):
        """关闭所有提供者连接"""
        for provider in self._providers.values():
            await provider.close()


# ============================================================
# 全局LLM网关实例
# ============================================================

_llm_gateway: Optional[LLMGateway] = None


def get_llm_gateway() -> LLMGateway:
    """
    获取LLM网关单例
    
    Returns:
        LLMGateway: 网关实例
    """
    global _llm_gateway
    if _llm_gateway is None:
        _llm_gateway = LLMGateway()
    return _llm_gateway


def initialize_llm_gateway() -> LLMGateway:
    """
    初始化LLM网关
    
    Returns:
        LLMGateway: 初始化的网关实例
    """
    return get_llm_gateway()
