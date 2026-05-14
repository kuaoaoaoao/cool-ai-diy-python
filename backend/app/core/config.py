# ============================================================
# 应用配置模块
# ============================================================
"""
本模块负责管理应用程序的所有配置参数
使用Pydantic Settings进行配置管理
"""

from typing import List, Optional
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    """应用全局配置类"""
    
    # ============================================================
    # 应用基础配置
    # ============================================================
    APP_NAME: str = "CoolAI智能业务平台"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    APP_SECRET_KEY: str = "your-secret-key-change-in-production"
    APP_JWT_ALGORITHM: str = "HS256"
    APP_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    
    # ============================================================
    # 数据库配置
    # ============================================================
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/coolai"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    
    # ============================================================
    # Redis缓存配置
    # ============================================================
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # ============================================================
    # Milvus向量数据库配置
    # ============================================================
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_COLLECTION: str = "coolai_knowledge"
    
    # ============================================================
    # LLM大模型配置
    # ============================================================
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4-turbo-preview"
    
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_BASE_URL: str = "https://api.anthropic.com"
    
    LOCAL_LLM_BASE_URL: str = "http://localhost:8000/v1"
    LOCAL_LLM_API_KEY: str = "EMPTY"
    LOCAL_LLM_MODEL: str = "chatglm3-6b"
    
    # ============================================================
    # TTS语音合成配置
    # ============================================================
    TTS_ENGINE: str = "edge"
    TTS_DEFAULT_VOICE: str = "zh-CN-XiaoxiaoNeural"
    TTS_DEFAULT_SPEED: float = 1.0
    TTS_SAMPLE_RATE: int = 24000
    TTS_OUTPUT_DIR: str = "./data/tts_output"
    
    # ============================================================
    # Embedding嵌入模型配置
    # ============================================================
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    EMBEDDING_BATCH_SIZE: int = 32
    
    # ============================================================
    # 文件上传配置
    # ============================================================
    ALLOWED_DOCUMENT_TYPES: List[str] = [".txt", ".pdf", ".docx", ".md"]
    MAX_FILE_SIZE: int = 100 * 1024 * 1024
    UPLOAD_DIR: str = "./data/uploads"
    
    # ============================================================
    # CORS跨域配置
    # ============================================================
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]
    
    # ============================================================
    # 日志与监控配置
    # ============================================================
    LOG_LEVEL: str = "INFO"
    ENABLE_METRICS: bool = True
    METRICS_PATH: str = "/metrics"
    
    # ============================================================
    # RAG知识库配置
    # ============================================================
    RAG_CHUNK_SIZE: int = 500
    RAG_CHUNK_OVERLAP: int = 50
    RAG_TOP_K: int = 5
    RAG_RRF_K: int = 60
    RAG_SIMILARITY_THRESHOLD: float = 0.5
    
    # ============================================================
    # MCP外部API配置
    # ============================================================
    # Tavily搜索API (https://tavily.com) - 留空则使用模拟数据
    TAVILY_API_KEY: str = ""
    # OpenWeatherMap API (https://openweathermap.org/api) - 留空则使用模拟数据
    OPENWEATHER_API_KEY: str = ""
    
    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}")
        return v.upper()
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """获取应用配置单例"""
    return Settings()


settings = get_settings()
