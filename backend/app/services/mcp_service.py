# ============================================================
# MCP (Model Context Protocol) 服务实现
# ============================================================
#
# 本模块实现MCP协议支持
# MCP是Anthropic提出的模型上下文协议，用于标准化
# AI模型与外部工具/资源的交互方式
#
# 主要功能：
# 1. MCP Server注册与发现
# 2. 工具定义标准化
# 3. 工具调用协议
# 4. 资源访问协议
#
# 协议规范：JSON-RPC 2.0
#
# Author: CoolAI Team
# Date: 2026-05-13
# ============================================================

import json
import logging
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import asyncio

logger = logging.getLogger(__name__)


# ============================================================
# 数据类定义
# ============================================================

class MCPMessageType(str, Enum):
    """MCP消息类型"""
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    ERROR = "error"


@dataclass
class MCPToolParameter:
    """工具参数定义"""
    name: str
    type: str = "string"
    description: str = ""
    required: bool = True
    default: Any = None
    enum: Optional[List[Any]] = None


@dataclass
class MCPTool:
    """MCP工具定义 - 符合MCP协议规范"""
    name: str
    description: str
    parameters: List[MCPToolParameter]
    handler: Optional[Callable] = None
    server_name: Optional[str] = None
    
    def to_openai_function(self) -> Dict[str, Any]:
        """转换为OpenAI Function Calling格式"""
        properties = {}
        required = []
        
        for param in self.parameters:
            prop: Dict[str, Any] = {"type": param.type, "description": param.description}
            if param.enum:
                prop["enum"] = param.enum
            if param.default is not None:
                prop["default"] = param.default
            properties[param.name] = prop
            if param.required:
                required.append(param.name)
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {"type": "object", "properties": properties, "required": required}
            }
        }
    
    def to_mcp_schema(self) -> Dict[str, Any]:
        """转换为MCP协议格式"""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": {
                "type": "object",
                "properties": {
                    p.name: {"type": p.type, "description": p.description, **({"enum": p.enum} if p.enum else {})}
                    for p in self.parameters
                },
                "required": [p.name for p in self.parameters if p.required]
            }
        }


@dataclass
class MCPResource:
    """MCP资源定义"""
    uri: str
    name: str
    description: str = ""
    mime_type: str = "text/plain"


@dataclass 
class MCPServerConfig:
    """MCP服务器配置"""
    name: str
    description: str = ""
    version: str = "1.0.0"
    transport: str = "sse"
    url: Optional[str] = None
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None


# ============================================================
# MCP Server 抽象基类
# ============================================================

class MCPServerBase(ABC):
    """MCP服务器抽象基类"""
    
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._tools: Dict[str, MCPTool] = {}
        self._resources: Dict[str, MCPResource] = {}
    
    @abstractmethod
    async def initialize(self) -> bool:
        pass
    
    @abstractmethod
    async def list_tools(self) -> List[MCPTool]:
        pass
    
    @abstractmethod
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        pass
    
    async def list_resources(self) -> List[MCPResource]:
        return list(self._resources.values())
    
    async def shutdown(self):
        pass
    
    def register_tool(self, tool: MCPTool):
        tool.server_name = self.config.name
        self._tools[tool.name] = tool
    
    def register_resource(self, resource: MCPResource):
        self._resources[resource.uri] = resource


# ============================================================
# 内置MCP服务器
# ============================================================

