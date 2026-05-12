"""
MiniMax TTS 语音合成实现（备份）
使用 MiniMax Speech-01 模型
"""
import os
import uuid
import httpx
from typing import List, Dict, Optional, AsyncGenerator
from app.utils.config_loader import config
from app.services.base.tts_base import TTSBase


class MiniMaxTTS(TTSBase):
    """MiniMax 语音合成服务（备份）"""
    
    def __init__(self):
        tts_config = config.get_tts_config("MiniMaxTTS")
        self.api_key = tts_config.get("api_key")
        self.api_url = tts_config.get("url", "https://api.minimax.chat/v1/t2a_v2")
        self.model = tts_config.get("model", "speech-01")
        self.output_dir = tts_config.get("output_dir", "outputs")
        
    async def synthesize(
        self, 
        text: str, 
        voice: Optional[str] = None,
        speed: Optional[float] = None
    ) -> str:
        """
        将文本转换为语音
        
        Args:
            text: 要转换的文本
            voice: 音色选择（可选）
            speed: 语速控制（可选）
            
        Returns:
            生成的音频文件路径
        """
        if not self.api_key:
            raise ValueError("MINIMAX_API_KEY 未配置")
            
        if not text or not text.strip():
            raise ValueError("文本内容不能为空")
            
        voice = voice or settings.TTS_VOICE
        speed = speed or settings.TTS_SPEED
        
        output_filename = f"tts_{uuid.uuid4().hex[:8]}.wav"
        output_path = os.path.join(self.output_dir, output_filename)
        
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
                raise Exception(f"MiniMax TTS API 调用失败: {response.text}")
                
            result = response.json()
            return await self._save_audio(result, output_path, client)
            
        except httpx.TimeoutException:
            raise Exception("MiniMax TTS API 请求超时")
        except Exception as e:
            raise Exception(f"MiniMax 语音合成失败: {str(e)}")
    
    async def synthesize_stream(
        self, 
        text: str, 
        voice: Optional[str] = None,
        speed: Optional[float] = None
    ) -> AsyncGenerator[bytes, None]:
        """
        流式语音合成
        
        Args:
            text: 要转换的文本
            voice: 音色选择（可选）
            speed: 语速控制（可选）
            
        Yields:
            音频数据块 (bytes)
        """
        if not self.api_key:
            raise ValueError("MINIMAX_API_KEY 未配置")
            
        voice = voice or settings.TTS_VOICE
        speed = speed or settings.TTS_SPEED
        
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
                raise Exception(f"MiniMax TTS API 调用失败: {response.text}")
                
            async for chunk in response.aiter_bytes():
                yield chunk
                
        except httpx.TimeoutException:
            raise Exception("MiniMax TTS API 请求超时")
        except Exception as e:
            raise Exception(f"MiniMax 流式语音合成失败: {str(e)}")
    
    async def _save_audio(self, result: dict, output_path: str, client: httpx.AsyncClient) -> str:
        """保存音频文件"""
        audio_data = result.get("data", {})
        audio_url = audio_data.get("audio")
        
        if audio_url:
            audio_response = await client.get(audio_url)
            with open(output_path, "wb") as f:
                f.write(audio_response.content)
        else:
            import base64
            audio_hex = audio_data.get("audio_hex", "")
            if audio_hex:
                audio_bytes = bytes.fromhex(audio_hex)
                with open(output_path, "wb") as f:
                    f.write(audio_bytes)
            else:
                raise Exception("TTS API 返回数据中未找到音频内容")
                
        return output_path
    
    async def get_voices(self) -> List[Dict[str, str]]:
        """获取可用音色列表"""
        return [
            {"id": "male-qn-qingse", "name": "青涩青年"},
            {"id": "male-qn-jingying", "name": "精英青年"},
            {"id": "male-qn-badao", "name": "霸道青年"},
            {"id": "female-shaonv", "name": "少女"},
            {"id": "female-yujie", "name": "御姐"},
            {"id": "presenter_male", "name": "男主持人"},
            {"id": "presenter_female", "name": "女主持人"},
        ]
    
    def get_provider_name(self) -> str:
        """获取服务提供商名称"""
        return "minimax"
