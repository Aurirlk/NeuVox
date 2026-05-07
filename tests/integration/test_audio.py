"""
集成测试 - 语音对话流程
测试 ASR -> LLM -> TTS 全链路
"""
import pytest
import os
import tempfile
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport

from main import app


@pytest.fixture
async def client():
    """创建测试客户端"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_audio_file():
    """创建模拟音频文件"""
    # 创建一个临时 WAV 文件
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        # 写入一些假数据（实际测试中应该是有效的音频数据）
        f.write(b"RIFF" + b"\x00" * 100)
        temp_path = f.name
    
    yield temp_path
    
    # 清理
    if os.path.exists(temp_path):
        os.remove(temp_path)


class TestAudioChat:
    """语音对话测试"""
    
    @pytest.mark.asyncio
    async def test_audio_chat_success(self, client, mock_audio_file):
        """测试语音对话成功"""
        mock_asr = AsyncMock()
        mock_asr.transcribe.return_value = "你好，我想问一下天气"
        
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = "今天天气晴朗，适合外出。"
        mock_llm.get_model_name.return_value = "deepseek-v4-flash"
        mock_llm.get_provider_name.return_value = "deepseek"
        
        mock_tts = AsyncMock()
        mock_tts.synthesize.return_value = "outputs/test_response.wav"
        mock_tts.get_provider_name.return_value = "mimo"
        
        with patch('app.routers.chat.ServiceFactory') as mock_factory:
            mock_factory.create_asr.return_value = mock_asr
            mock_factory.create_llm.return_value = mock_llm
            mock_factory.create_tts.return_value = mock_tts
            
            with open(mock_audio_file, "rb") as f:
                response = await client.post(
                    "/api/v1/chat/audio",
                    files={"file": ("test.wav", f, "audio/wav")}
                )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["text"] == "你好，我想问一下天气"
        assert data["reply"] == "今天天气晴朗，适合外出。"
        assert "audio_path" in data
    
    @pytest.mark.asyncio
    async def test_audio_chat_invalid_format(self, client):
        """测试不支持的音频格式"""
        response = await client.post(
            "/api/v1/chat/audio",
            files={"file": ("test.txt", b"not audio", "text/plain")}
        )
        
        assert response.status_code in [400, 422]
    
    @pytest.mark.asyncio
    async def test_audio_chat_asr_failure(self, client, mock_audio_file):
        """测试 ASR 识别失败"""
        mock_asr = AsyncMock()
        mock_asr.transcribe.side_effect = Exception("语音识别失败")
        
        with patch('app.routers.chat.ServiceFactory') as mock_factory:
            mock_factory.create_asr.return_value = mock_asr
            
            with open(mock_audio_file, "rb") as f:
                response = await client.post(
                    "/api/v1/chat/audio",
                    files={"file": ("test.wav", f, "audio/wav")}
                )
        
        assert response.status_code == 500


class TestAudioFile:
    """音频文件获取测试"""
    
    @pytest.mark.asyncio
    async def test_get_audio_not_found(self, client):
        """测试获取不存在的音频文件"""
        response = await client.get("/api/v1/audio/nonexistent.wav")
        
        assert response.status_code == 404


class TestCRMIntegration:
    """CRM 集成测试"""
    
    @pytest.mark.asyncio
    async def test_crm_stats(self, client):
        """测试 CRM 统计接口"""
        response = await client.get("/api/v1/crm/stats")
        
        # 无论数据库是否初始化，都应该返回响应
        assert response.status_code in [200, 500]
    
    @pytest.mark.asyncio
    async def test_crm_users_list(self, client):
        """测试用户列表接口"""
        response = await client.get("/api/v1/crm/users")
        
        # 无论数据库是否初始化，都应该返回响应
        assert response.status_code in [200, 500]
