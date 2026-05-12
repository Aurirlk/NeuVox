"""
MiMo ASR 语音识别实现
使用 MiMo 模型进行语音识别
"""
import os
import httpx
from typing import List
from app.utils.config_loader import config
from app.services.base.asr_base import ASRBase
from app.utils.logger import logger
from app.utils.retry import retry, CircuitBreaker, RetryExhaustedError


class MiMoASR(ASRBase):
    """MiMo 语音识别服务"""
    
    # 类级别熔断器
    _circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
    
    def __init__(self):
        asr_config = config.get_asr_config("MiMoASR")
        self.api_key = asr_config.get("api_key")
        self.api_url = asr_config.get("url", "https://api.minimax.chat/v1/audio/speech_to_text")
        self.model = asr_config.get("model", "mimo-v2.5")
        
    @retry(max_retries=3, delay=1.0, backoff_factor=2.0,
           exceptions=(httpx.TimeoutException, httpx.ConnectError))
    async def transcribe(self, audio_file_path: str) -> str:
        """
        将音频文件转换为文本
        
        重试策略：网络错误自动重试 3 次
        熔断策略：重试全部失败后才记录一次失败
        """
        if not self.api_key:
            raise ValueError("MIMO_TTS_API_KEY 未配置")
            
        if not os.path.exists(audio_file_path):
            raise FileNotFoundError(f"音频文件不存在: {audio_file_path}")
        
        if not self._circuit_breaker.allow_request():
            raise Exception("MiMo ASR 熔断器开启，暂时不可用")
            
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                with open(audio_file_path, "rb") as f:
                    files = {"file": (os.path.basename(audio_file_path), f, "audio/wav")}
                    data = {
                        "model": self.model,
                        "language": "zh-CN"
                    }
                    
                    response = await client.post(
                        self.api_url,
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        files=files,
                        data=data
                    )
                    
                if response.status_code != 200:
                    error_msg = f"ASR API 调用失败: {response.status_code} - {response.text}"
                    logger.error(f"[ASR] {error_msg}")
                    raise Exception(error_msg)
                    
                result = response.json()
                
                # 成功时记录熔断器成功
                self._circuit_breaker.record_success()
                text = result.get("text", "")
                logger.info(f"[ASR] MiMo 识别成功，文本长度: {len(text)}")
                return text
                
        except httpx.TimeoutException:
            raise
        except httpx.ConnectError:
            raise
        except ValueError:
            raise
        except FileNotFoundError:
            raise
        except RetryExhaustedError:
            self._circuit_breaker.record_failure()
            raise
        except Exception as e:
            logger.error(f"[ASR] 语音识别失败: {str(e)}")
            self._circuit_breaker.record_failure()
            raise
    
    def get_supported_formats(self) -> List[str]:
        """获取支持的音频格式"""
        return [".wav", ".mp3", ".m4a", ".ogg"]
    
    def get_provider_name(self) -> str:
        """获取服务提供商名称"""
        return "mimo"
