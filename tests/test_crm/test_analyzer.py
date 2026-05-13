"""
CRM 分析器单元测试
"""
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock

from app.crm.analyzer import CRMAnalyzer, crm_analyzer, CRM_EXTRACTION_PROMPT


class TestCRMAnalyzer:
    """CRM 分析器测试"""
    
    @pytest.fixture
    def analyzer(self):
        """创建分析器实例"""
        return CRMAnalyzer()
    
    @pytest.mark.asyncio
    async def test_extract_user_info_success(self, analyzer):
        """测试成功提取用户信息"""
        mock_response = '''
        {
            "name": "张三",
            "gender": "男",
            "age_range": "25-30岁",
            "occupation": "程序员",
            "city": "北京",
            "preferences": {
                "hobbies": ["编程", "阅读"],
                "food": ["咖啡"],
                "music": ["流行"],
                "other": []
            },
            "intent": "咨询",
            "budget_range": null,
            "tags": ["技术人员"],
            "notes": null
        }
        '''
        
        with patch.object(analyzer, '_get_llm') as mock_get_llm:
            mock_llm = AsyncMock()
            mock_llm.chat.return_value = mock_response
            mock_get_llm.return_value = mock_llm
            
            result = await analyzer.extract_user_info("用户：我叫张三，是一名程序员，住在北京")
            
            assert result["name"] == "张三"
            assert result["gender"] == "男"
            assert result["occupation"] == "程序员"
            assert result["city"] == "北京"
            assert "编程" in result["preferences"]["hobbies"]
    
    @pytest.mark.asyncio
    async def test_extract_user_info_json_error(self, analyzer):
        """测试 JSON 解析失败"""
        with patch.object(analyzer, '_get_llm') as mock_get_llm:
            mock_llm = AsyncMock()
            mock_llm.chat.return_value = "这不是JSON格式"
            mock_get_llm.return_value = mock_llm
            
            result = await analyzer.extract_user_info("测试消息")
            
            assert result == {}
    
    @pytest.mark.asyncio
    async def test_extract_user_info_exception(self, analyzer):
        """测试异常处理"""
        with patch.object(analyzer, '_get_llm') as mock_get_llm:
            mock_llm = AsyncMock()
            mock_llm.chat.side_effect = Exception("API 错误")
            mock_get_llm.return_value = mock_llm
            
            result = await analyzer.extract_user_info("测试消息")
            
            assert result == {}
    
    def test_merge_profile(self, analyzer):
        """测试合并用户画像"""
        from app.models.crm_models import UserProfile
        
        profile = UserProfile(user_id="test_user")
        
        new_data = {
            "name": "李四",
            "gender": "女",
            "city": "上海",
            "preferences": {
                "hobbies": ["阅读", "音乐"],
                "food": ["咖啡"]
            },
            "tags": ["新用户"]
        }
        
        updated = analyzer._merge_profile(profile, new_data)
        
        assert updated.name == "李四"
        assert updated.gender == "女"
        assert updated.city == "上海"
        assert "阅读" in updated.preferences["hobbies"]
        assert "音乐" in updated.preferences["hobbies"]
        assert "新用户" in updated.tags
    
    def test_merge_profile_existing_data(self, analyzer):
        """测试合并已有数据"""
        from app.models.crm_models import UserProfile
        
        profile = UserProfile(user_id="test_user")
        profile.name = "旧名字"
        profile.preferences = {"hobbies": ["旧爱好"]}
        profile.tags = ["旧标签"]
        
        new_data = {
            "name": "新名字",
            "preferences": {
                "hobbies": ["新爱好"]
            },
            "tags": ["新标签"]
        }
        
        updated = analyzer._merge_profile(profile, new_data)
        
        # 名字应该被更新
        assert updated.name == "新名字"
        # 爱好应该合并
        assert "旧爱好" in updated.preferences["hobbies"]
        assert "新爱好" in updated.preferences["hobbies"]
        # 标签应该合并
        assert "旧标签" in updated.tags
        assert "新标签" in updated.tags
    
    @pytest.mark.asyncio
    async def test_extract_intent(self, analyzer):
        """测试意图提取"""
        mock_response = '''
        {
            "intent": "weather",
            "confidence": 0.95,
            "entities": {"city": "北京"}
        }
        '''
        
        with patch.object(analyzer, '_get_llm') as mock_get_llm:
            mock_llm = AsyncMock()
            mock_llm.chat.return_value = mock_response
            mock_get_llm.return_value = mock_llm
            
            result = await analyzer.extract_intent("北京天气怎么样")
            
            assert result["intent"] == "weather"
            assert result["confidence"] == 0.95
            assert result["entities"]["city"] == "北京"
    
    @pytest.mark.asyncio
    async def test_extract_intent_fallback(self, analyzer):
        """测试意图提取失败降级"""
        with patch.object(analyzer, '_get_llm') as mock_get_llm:
            mock_llm = AsyncMock()
            mock_llm.chat.side_effect = Exception("API 错误")
            mock_get_llm.return_value = mock_llm
            
            result = await analyzer.extract_intent("测试消息")
            
            assert result["intent"] == "chat"
            assert result["confidence"] == 0.5
    
    def test_extraction_prompt_format(self):
        """测试提取提示词格式"""
        assert "{conversation}" in CRM_EXTRACTION_PROMPT
        assert "JSON" in CRM_EXTRACTION_PROMPT or "json" in CRM_EXTRACTION_PROMPT
