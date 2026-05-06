"""
TTS 服务单元测试
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.services.tts.mimo_tts import MiMoTTS
from app.services.tts.minimax_tts import MiniMaxTTS


class TestMiMoTTS:
    """MiMo TTS 测试"""
    
    @pytest.fixture
    def tts_service(self):
        """创建 TTS 服务实例"""
        with patch('app.services.tts.mimo_tts.settings') as mock_settings:
            mock_settings.MIMO_TTS_API_KEY = "test_key"
            mock_settings.MIMO_TTS_API_URL = "https://api.minimax.chat/test"
            mock_settings.MIMO_TTS_MODEL = "mimo-v2.5-tts"
            mock_settings.TTS_VOICE = "male-qn-qingse"
            mock_settings.TTS_SPEED = 1.0
            mock_settings.OUTPUT_DIR = "outputs"
            return MiMoTTS()
    
    @pytest.mark.asyncio
    async def test_synthesize_success(self, tts_service):
        """测试语音合成成功"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"audio": "http://example.com/audio.wav"}
        }
        
        mock_audio_response = MagicMock()
        mock_audio_response.content = b"audio_data"
        
        with patch('httpx.AsyncClient.post', new_callable=AsyncMock, return_value=mock_response):
            with patch('httpx.AsyncClient.get', new_callable=AsyncMock, return_value=mock_audio_response):
                with patch('builtins.open', MagicMock()):
                    result = await tts_service.synthesize("你好")
                    assert "outputs" in result and "tts_" in result
    
    @pytest.mark.asyncio
    async def test_synthesize_empty_text(self, tts_service):
        """测试空文本抛出异常"""
        with pytest.raises(ValueError, match="文本内容不能为空"):
            await tts_service.synthesize("")
    
    @pytest.mark.asyncio
    async def test_synthesize_without_api_key(self):
        """测试无 API Key 时抛出异常"""
        with patch('app.services.tts.mimo_tts.settings') as mock_settings:
            mock_settings.MIMO_TTS_API_KEY = None
            service = MiMoTTS()
            
            with pytest.raises(ValueError, match="MIMO_TTS_API_KEY 未配置"):
                await service.synthesize("你好")
    
    @pytest.mark.asyncio
    async def test_synthesize_api_error(self, tts_service):
        """测试 API 错误"""
        mock_response = AsyncMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        
        with patch('httpx.AsyncClient.post', return_value=mock_response):
            with pytest.raises(Exception, match="MiMo 语音合成失败"):
                await tts_service.synthesize("你好")
    
    @pytest.mark.asyncio
    async def test_get_voices(self, tts_service):
        """测试获取音色列表"""
        voices = await tts_service.get_voices()
        
        assert len(voices) == 3
        assert voices[0]["id"] == "mimo-v2.5-tts"
    
    def test_get_provider_name(self, tts_service):
        """测试获取提供商名称"""
        assert tts_service.get_provider_name() == "mimo"


class TestMiniMaxTTS:
    """MiniMax TTS 测试"""
    
    @pytest.fixture
    def tts_service(self):
        """创建 TTS 服务实例"""
        with patch('app.services.tts.minimax_tts.settings') as mock_settings:
            mock_settings.MINIMAX_API_KEY = "test_key"
            mock_settings.MINIMAX_TTS_URL = "https://api.minimax.chat/test"
            mock_settings.MINIMAX_TTS_MODEL = "speech-01"
            mock_settings.TTS_VOICE = "male-qn-qingse"
            mock_settings.TTS_SPEED = 1.0
            mock_settings.OUTPUT_DIR = "outputs"
            return MiniMaxTTS()
    
    @pytest.mark.asyncio
    async def test_get_voices(self, tts_service):
        """测试获取音色列表"""
        voices = await tts_service.get_voices()
        
        assert len(voices) == 7
        assert voices[0]["id"] == "male-qn-qingse"
    
    def test_get_provider_name(self, tts_service):
        """测试获取提供商名称"""
        assert tts_service.get_provider_name() == "minimax"
