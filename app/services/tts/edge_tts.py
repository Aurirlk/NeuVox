"""
EdgeTTS 语音合成实现
使用微软 Edge TTS 免费服务
"""
import os
import tempfile
import edge_tts
from typing import List, Dict, Optional, AsyncGenerator
from app.utils.config_loader import config
from app.services.base.tts_base import TTSBase
from app.utils.logger import logger
from app.utils.retry import retry, CircuitBreaker, RetryExhaustedError


class EdgeTTS(TTSBase):
    """Edge TTS 语音合成服务（免费）"""
    
    # 类级别熔断器
    _circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
    
    def __init__(self):
        tts_config = config.get_tts_config("EdgeTTS")
        self.voice = tts_config.get("voice", "zh-CN-XiaoxiaoNeural")
        self.output_dir = tts_config.get("output_dir", "outputs")
        os.makedirs(self.output_dir, exist_ok=True)
        
    @retry(max_retries=3, delay=1.0, backoff_factor=2.0,
           exceptions=(Exception,))
    async def synthesize(
        self, 
        text: str, 
        voice: Optional[str] = None,
        speed: Optional[float] = None
    ) -> str:
        """
        将文本转换为语音
        """
        if not text or not text.strip():
            raise ValueError("文本不能为空")
        
        if not self._circuit_breaker.allow_request():
            raise Exception("EdgeTTS 熔断器开启，暂时不可用")
            
        voice = voice or self.voice
        
        try:
            # 生成临时文件
            temp_file = tempfile.NamedTemporaryFile(
                delete=False, 
                suffix=".mp3",
                dir=self.output_dir
            )
            output_path = temp_file.name
            temp_file.close()
            
            # 使用 edge-tts 生成语音
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(output_path)
            
            self._circuit_breaker.record_success()
            logger.info(f"[EdgeTTS] 合成成功: {output_path}")
            return output_path
                
        except Exception as e:
            logger.error(f"[EdgeTTS] 语音合成失败: {str(e)}")
            self._circuit_breaker.record_failure()
            raise
    
    @retry(max_retries=3, delay=1.0, backoff_factor=2.0,
           exceptions=(Exception,))
    async def synthesize_stream(
        self, 
        text: str, 
        voice: Optional[str] = None,
        speed: Optional[float] = None
    ) -> AsyncGenerator[bytes, None]:
        """
        流式语音合成
        """
        if not text or not text.strip():
            raise ValueError("文本不能为空")
        
        if not self._circuit_breaker.allow_request():
            raise Exception("EdgeTTS 熔断器开启，暂时不可用")
            
        voice = voice or self.voice
        
        try:
            communicate = edge_tts.Communicate(text, voice)
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    yield chunk["data"]
            
            self._circuit_breaker.record_success()
                
        except Exception as e:
            logger.error(f"[EdgeTTS] 流式合成失败: {str(e)}")
            self._circuit_breaker.record_failure()
            raise
    
    async def get_voices(self) -> List[Dict[str, str]]:
        """获取可用音色列表"""
        voices = await edge_tts.list_voices()
        # 过滤中文音色
        zh_voices = [
            {"id": v["ShortName"], "name": v["FriendlyName"]}
            for v in voices
            if v["Locale"].startswith("zh-")
        ]
        return zh_voices
    
    def get_provider_name(self) -> str:
        return "edge"
