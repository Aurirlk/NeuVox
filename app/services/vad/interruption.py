"""
意图打断机制
支持用户在 TTS 播放时打断 AI
"""
import asyncio
from typing import Optional, Callable
from enum import Enum

from app.utils.logger import logger


class InterruptionState(Enum):
    """打断状态"""
    IDLE = "idle"              # 空闲
    SPEAKING = "speaking"      # AI 正在说话
    LISTENING = "listening"    # 正在监听用户输入
    INTERRUPTED = "interrupted"  # 已被打断


class InterruptionManager:
    """
    打断管理器
    
    功能：
    - 监控 TTS 播放状态
    - 检测用户语音打断
    - 触发中断信号
    """
    
    def __init__(self):
        self._state = InterruptionState.IDLE
        self._current_session_id: Optional[str] = None
        self._abort_event = asyncio.Event()
        self._interruption_callback: Optional[Callable] = None
        
        logger.info("[Interruption] 打断管理器初始化完成")
    
    @property
    def state(self) -> InterruptionState:
        """获取当前状态"""
        return self._state
    
    def set_speaking(self, session_id: str):
        """
        设置为正在说话状态
        
        Args:
            session_id: 当前会话 ID
        """
        self._state = InterruptionState.SPEAKING
        self._current_session_id = session_id
        self._abort_event.clear()
        logger.debug(f"[Interruption] 设置状态为 SPEAKING: {session_id}")
    
    def set_listening(self):
        """设置为正在监听状态"""
        self._state = InterruptionState.LISTENING
        logger.debug("[Interruption] 设置状态为 LISTENING")
    
    def set_idle(self):
        """设置为空闲状态"""
        self._state = InterruptionState.IDLE
        self._current_session_id = None
        logger.debug("[Interruption] 设置状态为 IDLE")
    
    def interrupt(self, session_id: str) -> bool:
        """
        触发打断
        
        Args:
            session_id: 触发打断的会话 ID
            
        Returns:
            是否成功打断
        """
        if self._state == InterruptionState.SPEAKING:
            if self._current_session_id == session_id or self._current_session_id is None:
                self._state = InterruptionState.INTERRUPTED
                self._abort_event.set()
                logger.info(f"[Interruption] 触发打断: {session_id}")
                return True
        
        return False
    
    def should_abort(self) -> bool:
        """检查是否应该中止当前操作"""
        return self._abort_event.is_set()
    
    def clear_abort(self):
        """清除中止信号"""
        self._abort_event.clear()
    
    def get_state(self) -> dict:
        """获取当前状态"""
        return {
            "state": self._state.value,
            "session_id": self._current_session_id,
            "should_abort": self.should_abort()
        }


class InterruptionHandler:
    """
    打断处理器
    集成到 WebSocket 处理流程中
    """
    
    def __init__(self):
        self.managers: Dict[str, InterruptionManager] = {}
    
    def get_manager(self, session_id: str) -> InterruptionManager:
        """获取会话的打断管理器"""
        if session_id not in self.managers:
            self.managers[session_id] = InterruptionManager()
        return self.managers[session_id]
    
    def remove_manager(self, session_id: str):
        """移除会话的打断管理器"""
        if session_id in self.managers:
            del self.managers[session_id]
    
    def check_interruption(self, session_id: str, is_speech: bool) -> bool:
        """
        检查是否触发打断
        
        Args:
            session_id: 会话 ID
            is_speech: 是否检测到语音
            
        Returns:
            是否触发打断
        """
        manager = self.get_manager(session_id)
        
        if is_speech and manager.state == InterruptionState.SPEAKING:
            return manager.interrupt(session_id)
        
        return False


# 全局打断处理器
interruption_handler = InterruptionHandler()
