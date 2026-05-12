"""
VAD (Voice Activity Detection) 语音活动检测模块
支持实时音频流的端点检测和断句
"""
import numpy as np
from typing import Optional, Tuple
from collections import deque

from app.utils.logger import logger


class VADDetector:
    """
    语音活动检测器
    
    功能：
    - 检测语音活动（有人说话/没人说话）
    - 端点检测（停顿超过阈值时断句）
    - 实时音频流处理
    """
    
    def __init__(
        self,
        sample_rate: int = 16000,
        frame_duration_ms: int = 30,
        threshold: float = 0.5,
        silence_duration_ms: int = 800,
        min_speech_duration_ms: int = 300
    ):
        """
        初始化 VAD 检测器
        
        Args:
            sample_rate: 采样率
            frame_duration_ms: 帧长度（毫秒）
            threshold: 语音活动阈值 (0-1)
            silence_duration_ms: 静音持续时间阈值（毫秒），超过此时间视为断句
            min_speech_duration_ms: 最小语音持续时间（毫秒）
        """
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.threshold = threshold
        self.silence_duration_ms = silence_duration_ms
        self.min_speech_duration_ms = min_speech_duration_ms
        
        # 状态
        self.is_speaking = False
        self.silence_frames = 0
        self.speech_frames = 0
        self.audio_buffer = bytearray()
        
        # 帧大小（样本数）
        self.frame_size = int(sample_rate * frame_duration_ms / 1000)
        
        # VAD 模型（可选，这里使用简单的能量检测）
        self._model = None
        
        logger.info(f"[VAD] 初始化完成: sample_rate={sample_rate}, threshold={threshold}")
    
    def _load_model(self):
        """加载 Silero VAD 模型（可选）"""
        try:
            import torch
            
            # 尝试加载 Silero VAD
            model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                trust_repo=True
            )
            self._model = model
            logger.info("[VAD] Silero VAD 模型加载成功")
        except Exception as e:
            logger.warning(f"[VAD] Silero VAD 加载失败，使用能量检测: {e}")
            self._model = None
    
    def detect_energy(self, audio_frame: np.ndarray) -> float:
        """
        计算音频帧的能量（简单 VAD）
        
        Args:
            audio_frame: 音频帧数据
            
        Returns:
            能量值 (0-1)
        """
        if len(audio_frame) == 0:
            return 0.0
        
        # 计算 RMS 能量
        rms = np.sqrt(np.mean(audio_frame.astype(np.float32) ** 2))
        
        # 归一化到 0-1
        energy = min(rms / 32768.0, 1.0)
        
        return energy
    
    def process_frame(self, audio_frame: np.ndarray) -> Tuple[bool, bool]:
        """
        处理音频帧
        
        Args:
            audio_frame: 音频帧数据 (16-bit PCM)
            
        Returns:
            (is_speech, is_endpoint)
            - is_speech: 是否有语音活动
            - is_endpoint: 是否到达端点（断句）
        """
        # 计算能量
        energy = self.detect_energy(audio_frame)
        
        # 判断是否有语音
        is_speech = energy > self.threshold
        
        is_endpoint = False
        
        if is_speech:
            # 有语音
            self.speech_frames += 1
            self.silence_frames = 0
            
            if not self.is_speaking:
                self.is_speaking = True
                logger.debug("[VAD] 语音开始")
        else:
            # 无语音
            if self.is_speaking:
                self.silence_frames += 1
                
                # 检查是否到达端点（静音超过阈值）
                silence_duration_ms = self.silence_frames * self.frame_duration_ms
                if silence_duration_ms >= self.silence_duration_ms:
                    # 检查语音持续时间是否足够
                    speech_duration_ms = self.speech_frames * self.frame_duration_ms
                    if speech_duration_ms >= self.min_speech_duration_ms:
                        is_endpoint = True
                        logger.debug(f"[VAD] 端点检测: 语音持续 {speech_duration_ms}ms")
                    
                    # 重置状态
                    self.is_speaking = False
                    self.silence_frames = 0
                    self.speech_frames = 0
        
        return is_speech, is_endpoint
    
    def process_audio_chunk(self, audio_data: bytes) -> Tuple[bool, bool, Optional[bytes]]:
        """
        处理音频数据块
        
        Args:
            audio_data: 音频数据 (16-bit PCM)
            
        Returns:
            (is_speech, is_endpoint, buffered_audio)
            - is_speech: 是否有语音活动
            - is_endpoint: 是否到达端点
            - buffered_audio: 缓冲的音频数据（端点时返回）
        """
        # 转换为 numpy 数组
        audio_frame = np.frombuffer(audio_data, dtype=np.int16)
        
        # 检测
        is_speech, is_endpoint = self.process_frame(audio_frame)
        
        # 缓冲音频
        self.audio_buffer.extend(audio_data)
        
        buffered_audio = None
        if is_endpoint:
            # 返回缓冲的音频
            buffered_audio = bytes(self.audio_buffer)
            self.audio_buffer.clear()
        
        return is_speech, is_endpoint, buffered_audio
    
    def reset(self):
        """重置状态"""
        self.is_speaking = False
        self.silence_frames = 0
        self.speech_frames = 0
        self.audio_buffer.clear()
    
    def get_state(self) -> dict:
        """获取当前状态"""
        return {
            "is_speaking": self.is_speaking,
            "silence_frames": self.silence_frames,
            "speech_frames": self.speech_frames,
            "buffer_size": len(self.audio_buffer)
        }


