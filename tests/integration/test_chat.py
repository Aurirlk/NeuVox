"""
集成测试 - 文本对话流程
测试 ASR -> LLM -> TTS 全链路
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport

from main import app


@pytest.fixture
async def client():
    """创建测试客户端"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestHealthCheck:
    """健康检查测试"""
    
    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """测试健康检查接口"""
        response = await client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "0.1.0"
        assert "services" in data


class TestTextChat:
    """文本对话测试"""
    
    @pytest.mark.asyncio
    async def test_text_chat_success(self, client):
        """测试文本对话成功"""
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = "你好！有什么可以帮助你的吗？"
        mock_llm.get_model_name.return_value = "deepseek-v4-flash"
        mock_llm.get_provider_name.return_value = "deepseek"
        
        mock_tts = AsyncMock()
        mock_tts.synthesize.return_value = "outputs/test.wav"
        mock_tts.get_provider_name.return_value = "mimo"
        
        with patch('app.routers.chat.ServiceFactory') as mock_factory:
            mock_factory.create_llm.return_value = mock_llm
            mock_factory.create_tts.return_value = mock_tts
            
            response = await client.post(
                "/api/v1/chat/text",
                json={"message": "你好", "history": []}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["message"] == "你好！有什么可以帮助你的吗？"
        assert "audio_path" in data
    
    @pytest.mark.asyncio
    async def test_text_chat_with_history(self, client):
        """测试带历史记录的文本对话"""
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = "我记得你之前问过天气。"
        mock_llm.get_model_name.return_value = "deepseek-v4-flash"
        mock_llm.get_provider_name.return_value = "deepseek"
        
        with patch('app.routers.chat.ServiceFactory') as mock_factory:
            mock_factory.create_llm.return_value = mock_llm
            mock_factory.create_tts.side_effect = Exception("TTS 不可用")
            
            response = await client.post(
                "/api/v1/chat/text",
                json={
                    "message": "那现在呢？",
                    "history": [
                        {"role": "user", "content": "今天天气怎么样？"},
                        {"role": "assistant", "content": "今天天气晴朗。"}
                    ]
                }
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
    
    @pytest.mark.asyncio
    async def test_text_chat_empty_message(self, client):
        """测试空消息"""
        response = await client.post(
            "/api/v1/chat/text",
            json={"message": "", "history": []}
        )
        
        # 空消息应该返回错误
        assert response.status_code in [400, 422, 500]


class TestProviders:
    """提供商查询测试"""
    
    @pytest.mark.asyncio
    async def test_get_providers(self, client):
        """测试获取提供商列表"""
        response = await client.get("/api/v1/providers")
        
        assert response.status_code == 200
        data = response.json()
        assert "llm" in data
        assert "tts" in data
        assert "asr" in data
        assert "deepseek" in data["llm"]
        assert "mimo" in data["tts"]


class TestVoices:
    """音色查询测试"""
    
    @pytest.mark.asyncio
    async def test_get_voices(self, client):
        """测试获取音色列表"""
        mock_tts = AsyncMock()
        mock_tts.get_voices.return_value = [
            {"id": "mimo-v2.5-tts", "name": "MiMo 标准语音"}
        ]
        
        with patch('app.routers.chat.ServiceFactory') as mock_factory:
            mock_factory.create_tts.return_value = mock_tts
            
            response = await client.get("/api/v1/voices")
        
        assert response.status_code == 200
        data = response.json()
        assert "voices" in data
        assert len(data["voices"]) > 0
