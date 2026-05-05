"""
重试和异常处理工具
支持网络超时重试、API 额度耗尽兜底、熔断保护
"""
import asyncio
import functools
import random
import time
from typing import Callable, Optional
from app.utils.logger import logger


class RetryExhaustedError(Exception):
    """重试次数耗尽错误"""
    pass


def retry(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable] = None
):
    """
    重试装饰器（指数退避 + 随机抖动）
    
    Args:
        max_retries: 最大重试次数
        delay: 初始延迟时间（秒）
        backoff_factor: 退避因子
        jitter: 是否添加随机抖动（防止惊群效应）
        exceptions: 需要重试的异常类型
        on_retry: 重试时的回调函数
        
    Usage:
        @retry(max_retries=3, exceptions=(ConnectionError, TimeoutError))
        async def fetch_data():
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        # 添加随机抖动
                        actual_delay = current_delay
                        if jitter:
                            actual_delay = current_delay * (0.5 + random.random())
                        
                        logger.warning(
                            f"[Retry] {func.__name__} 第 {attempt + 1} 次失败: {e}，"
                            f"{actual_delay:.1f}s 后重试..."
                        )
                        
                        if on_retry:
                            if asyncio.iscoroutinefunction(on_retry):
                                await on_retry(attempt + 1, e)
                            else:
                                on_retry(attempt + 1, e)
                        
                        await asyncio.sleep(actual_delay)
                        current_delay *= backoff_factor
                    else:
                        logger.error(
                            f"[Retry] {func.__name__} 重试 {max_retries} 次后仍失败: {e}"
                        )
            
            raise RetryExhaustedError(
                f"{func.__name__} 重试 {max_retries} 次后失败: {last_exception}"
            )
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        actual_delay = current_delay
                        if jitter:
                            actual_delay = current_delay * (0.5 + random.random())
                        
                        logger.warning(
                            f"[Retry] {func.__name__} 第 {attempt + 1} 次失败: {e}，"
                            f"{actual_delay:.1f}s 后重试..."
                        )
                        
                        if on_retry:
                            on_retry(attempt + 1, e)
                        
                        time.sleep(actual_delay)
                        current_delay *= backoff_factor
                    else:
                        logger.error(
                            f"[Retry] {func.__name__} 重试 {max_retries} 次后仍失败: {e}"
                        )
            
            raise RetryExhaustedError(
                f"{func.__name__} 重试 {max_retries} 次后失败: {last_exception}"
            )
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class CircuitBreaker:
    """
    熔断器（三态模型：closed → open → half-open）
    
    重要：record_failure 应只在所有重试耗尽后调用一次，
    避免与 @retry 装饰器冲突导致熔断器过早触发。
    
    Usage:
        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
        
        if not breaker.allow_request():
            raise Exception("服务熔断中")
            
        try:
            result = await call_api()
            breaker.record_success()
        except Exception as e:
            breaker.record_failure()
            raise
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        
        self._failure_count = 0
        self._last_failure_time = 0
        self._state = "closed"  # closed, open, half-open
    
    def get_state(self) -> str:
        """获取当前状态（无副作用）"""
        if self._state == "open":
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                return "half-open"
        return self._state
    
    def allow_request(self) -> bool:
        """是否允许请求"""
        state = self.get_state()
        return state in ("closed", "half-open")
    
    def record_success(self):
        """记录成功"""
        self._failure_count = 0
        self._state = "closed"
    
    def record_failure(self):
        """记录失败"""
        self._failure_count += 1
        self._last_failure_time = time.time()
        
        if self._failure_count >= self.failure_threshold:
            self._state = "open"
            logger.warning(
                f"[CircuitBreaker] 熔断器开启，失败次数: {self._failure_count}，"
                f"将在 {self.recovery_timeout}s 后尝试恢复"
            )
    
    def reset(self):
        """重置熔断器"""
        self._failure_count = 0
        self._state = "closed"
    
    @property
    def failure_count(self) -> int:
        return self._failure_count


class RateLimiter:
    """
    速率限制器（滑动窗口）
    
    Usage:
        limiter = RateLimiter(max_calls=10, period=60)
        
        async with limiter:
            result = await call_api()
    """
    
    def __init__(self, max_calls: int = 10, period: float = 60.0):
        self.max_calls = max_calls
        self.period = period
        self._calls = []
        self._lock = asyncio.Lock()
    
    async def __aenter__(self):
        async with self._lock:
            now = time.time()
            
            # 清理过期的调用记录
            self._calls = [t for t in self._calls if now - t < self.period]
            
            # 检查是否超过限制
            if len(self._calls) >= self.max_calls:
                wait_time = self.period - (now - self._calls[0])
                logger.warning(f"[RateLimiter] 达到速率限制，等待 {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                
                # 重新清理
                now = time.time()
                self._calls = [t for t in self._calls if now - t < self.period]
            
            self._calls.append(time.time())
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
