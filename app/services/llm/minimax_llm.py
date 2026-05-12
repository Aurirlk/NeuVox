"""
MiniMax LLM 大语言模型实现（备份）
"""
import httpx
from typing import List, Dict, Optional, AsyncGenerator
from app.utils.config_loader import config
from app.services.base.llm_base import LLMBase


class MiniMaxLLM(LLMBase):
    """MiniMax 大语言模型服务（备份）"""
    
    def __init__(self):
        llm_config = config.get_llm_config("MiniMaxLLM")
        self.api_key = llm_config.get("api_key")
        self.api_url = llm_config.get("url", "https://api.minimax.chat/v1/text/chatcompletion_v2")
        self.model = llm_config.get("model_name", "MiniMax-Text-01")
        self.group_id = llm_config.get("group_id")
        
        self.system_prompt = """你是一个友好、专业的智能语音助手。请用简洁自然的中文回答用户的问题。
回复要口语化，适合语音播报，避免使用Markdown格式和特殊符号。"""
        
    async def chat(
        self, 
        user_message: str, 
        history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        与大模型进行对话
        
        Args:
            user_message: 用户消息
            history: 对话历史
            
        Returns:
            模型回复文本
        """
        if not self.api_key:
            raise ValueError("MINIMAX_API_KEY 未配置")
            
        messages = self._build_messages(user_message, history)
        
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
                        "temperature": settings.LLM_TEMPERATURE,
                        "max_tokens": settings.LLM_MAX_TOKENS,
                        "group_id": self.group_id,
                        "stream": False
                    }
                )
                
            if response.status_code != 200:
                raise Exception(f"MiniMax API 调用失败: {response.text}")
                
            result = response.json()
            return result["choices"][0]["message"]["content"]
            
        except httpx.TimeoutException:
            raise Exception("MiniMax API 请求超时")
        except Exception as e:
            raise Exception(f"MiniMax 对话失败: {str(e)}")
    
    async def chat_stream(
        self, 
        user_message: str, 
        history: Optional[List[Dict[str, str]]] = None
    ) -> AsyncGenerator[str, None]:
        """
        与大模型进行流式对话
        
        Args:
            user_message: 用户消息
            history: 对话历史
            
        Yields:
            模型回复的文本片段
        """
        if not self.api_key:
            raise ValueError("MINIMAX_API_KEY 未配置")
            
        messages = self._build_messages(user_message, history)
        
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
                        "temperature": settings.LLM_TEMPERATURE,
                        "max_tokens": settings.LLM_MAX_TOKENS,
                        "group_id": self.group_id,
                        "stream": True
                    }
                ) as response:
                    if response.status_code != 200:
                        raise Exception(f"MiniMax API 调用失败")
                        
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
                                
        except httpx.TimeoutException:
            raise Exception("MiniMax API 请求超时")
        except Exception as e:
            raise Exception(f"MiniMax 流式对话失败: {str(e)}")
    
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
        return "minimax"
