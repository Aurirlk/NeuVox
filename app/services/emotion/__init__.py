"""
情感分析模块
支持文本和语音的情感识别
"""
from app.services.emotion.analyzer import EmotionAnalyzer, EmotionType

__all__ = ["EmotionAnalyzer", "EmotionType"]