class BuiltinMCPServer(MCPServerBase):
    """CoolAI平台内置工具服务器"""
    
    def __init__(self):
        super().__init__(MCPServerConfig(
            name="coolai-builtin",
            description="CoolAI内置工具服务器",
            version="1.0.0"
        ))
        self._register_builtin_tools()
    
    def _register_builtin_tools(self):
        # 知识库检索
        self.register_tool(MCPTool(
            name="knowledge_search",
            description="在知识库中检索相关信息。当用户的问题可能需要参考特定文档或知识时使用。",
            parameters=[
                MCPToolParameter(name="query", type="string", description="搜索查询文本", required=True),
                MCPToolParameter(name="top_k", type="integer", description="返回结果数量", required=False, default=5),
            ],
            handler=self._handle_knowledge_search
        ))
        
        # 网络搜索（后期接入真实搜索API）
        self.register_tool(MCPTool(
            name="web_search",
            description="搜索互联网获取最新信息。当需要获取实时信息时使用。",
            parameters=[MCPToolParameter(name="query", type="string", description="搜索关键词", required=True)],
            handler=self._handle_web_search
        ))
        
        # 代码执行
        self.register_tool(MCPTool(
            name="code_execute",
            description="在安全沙箱中执行Python代码。用于计算、数据处理等场景。",
            parameters=[MCPToolParameter(name="code", type="string", description="要执行的Python代码", required=True)],
            handler=self._handle_code_execute
        ))
        
        # TTS
        self.register_tool(MCPTool(
            name="text_to_speech",
            description="将文本转换为语音。",
            parameters=[
                MCPToolParameter(name="text", type="string", description="要转为语音的文本", required=True),
                MCPToolParameter(name="voice", type="string", description="语音ID", required=False, default="zh-CN-XiaoxiaoNeural"),
            ],
            handler=self._handle_tts
        ))
        
        # 天气查询（后期接入真实API）
        self.register_tool(MCPTool(
            name="get_weather",
            description="获取指定城市的天气信息。",
            parameters=[MCPToolParameter(name="city", type="string", description="城市名称", required=True)],
            handler=self._handle_get_weather
        ))
    
    async def initialize(self) -> bool:
        return True
    
    async def list_tools(self) -> List[MCPTool]:
        return list(self._tools.values())
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        tool = self._tools.get(tool_name)
        if not tool:
            raise ValueError(f"工具不存在: {tool_name}")
        if tool.handler:
            try:
                return await tool.handler(**arguments)
            except Exception as e:
                return {"error": str(e)}
        return {"result": f"工具 {tool_name} 执行完成"}
    
    # 工具处理器
    async def _handle_knowledge_search(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        try:
            from app.services.rag_service_impl import get_rag_pipeline
            rag = get_rag_pipeline()
            results = await rag.retrieve(query, top_k=top_k)
            return {"results": [{"content": r.chunk.content, "score": r.score, "source": r.chunk.metadata.get("title", "")} for r in results], "total": len(results)}
        except Exception as e:
            return {"error": f"知识库检索失败: {e}"}
    
    async def _handle_web_search(self, query: str) -> Dict[str, Any]:
        """
        网络搜索工具
        
        优先使用Tavily搜索API，如果未配置则降级为模拟数据
        Tavily API文档: https://tavily.com/documentation
        """
        from app.core.config import settings
        
        tavily_key = settings.TAVILY_API_KEY
        
        if tavily_key:
            # 使用Tavily搜索API
            try:
                import httpx
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.post(
                        "https://api.tavily.com/search",
                        json={
                            "api_key": tavily_key,
                            "query": query,
                            "search_depth": "basic",
                            "include_answer": True,
                            "max_results": 5,
                        }
                    )
                    if response.status_code == 200:
                        data = response.json()
                        results = []
                        for r in data.get("results", []):
                            results.append({
                                "title": r.get("title", ""),
                                "snippet": r.get("content", "")[:500],
                                "url": r.get("url", ""),
                                "score": r.get("score", 0),
                            })
                        return {
                            "query": query,
                            "answer": data.get("answer", ""),
                            "results": results,
                            "source": "tavily",
                        }
                    else:
                        logger.warning(f"Tavily搜索API返回错误: {response.status_code}")
            except Exception as e:
                logger.warning(f"Tavily搜索API调用失败: {e}，降级为模拟数据")
        
        # 降级：返回模拟数据
        return {
            "query": query, 
            "results": [
                {"title": f"搜索结果 - {query}", "snippet": "模拟结果，需配置Tavily API Key以获取真实搜索结果", "url": "https://example.com"}
            ], 
            "note": "当前为模拟结果，请在.env中配置TAVILY_API_KEY"
        }
    
    async def _handle_code_execute(self, code: str) -> Dict[str, Any]:
        import io, sys
        dangerous = ["import os", "import subprocess", "import shutil", "__import__"]
        for kw in dangerous:
            if kw in code:
                return {"error": f"安全限制：包含不允许的操作: {kw}"}
        try:
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            exec(code, {"__builtins__": {}}, {})
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout
            return {"output": output}
        except Exception as e:
            sys.stdout = old_stdout
            return {"error": f"代码执行错误: {e}"}
    
    async def _handle_tts(self, text: str, voice: str = "zh-CN-XiaoxiaoNeural") -> Dict[str, Any]:
        try:
            from app.services.tts_service import get_tts_service, TTSConfig, TTSEngineType, AudioFormat
            tts = get_tts_service()
            config = TTSConfig(engine=TTSEngineType.EDGE, voice=voice, format=AudioFormat.MP3)
            result = await tts.synthesize(text=text, config=config, return_base64=True)
            return {"success": result.success, "audio_size": result.size, "format": "mp3"} if result.success else {"error": result.error}
        except Exception as e:
            return {"error": f"TTS合成失败: {e}"}
    
    async def _handle_get_weather(self, city: str) -> Dict[str, Any]:
        """
        天气查询工具
        
        优先使用OpenWeatherMap API，如果未配置则降级为模拟数据
        OpenWeatherMap API文档: https://openweathermap.org/api
        """
        from app.core.config import settings
        
        weather_key = settings.OPENWEATHER_API_KEY
        
        if weather_key:
            # 使用OpenWeatherMap API
            try:
                import httpx
                async with httpx.AsyncClient(timeout=10.0) as client:
                    # 先获取城市坐标
                    geo_response = await client.get(
                        "http://api.openweathermap.org/geo/1.0/direct",
                        params={"q": city, "limit": 1, "appid": weather_key}
                    )
                    
                    if geo_response.status_code == 200 and geo_response.json():
                        geo_data = geo_response.json()[0]
                        lat, lon = geo_data.get("lat"), geo_data.get("lon")
                        location_name = geo_data.get("local_names", {}).get("zh", geo_data.get("name", city))
                        
                        # 获取天气数据
                        weather_response = await client.get(
                            "https://api.openweathermap.org/data/2.5/weather",
                            params={"lat": lat, "lon": lon, "appid": weather_key, "units": "metric", "lang": "zh_cn"}
                        )
                        
                        if weather_response.status_code == 200:
                            data = weather_response.json()
                            weather_desc = ", ".join(w.get("description", "") for w in data.get("weather", []))
                            return {
                                "city": location_name,
                                "temperature": f"{data['main']['temp']}°C",
                                "feels_like": f"{data['main']['feels_like']}°C",
                                "weather": weather_desc,
                                "humidity": f"{data['main']['humidity']}%",
                                "wind_speed": f"{data.get('wind', {}).get('speed', 0)} m/s",
                                "source": "openweathermap",
                            }
                    else:
                        logger.warning(f"OpenWeatherMap城市查询失败: {city}")
            except Exception as e:
                logger.warning(f"OpenWeatherMap API调用失败: {e}，降级为模拟数据")
        
        # 降级：返回模拟数据
        return {
            "city": city, 
            "temperature": "25°C", 
            "weather": "晴", 
            "humidity": "60%", 
            "note": "当前为模拟数据，请在.env中配置OPENWEATHER_API_KEY"
        }


# ============================================================
# 远程MCP服务器
# ============================================================

class RemoteMCPServer(MCPServerBase):
    """通过SSE/HTTP连接远程MCP服务器"""
    
    def __init__(self, config: MCPServerConfig):
        super().__init__(config)
        self._client = None
    
    async def initialize(self) -> bool:
        import httpx
        if not self.config.url:
            return False
        try:
            self._client = httpx.AsyncClient(base_url=self.config.url, timeout=httpx.Timeout(30.0))
            response = await self._client.post("/", json={
                "jsonrpc": "2.0", "method": "initialize", "id": 1,
                "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "coolai", "version": "1.0.0"}}
            })
            if response.status_code == 200:
                tools = await self.list_tools()
                for tool in tools:
                    self._tools[tool.name] = tool
                return True
            return False
        except Exception as e:
            logger.error(f"远程MCP服务器连接失败: {e}")
            return False
    
    async def list_tools(self) -> List[MCPTool]:
        if not self._client:
            return []
        try:
            response = await self._client.post("/", json={"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 2})
            if response.status_code == 200:
                result = response.json()
                tools = []
                for td in result.get("result", {}).get("tools", []):
                    params = []
                    schema = td.get("inputSchema", {})
                    for name, prop in schema.get("properties", {}).items():
                        params.append(MCPToolParameter(name=name, type=prop.get("type", "string"), description=prop.get("description", ""), required=name in schema.get("required", [])))
                    tools.append(MCPTool(name=td["name"], description=td.get("description", ""), parameters=params, server_name=self.config.name))
                return tools
        except Exception as e:
            logger.error(f"获取远程工具列表失败: {e}")
        return []
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        if not self._client:
            raise ValueError("MCP服务器未连接")
        response = await self._client.post("/", json={"jsonrpc": "2.0", "method": "tools/call", "params": {"name": tool_name, "arguments": arguments}, "id": 3})
        if response.status_code == 200:
            return response.json().get("result")
        raise Exception(f"工具调用失败: {response.status_code}")
    
    async def shutdown(self):
        if self._client:
            await self._client.aclose()


# ============================================================
# MCP 注册中心
# ============================================================

class MCPRegistry:
    """MCP注册中心 - 管理所有MCP服务器的注册、发现和调用"""
    
    def __init__(self):
        self._servers: Dict[str, MCPServerBase] = {}
        self._tool_to_server: Dict[str, str] = {}
    
    async def register_server(self, server: MCPServerBase) -> bool:
        try:
            success = await server.initialize()
            if not success:
                return False
            self._servers[server.config.name] = server
            tools = await server.list_tools()
            for tool in tools:
                self._tool_to_server[tool.name] = server.config.name
            logger.info(f"MCP服务器注册成功: {server.config.name}, 工具数: {len(tools)}")
            return True
        except Exception as e:
            logger.error(f"MCP服务器注册失败: {e}")
            return False
    
    def get_all_tools(self) -> List[MCPTool]:
        all_tools = []
        for server in self._servers.values():
            all_tools.extend(server._tools.values())
        return all_tools
    
    def get_tools_as_openai_format(self) -> List[Dict[str, Any]]:
        return [tool.to_openai_function() for tool in self.get_all_tools()]
    
    def get_tool(self, tool_name: str) -> Optional[MCPTool]:
        server_name = self._tool_to_server.get(tool_name)
        if server_name and server_name in self._servers:
            return self._servers[server_name]._tools.get(tool_name)
        return None
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        server_name = self._tool_to_server.get(tool_name)
        if not server_name:
            raise ValueError(f"工具不存在: {tool_name}")
        server = self._servers.get(server_name)
        if not server:
            raise ValueError(f"MCP服务器不存在: {server_name}")
        return await server.call_tool(tool_name, arguments)
    
    def list_servers(self) -> List[Dict[str, Any]]:
        return [{"name": s.config.name, "description": s.config.description, "tool_count": len(s._tools)} for s in self._servers.values()]


# 全局实例
_mcp_registry: Optional[MCPRegistry] = None

def get_mcp_registry() -> MCPRegistry:
    global _mcp_registry
    if _mcp_registry is None:
        _mcp_registry = MCPRegistry()
    return _mcp_registry

async def initialize_mcp_registry() -> MCPRegistry:
    registry = get_mcp_registry()
    await registry.register_server(BuiltinMCPServer())
    return registry