class VADStreamProcessor:
    """
    VAD 流式处理器
    用于 WebSocket 流式音频处理
    """
    
    def __init__(self, session_id: str):
        """
        初始化流式处理器
        
        Args:
            session_id: 会话 ID
        """
        self.session_id = session_id
        self.vad = VADDetector()
        self.audio_buffer = bytearray()
        self.is_recording = False
        self.segments = []  # 识别出的音频段
        
        logger.info(f"[VADStream] 初始化会话: {session_id}")
    
    async def process_audio_data(self, audio_data: bytes) -> dict:
        """
        处理音频数据
        
        Args:
            audio_data: 音频数据
            
        Returns:
            处理结果
        """
        result = {
            "is_speech": False,
            "is_endpoint": False,
            "segment": None,
            "buffer_size": len(self.audio_buffer)
        }
        
        # 转换为 numpy 数组
        audio_frame = np.frombuffer(audio_data, dtype=np.int16)
        
        # VAD 检测
        is_speech, is_endpoint = self.vad.process_frame(audio_frame)
        
        result["is_speech"] = is_speech
        result["is_endpoint"] = is_endpoint
        
        # 缓冲音频
        self.audio_buffer.extend(audio_data)
        
        if is_endpoint:
            # 返回完整的音频段
            segment = bytes(self.audio_buffer)
            result["segment"] = segment
            self.segments.append(segment)
            self.audio_buffer.clear()
            
            logger.info(f"[VADStream] {self.session_id} 段落完成，长度: {len(segment)}")
        
        return result
    
    async def start_recording(self):
        """开始录音"""
        self.is_recording = True
        self.audio_buffer.clear()
        self.vad.reset()
        logger.info(f"[VADStream] {self.session_id} 开始录音")
    
    async def stop_recording(self) -> Optional[bytes]:
        """停止录音，返回剩余音频"""
        self.is_recording = False
        
        # 返回缓冲的音频
        if len(self.audio_buffer) > 0:
            segment = bytes(self.audio_buffer)
            self.audio_buffer.clear()
            logger.info(f"[VADStream] {self.session_id} 停止录音，剩余音频长度: {len(segment)}")
            return segment
        
        return None
    
    def get_segments(self) -> List[bytes]:
        """获取所有识别出的音频段"""
        return self.segments.copy()
    
    def clear_segments(self):
        """清空音频段"""
        self.segments.clear()
    
    def get_state(self) -> dict:
        """获取当前状态"""
        return {
            "session_id": self.session_id,
            "is_recording": self.is_recording,
            "buffer_size": len(self.audio_buffer),
            "segments_count": len(self.segments),
            "vad_state": self.vad.get_state()
        }
