"""
测试配置
"""
import pytest
import asyncio
import os
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock

# 设置测试环境变量
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_xiaozhi.db"

from main import app
from app.database import init_db


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    """初始化测试数据库"""
    await init_db()
    yield
    # 清理测试数据库
    import gc
    gc.collect()
    try:
        if os.path.exists("test_xiaozhi.db"):
            os.remove("test_xiaozhi.db")
    except PermissionError:
        pass  # 忽略文件锁定错误


@pytest.fixture
async def client() -> AsyncGenerator:
    """创建测试客户端"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_llm_service():
    """模拟 LLM 服务"""
    mock = MagicMock()
    mock.chat = AsyncMock(return_value="你好！我是智能语音助手，有什么可以帮助你的吗？")
    mock.get_model_name.return_value = "deepseek-v4-flash"
    mock.get_provider_name.return_value = "deepseek"
    return mock


@pytest.fixture
def mock_tts_service():
    """模拟 TTS 服务"""
    mock = MagicMock()
    mock.synthesize = AsyncMock(return_value="outputs/tts_test.wav")
    mock.get_voices = AsyncMock(return_value=[
        {"id": "mimo-v2.5-tts", "name": "MiMo 标准语音"}
    ])
    mock.get_provider_name.return_value = "mimo"
    return mock


@pytest.fixture
def mock_asr_service():
    """模拟 ASR 服务"""
    mock = MagicMock()
    mock.transcribe = AsyncMock(return_value="你好，我想问一下天气")
    mock.get_supported_formats.return_value = [".wav", ".mp3"]
    mock.get_provider_name.return_value = "minimax"
    return mock
