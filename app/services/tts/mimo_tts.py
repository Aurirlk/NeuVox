"""
MiMo TTS 语音合成实现
使用 MiMo 2.5 TTS 模型
"""
import os
import time
import uuid
import httpx
import aiofiles
from typing import List, Dict, Optional, AsyncGenerator
from app.config import settings
from app.services.base.tts_base import TTSBase
from app.utils.logger import logger
from app.utils.retry import retry, CircuitBreaker, RetryExhaustedError


class MiMoTTS(TTSBase):
    """MiMo 语音合成服务"""
    
    # 类级别熔断器
    _circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
    
    def __init__(self):
        self.api_key = settings.MIMO_TTS_API_KEY
        self.api_url = settings.MIMO_TTS_API_URL
        self.model = settings.MIMO_TTS_MODEL
        self.output_dir = settings.OUTPUT_DIR
        
    async def synthesize(
        self, 
        text: str, 
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        emotion: Optional[str] = None
    ) -> str:
        """
        将文本转换为语音
        
        Args:
            text: 要转换的文本
            voice: 音色选择（可选）
            speed: 语速控制（可选）
            emotion: 情感风格（可选）: cheerful/sad/angry/surprised等
            
        Returns:
            生成的音频文件路径
        """
        if not self.api_key:
            raise ValueError("MIMO_TTS_API_KEY 未配置")
            
        if not text or not text.strip():
            raise ValueError("文本内容不能为空")
        
        if not self._circuit_breaker.allow_request():
            raise Exception("MiMo TTS API 熔断器开启，暂时不可用")
            
        voice = voice or settings.TTS_VOICE
        speed = speed or settings.TTS_SPEED
        
        # 如果指定了情绪，调整语速
        if emotion:
            from app.services.emotion.analyzer import emotion_analyzer
            tts_params = emotion_analyzer.get_tts_params(emotion)
            speed = tts_params.get("speed", speed)
            logger.info(f"[TTS] 使用情绪风格: {emotion}, 语速: {speed}")
        
        output_filename = f"tts_{uuid.uuid4().hex[:8]}.wav"
        output_path = os.path.join(self.output_dir, output_filename)
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "text": text,
                        "voice_setting": {
                            "voice_id": voice,
                            "speed": speed
                        },
                        "audio_setting": {
                            "sample_rate": 32000,
                            "bitrate": 128000,
                            "format": "wav"
                        }
                    }
                )
                
            if response.status_code != 200:
                error_msg = f"MiMo TTS API 调用失败: {response.status_code} - {response.text}"
                logger.error(f"[TTS] {error_msg}")
                raise Exception(error_msg)
                
            result = response.json()
            audio_path = await self._save_audio(result, output_path)
            
            # 成功时记录熔断器成功
            self._circuit_breaker.record_success()
            latency = (time.time() - start_time) * 1000
            logger.info(f"[TTS] MiMo 合成成功，耗时: {latency:.0f}ms，文件: {audio_path}")
            
            return audio_path
            
        except httpx.TimeoutException:
            # 网络超时 - 由 @retry 处理重试
            raise
        except httpx.ConnectError:
            # 连接错误 - 由 @retry 处理重试
            raise
        except ValueError:
            # 参数错误 - 不重试
            raise
        except Exception as e:
            # 其他错误
            logger.error(f"[TTS] MiMo 语音合成失败: {str(e)}")
            raise
    
    async def _synthesize_with_retry(
        self, 
        text: str, 
        voice: Optional[str] = None,
        speed: Optional[float] = None
    ) -> str:
        """带重试的合成方法"""
        try:
            return await self.synthesize(text, voice, speed)
        except RetryExhaustedError as e:
            # 重试全部失败 - 记录熔断器失败
            self._circuit_breaker.record_failure()
            raise Exception(f"MiMo TTS 合成失败: {str(e)}")
        except Exception as e:
            # 其他异常 - 记录熔断器失败
            if "熔断器开启" not in str(e):
                self._circuit_breaker.record_failure()
            raise
    
    async def _save_audio(self, result: dict, output_path: str) -> str:
        """保存音频文件（异步）"""
        audio_data = result.get("data", {})
        audio_url = audio_data.get("audio")
        
        if audio_url:
            async with httpx.AsyncClient() as client:
                audio_response = await client.get(audio_url)
                async with aiofiles.open(output_path, "wb") as f:
                    await f.write(audio_response.content)
        else:
            audio_hex = audio_data.get("audio_hex", "")
            if audio_hex:
                audio_bytes = bytes.fromhex(audio_hex)
                async with aiofiles.open(output_path, "wb") as f:
                    await f.write(audio_bytes)
            else:
                raise Exception("TTS API 返回数据中未找到音频内容")
                
        return output_path
    
    async def synthesize_stream(
        self, 
        text: str, 
        voice: Optional[str] = None,
        speed: Optional[float] = None
    ) -> AsyncGenerator[bytes, None]:
        """
        流式语音合成
        """
        if not self.api_key:
            raise ValueError("MIMO_TTS_API_KEY 未配置")
        
        if not self._circuit_breaker.allow_request():
            raise Exception("MiMo TTS API 熔断器开启，暂时不可用")
            
        voice = voice or settings.TTS_VOICE
        speed = speed or settings.TTS_SPEED
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "text": text,
                        "voice_setting": {
                            "voice_id": voice,
                            "speed": speed
                        },
                        "audio_setting": {
                            "sample_rate": 32000,
                            "bitrate": 128000,
                            "format": "wav"
                        },
                        "stream": True
                    }
                )
                
            if response.status_code != 200:
                self._circuit_breaker.record_failure()
                raise Exception(f"MiMo TTS API 调用失败: {response.status_code}")
                
            async for chunk in response.aiter_bytes():
                yield chunk
            
            # 记录成功
            self._circuit_breaker.record_success()
            latency = (time.time() - start_time) * 1000
            logger.info(f"[TTS] MiMo 流式合成完成，耗时: {latency:.0f}ms")
                
        except httpx.TimeoutException:
            self._circuit_breaker.record_failure()
            raise Exception("MiMo TTS API 请求超时")
        except Exception as e:
            if "熔断器开启" not in str(e):
                self._circuit_breaker.record_failure()
            raise Exception(f"MiMo 流式语音合成失败: {str(e)}")
    
    async def get_voices(self) -> List[Dict[str, str]]:
        """获取可用音色列表"""
        return [
            {"id": "mimo-v2.5-tts", "name": "MiMo 标准语音"},
            {"id": "mimo-v2.5-tts-voiceclone", "name": "MiMo 声音克隆"},
            {"id": "mimo-v2.5-tts-voicedesign", "name": "MiMo 声音设计"},
        ]
    
    def get_provider_name(self) -> str:
        """获取服务提供商名称"""
        return "mimo"
