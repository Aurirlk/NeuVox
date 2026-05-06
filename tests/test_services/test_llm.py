"""
LLM 服务单元测试
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.services.llm.deepseek_llm import DeepSeekLLM
from app.services.llm.minimax_llm import MiniMaxLLM


class TestDeepSeekLLM:
    """DeepSeek LLM 测试"""
    
    @pytest.fixture
    def llm_service(self):
        """创建 LLM 服务实例"""
        with patch('app.services.llm.deepseek_llm.settings') as mock_settings:
            mock_settings.DEEPSEEK_API_KEY = "test_key"
            mock_settings.DEEPSEEK_API_URL = "https://api.deepseek.com/test"
            mock_settings.DEEPSEEK_MODEL = "deepseek-v4-flash"
            mock_settings.LLM_TEMPERATURE = 0.7
            mock_settings.LLM_MAX_TOKENS = 2048
            return DeepSeekLLM()
    
    @pytest.mark.asyncio
    async def test_chat_success(self, llm_service):
        """测试聊天成功"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "你好！"}}]
        }
        
        with patch('httpx.AsyncClient.post', new_callable=AsyncMock, return_value=mock_response):
            result = await llm_service.chat("你好")
            assert result == "你好！"
    
    @pytest.mark.asyncio
    async def test_chat_without_api_key(self):
        """测试无 API Key 时抛出异常"""
        with patch('app.services.llm.deepseek_llm.settings') as mock_settings:
            mock_settings.DEEPSEEK_API_KEY = None
            service = DeepSeekLLM()
            
            with pytest.raises(ValueError, match="DEEPSEEK_API_KEY 未配置"):
                await service.chat("你好")
    
    @pytest.mark.asyncio
    async def test_chat_api_error(self, llm_service):
        """测试 API 错误"""
        mock_response = AsyncMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        
        with patch('httpx.AsyncClient.post', return_value=mock_response):
            with pytest.raises(Exception, match="DeepSeek 对话失败"):
                await llm_service.chat("你好")
    
    @pytest.mark.asyncio
    async def test_chat_timeout(self, llm_service):
        """测试超时重试"""
        with patch('httpx.AsyncClient.post', side_effect=httpx.TimeoutException("Timeout")):
            with pytest.raises(Exception):
                await llm_service.chat("你好")
    
    def test_build_messages(self, llm_service):
        """测试消息构建"""
        messages = llm_service._build_messages("你好", [{"role": "user", "content": "之前的消息"}])
        
        assert len(messages) == 3
        assert messages[0]["role"] == "system"
        assert messages[1]["content"] == "之前的消息"
        assert messages[2]["content"] == "你好"
    
    def test_get_model_name(self, llm_service):
        """测试获取模型名称"""
        assert llm_service.get_model_name() == "deepseek-v4-flash"
    
    def test_get_provider_name(self, llm_service):
        """测试获取提供商名称"""
        assert llm_service.get_provider_name() == "deepseek"


class TestMiniMaxLLM:
    """MiniMax LLM 测试"""
    
    @pytest.fixture
    def llm_service(self):
        """创建 LLM 服务实例"""
        with patch('app.services.llm.minimax_llm.settings') as mock_settings:
            mock_settings.MINIMAX_API_KEY = "test_key"
            mock_settings.MINIMAX_LLM_URL = "https://api.minimax.chat/test"
            mock_settings.MINIMAX_LLM_MODEL = "MiniMax-Text-01"
            mock_settings.MINIMAX_GROUP_ID = "test_group"
            mock_settings.LLM_TEMPERATURE = 0.7
            mock_settings.LLM_MAX_TOKENS = 2048
            return MiniMaxLLM()
    
    @pytest.mark.asyncio
    async def test_chat_success(self, llm_service):
        """测试聊天成功"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "MiniMax 回复"}}]
        }
        
        with patch('httpx.AsyncClient.post', new_callable=AsyncMock, return_value=mock_response):
            result = await llm_service.chat("你好")
            assert result == "MiniMax 回复"
    
    def test_get_provider_name(self, llm_service):
        """测试获取提供商名称"""
        assert llm_service.get_provider_name() == "minimax"
