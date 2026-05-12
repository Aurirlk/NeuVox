"""
FunASR 语音识别实现
使用阿里达摩院的 FunASR 免费本地模型
"""
import os
from typing import List
from app.services.base.asr_base import ASRBase
from app.utils.logger import logger
from app.utils.retry import retry, CircuitBreaker, RetryExhaustedError


class FunASR(ASRBase):
    """FunASR 语音识别服务（免费本地模型）"""
    
    # 类级别熔断器
    _circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
    _model = None
    
    def __init__(self):
        self.model_id = "paraformer-zh"
        
    def _get_model(self):
        """懒加载模型"""
        if FunASR._model is None:
            try:
                from funasr import AutoModel
                FunASR._model = AutoModel(
                    model=self.model_id,
                    vad_model="fsmn-vad",
                    punc_model="ct-punc",
                    device="cpu"
                )
                logger.info("[FunASR] 模型加载完成")
            except Exception as e:
                logger.error(f"[FunASR] 模型加载失败: {e}")
                raise
        return FunASR._model
    
    @retry(max_retries=2, delay=1.0, backoff_factor=2.0,
           exceptions=(Exception,))
    async def transcribe(self, audio_file_path: str) -> str:
        """
        将音频文件转换为文本
        
        FunASR 是本地模型，无需 API Key
        """
        if not os.path.exists(audio_file_path):
            raise FileNotFoundError(f"音频文件不存在: {audio_file_path}")
        
        if not self._circuit_breaker.allow_request():
            raise Exception("FunASR 熔断器开启，暂时不可用")
            
        try:
            model = self._get_model()
            result = model.generate(input=audio_file_path)
            
            self._circuit_breaker.record_success()
            
            # 提取识别结果
            text = ""
            if result and len(result) > 0:
                text = result[0].get("text", "")
            
            logger.info(f"[FunASR] 识别成功，文本长度: {len(text)}")
            return text
                
        except Exception as e:
            logger.error(f"[FunASR] 语音识别失败: {str(e)}")
            self._circuit_breaker.record_failure()
            raise
    
    def get_supported_formats(self) -> List[str]:
        return [".wav", ".mp3", ".m4a", ".ogg", ".flac"]
    
    def get_provider_name(self) -> str:
        return "funasr"
