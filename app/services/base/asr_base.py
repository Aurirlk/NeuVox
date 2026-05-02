"""
ASR (Automatic Speech Recognition) 抽象基类
定义语音识别服务的统一接口
"""
from abc import ABC, abstractmethod
from typing import List, Optional


class ASRBase(ABC):
    """语音识别服务抽象基类"""
    
    @abstractmethod
    async def transcribe(self, audio_file_path: str) -> str:
        """
        将音频文件转换为文本
        
        Args:
            audio_file_path: 音频文件路径
            
        Returns:
            识别出的文本
        """
        pass
    
    @abstractmethod
    def get_supported_formats(self) -> List[str]:
        """
        获取支持的音频格式
        
        Returns:
            支持的文件扩展名列表，如 [".wav", ".mp3"]
        """
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """
        获取服务提供商名称
        
        Returns:
            提供商名称，如 "minimax", "whisper"
        """
        pass
