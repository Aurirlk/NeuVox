"""
情感分析器
从文本或语音中提取情绪信息
"""
import json
import re
from enum import Enum
from typing import Dict, Any, Optional

from app.utils.logger import logger


class EmotionType(str, Enum):
    """情绪类型"""
    HAPPY = "happy"          # 开心
    SAD = "sad"              # 悲伤
    ANGRY = "angry"          # 生气
    NEUTRAL = "neutral"      # 中性
    SURPRISED = "surprised"  # 惊讶
    FEARFUL = "fearful"      # 害怕
    DISGUSTED = "disgusted"  # 厌恶


class EmotionAnalyzer:
    """
    情感分析器
    
    支持：
    - 文本情感分析（关键词 + LLM）
    - 情感强度评估
    - 情感到 TTS 参数映射
    """
    
    # 情感关键词映射
    EMOTION_KEYWORDS = {
        EmotionType.HAPPY: {
            "keywords": ["开心", "高兴", "快乐", "太好了", "哈哈", "嘻嘻", "棒", "厉害", "喜欢", "爱"],
            "emoji": "😊",
            "tts_style": "cheerful"
        },
        EmotionType.SAD: {
            "keywords": ["难过", "伤心", "失望", "郁闷", "不开心", "哎", "唉", "可惜"],
            "emoji": "😢",
            "tts_style": "sad"
        },
        EmotionType.ANGRY: {
            "keywords": ["生气", "愤怒", "讨厌", "烦死了", "气死", "滚", "闭嘴"],
            "emoji": "😠",
            "tts_style": "angry"
        },
        EmotionType.SURPRISED: {
            "keywords": ["惊讶", "天哪", "哇", "不会吧", "真的吗", "居然", "竟然"],
            "emoji": "😲",
            "tts_style": "surprised"
        },
        EmotionType.FEARFUL: {
            "keywords": ["害怕", "恐惧", "吓死", "好怕", "不敢", "危险"],
            "emoji": "😨",
            "tts_style": "fearful"
        },
        EmotionType.DISGUSTED: {
            "keywords": ["恶心", "讨厌", "受不了", "无语", "吐了"],
            "emoji": "🤢",
            "tts_style": "disgusted"
        },
    }
    
    # 情感强度关键词
    INTENSITY_KEYWORDS = {
        "high": ["非常", "特别", "超级", "太", "极", "超", "巨"],
        "medium": ["很", "挺", "蛮", "比较"],
        "low": ["有点", "稍微", "一点", "略微"]
    }
    
    # TTS 风格映射
    TTS_STYLE_MAP = {
        "cheerful": {"speed": 1.1, "pitch": "high"},
        "sad": {"speed": 0.85, "pitch": "low"},
        "angry": {"speed": 1.2, "pitch": "medium"},
        "surprised": {"speed": 1.15, "pitch": "high"},
        "fearful": {"speed": 0.9, "pitch": "high"},
        "disgusted": {"speed": 0.95, "pitch": "medium"},
        "neutral": {"speed": 1.0, "pitch": "medium"}
    }
    
    def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        分析文本情感
        
        Args:
            text: 输入文本
            
        Returns:
            情感分析结果
        """
        emotion = EmotionType.NEUTRAL
        confidence = 0.5
        intensity = "medium"
        emotions_found = []
        
        # 检查情感关键词
        for emotion_type, rules in self.EMOTION_KEYWORDS.items():
            for keyword in rules["keywords"]:
                if keyword in text:
                    emotions_found.append(emotion_type)
                    break
        
        # 检查强度关键词
        for level, keywords in self.INTENSITY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    intensity = level
                    break
        
        # 确定主要情感
        if emotions_found:
            # 取第一个匹配的情感（可以优化为投票机制）
            emotion = emotions_found[0]
            confidence = 0.8 if len(emotions_found) == 1 else 0.7
        
        # 获取 TTS 风格
        tts_style = self.EMOTION_KEYWORDS.get(emotion, {}).get("tts_style", "neutral")
        emoji = self.EMOTION_KEYWORDS.get(emotion, {}).get("emoji", "")
        
        result = {
            "emotion": emotion.value,
            "emotion_label": emotion.value,
            "confidence": confidence,
            "intensity": intensity,
            "tts_style": tts_style,
            "emoji": emoji,
            "emotions_found": [e.value for e in emotions_found]
        }
        
        logger.debug(f"[Emotion] 文本情感: {emotion.value} (置信度: {confidence})")
        return result
    
    async def analyze_with_llm(self, text: str) -> Dict[str, Any]:
        """
        使用 LLM 进行情感分析（更准确）
        
        Args:
            text: 输入文本
            
        Returns:
            情感分析结果
        """
        try:
            from app.services.factory import ServiceFactory
            
            llm_service = ServiceFactory.create_llm()
            
            prompt = f"""分析以下文本的情感，返回 JSON 格式：
文本：{text}

返回格式：
{{
    "emotion": "happy/sad/angry/neutral/surprised/fearful/disgusted",
    "confidence": 0.85,
    "intensity": "high/medium/low",
    "reason": "情感分析原因"
}}"""
            
            response = await llm_service.chat(prompt)
            
            # 解析 JSON
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
            
            result = json.loads(response.strip())
            
            # 添加 TTS 风格
            emotion_str = result.get("emotion", "neutral")
            try:
                emotion = EmotionType(emotion_str)
            except ValueError:
                emotion = EmotionType.NEUTRAL
            
            result["emotion"] = emotion.value
            result["tts_style"] = self.EMOTION_KEYWORDS.get(emotion, {}).get("tts_style", "neutral")
            result["emoji"] = self.EMOTION_KEYWORDS.get(emotion, {}).get("emoji", "")
            
            return result
            
        except Exception as e:
            logger.warning(f"[Emotion] LLM 情感分析失败，使用关键词分析: {e}")
            return self.analyze_text(text)
    
    def get_tts_params(self, emotion: str) -> Dict[str, Any]:
        """
        根据情感获取 TTS 参数
        
        Args:
            emotion: 情感类型
            
        Returns:
            TTS 参数
        """
        style = self.TTS_STYLE_MAP.get(emotion, self.TTS_STYLE_MAP["neutral"])
        
        return {
            "speed": style["speed"],
            "pitch": style["pitch"]
        }
    
    def get_emotion_label(self, emotion: str) -> str:
        """获取情感标签（带 emoji）"""
        emotion_type = EmotionType(emotion) if emotion in [e.value for e in EmotionType] else EmotionType.NEUTRAL
        return self.EMOTION_KEYWORDS.get(emotion_type, {}).get("emoji", "") + " " + emotion


# 全局情感分析器实例
emotion_analyzer = EmotionAnalyzer()
