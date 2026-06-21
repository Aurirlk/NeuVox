"""
应用配置模块
"""
import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """应用配置"""
    
    # 应用基础配置
    APP_NAME: str = "小智语音交互服务"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    
    # API 配置
    API_V1_PREFIX: str = "/api/v1"
    
    # DeepSeek API 配置 (LLM - 主选)
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_API_URL: str = "https://api.deepseek.com/v1/chat/completions"
    DEEPSEEK_MODEL: str = "deepseek-v4-flash"
    
    # MiMo TTS API 配置 (主选)
    MIMO_TTS_API_KEY: Optional[str] = None
    MIMO_TTS_API_URL: str = "https://api.minimax.chat/v1/t2a_v2"
    MIMO_TTS_MODEL: str = "mimo-v2.5-tts"
    
    # MiniMax API 配置 (备份 LLM + TTS)
    MINIMAX_API_KEY: Optional[str] = None
    MINIMAX_GROUP_ID: Optional[str] = None
    MINIMAX_LLM_URL: str = "https://api.minimax.chat/v1/text/chatcompletion_v2"
    MINIMAX_LLM_MODEL: str = "MiniMax-Text-01"
    MINIMAX_TTS_URL: str = "https://api.minimax.chat/v1/t2a_v2"
    MINIMAX_TTS_MODEL: str = "speech-01"
    MINIMAX_ASR_URL: str = "https://api.minimax.chat/v1/t2a_v2"
    
    # 和风天气 API 配置
    QWEATHER_API_KEY: Optional[str] = None
    
    # 文件存储配置
    UPLOAD_DIR: str = "uploads"
    OUTPUT_DIR: str = "outputs"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    
    # TTS 配置
    TTS_VOICE: str = "male-qn-qingse"
    TTS_SPEED: float = 1.0
    
    # LLM 配置
    LLM_MODEL: str = "MiniMax-Text-01"
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 2048
    
    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # WebSocket 配置
    WS_HOST: str = "0.0.0.0"
    WS_PORT: int = 8001
    
    # OTA 配置
    OTA_HOST: str = "0.0.0.0"
    OTA_PORT: int = 8003
    
    # 数据库配置
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/neuvox.db"
    KNOWLEDGE_DB_URL: str = "sqlite+aiosqlite:///./data/knowledge.db"
    MEMORY_DB_PATH: str = "data/memory_db"
    
    # 成本控制配置
    COST_DAILY_LIMIT: float = 10.0      # 日限额（元）
    COST_MONTHLY_LIMIT: float = 200.0   # 月限额（元）
    COST_WARN_THRESHOLD: float = 0.8    # 预警阈值
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"


settings = Settings()

# 确保上传和输出目录存在
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
