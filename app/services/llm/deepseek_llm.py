"""
DeepSeek LLM 大语言模型实现
支持 deepseek-v4-flash, deepseek-v4-pro
"""
import time
import httpx
from typing import List, Dict, Optional, AsyncGenerator, Tuple
from app.utils.config_loader import config
from app.services.base.llm_base import LLMBase
from app.utils.logger import logger
from app.utils.retry import retry, CircuitBreaker, RetryExhaustedError


class DeepSeekLLM(LLMBase):
    """DeepSeek 大语言模型服务"""
    
    # 类级别熔断器（所有实例共享）
    _circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
    
    def __init__(self):
        llm_config = config.get_llm_config("DeepSeekLLM")
        self.api_key = llm_config.get("api_key")
        self.api_url = llm_config.get("url", "https://api.deepseek.com/v1/chat/completions")
        self.model = llm_config.get("model_name", "deepseek-v4-flash")
        self.temperature = llm_config.get("temperature", 0.7)
        self.max_tokens = llm_config.get("max_tokens", 2048)
        
        self.system_prompt = """你是一个友好、专业的智能语音助手。请用简洁自然的中文回答用户的问题。
回复要口语化，适合语音播报，避免使用Markdown格式和特殊符号。"""
        
    @retry(max_retries=3, delay=1.0, backoff_factor=2.0, 
           exceptions=(httpx.TimeoutException, httpx.ConnectError))
    async def chat(
        self, 
        user_message: str, 
        history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        与大模型进行对话
        
        重试策略：网络错误自动重试 3 次
        熔断策略：重试全部失败后才记录一次失败
        """
        content, _ = await self._chat_with_usage(user_message, history)
        return content
    
    async def chat_with_usage(
        self, 
        user_message: str, 
        history: Optional[List[Dict[str, str]]] = None
    ) -> Tuple[str, Dict]:
        """
        与大模型进行对话，返回回复内容和 token 用量
        
        Returns:
            (reply_text, usage_dict) 元组
        """
        return await self._chat_with_usage(user_message, history)
    
    async def _chat_with_usage(
        self, 
        user_message: str, 
        history: Optional[List[Dict[str, str]]] = None
    ) -> Tuple[str, Dict]:
        """与大模型进行对话（返回 token 用量）"""
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY 未配置")
        
        if not self._circuit_breaker.allow_request():
            raise Exception("DeepSeek API 熔断器开启，暂时不可用")
            
        messages = self._build_messages(user_message, history)
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
                        "messages": messages,
                        "temperature": self.temperature,
                        "max_tokens": self.max_tokens,
                    }
                )
                
            if response.status_code != 200:
                error_msg = f"DeepSeek API 调用失败: {response.status_code} - {response.text}"
                logger.error(f"[LLM] {error_msg}")
                raise Exception(error_msg)
                
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
            # 获取 token 用量
            usage = result.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            
            # 成功时记录熔断器成功
            self._circuit_breaker.record_success()
            latency = (time.time() - start_time) * 1000
            logger.info(
                f"[LLM] DeepSeek 调用成功，耗时: {latency:.0f}ms，"
                f"tokens: {prompt_tokens}+{completion_tokens}"
            )
            
            return content, {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "latency_ms": latency
            }
            
        except httpx.TimeoutException:
            # 网络超时 - 由 @retry 处理重试
            raise
        except httpx.ConnectError:
            # 连接错误 - 由 @retry 处理重试
            raise
        except ValueError:
            # API Key 未配置 - 不重试
            raise
        except RetryExhaustedError:
            # 重试全部失败 - 记录熔断器失败
            self._circuit_breaker.record_failure()
            raise
        except Exception as e:
            # 其他错误 - 记录日志和熔断器
            logger.error(f"[LLM] DeepSeek 对话失败: {str(e)}")
            self._circuit_breaker.record_failure()
            raise
    
    @retry(max_retries=3, delay=1.0, backoff_factor=2.0,
           exceptions=(httpx.TimeoutException, httpx.ConnectError))
    async def chat_stream(
        self, 
        user_message: str, 
        history: Optional[List[Dict[str, str]]] = None
    ) -> AsyncGenerator[str, None]:
        """
        与大模型进行流式对话
        
        重试策略：网络错误自动重试 3 次
        """
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY 未配置")
        
        if not self._circuit_breaker.allow_request():
            raise Exception("DeepSeek API 熔断器开启，暂时不可用")
            
        messages = self._build_messages(user_message, history)
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream(
                    "POST",
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": self.temperature,
                        "max_tokens": self.max_tokens,
                        "stream": True
                    }
                ) as response:
                    if response.status_code != 200:
                        raise Exception(f"DeepSeek API 调用失败: {response.status_code}")
                        
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data.strip() == "[DONE]":
                                break
                            try:
                                import json
                                chunk = json.loads(data)
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                continue
            
            # 记录成功
            self._circuit_breaker.record_success()
            latency = (time.time() - start_time) * 1000
            logger.info(f"[LLM] DeepSeek 流式调用完成，耗时: {latency:.0f}ms")
                                
        except httpx.TimeoutException:
            # 网络超时 - 由 @retry 处理重试
            raise
        except httpx.ConnectError:
            # 连接错误 - 由 @retry 处理重试
            raise
        except RetryExhaustedError:
            self._circuit_breaker.record_failure()
            raise
        except Exception as e:
            if "熔断器开启" not in str(e):
                self._circuit_breaker.record_failure()
            raise
    
    def _build_messages(
        self, 
        user_message: str, 
        history: Optional[List[Dict[str, str]]] = None
    ) -> List[Dict[str, str]]:
        """构建消息列表"""
        messages = [{"role": "system", "content": self.system_prompt}]
        
        if history:
            messages.extend(history)
            
        messages.append({"role": "user", "content": user_message})
        return messages
    
    def get_model_name(self) -> str:
        """获取模型名称"""
        return self.model
    
    def get_provider_name(self) -> str:
        """获取服务提供商名称"""
        return "deepseek"
