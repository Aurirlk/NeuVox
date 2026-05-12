"""
摄像头流分析器
支持实时视频帧处理和分析
"""
import base64
import io
from typing import Optional, Dict, Any, AsyncGenerator
from datetime import datetime

from app.utils.logger import logger


class CameraAnalyzer:
    """
    摄像头流分析器
    
    功能：
    - 接收视频帧（Base64 编码）
    - 使用 VLLM 分析画面内容
    - 支持主动观察和被动监听模式
    """
    
    def __init__(self, vllm_provider: str = "qwen"):
        """
        初始化摄像头分析器
        
        Args:
            vllm_provider: VLLM 提供商
        """
        self.vllm_provider = vllm_provider
        self._vllm_client = None
        self._last_analysis = None
        self._analysis_cache = {}
        
        logger.info(f"[CameraAnalyzer] 初始化完成: provider={vllm_provider}")
    
    def _get_vllm_client(self):
        """获取 VLLM 客户端"""
        if self._vllm_client is None:
            try:
                from app.services.vllm.vllm_client import VLLMClient
                self._vllm_client = VLLMClient(provider=self.vllm_provider)
            except Exception as e:
                logger.error(f"[CameraAnalyzer] VLLM 客户端初始化失败: {e}")
                raise
        return self._vllm_client
    
    async def analyze_frame(
        self, 
        frame_data: str,
        prompt: str = "请描述这个画面中的内容",
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        分析单帧画面
        
        Args:
            frame_data: Base64 编码的图片数据
            prompt: 分析提示词
            use_cache: 是否使用缓存
            
        Returns:
            分析结果
        """
        try:
            # 检查缓存（简单的时间戳去重）
            cache_key = f"{frame_data[:50]}_{prompt}"
            if use_cache and cache_key in self._analysis_cache:
                cache_time = self._analysis_cache[cache_key]
                if time.time() - cache_time < 2.0:  # 2秒内的相同请求使用缓存
                    return {"cached": True, "description": "近期已分析"}
            
            # 保存临时图片文件
            temp_path = f"outputs/frame_{uuid.uuid4().hex[:8]}.jpg"
            
            # 解码 Base64
            image_data = base64.b64decode(frame_data)
            with open(temp_path, "wb") as f:
                f.write(image_data)
            
            # 使用 VLLM 分析
            vllm_client = self._get_vllm_client()
            description = await vllm_client.understand_image(temp_path, prompt)
            
            # 清理临时文件
            os.remove(temp_path)
            
            # 更新缓存
            self._analysis_cache[cache_key] = time.time()
            
            result = {
                "description": description,
                "timestamp": datetime.now().isoformat(),
                "cached": False
            }
            
            self._last_analysis = result
            return result
            
        except Exception as e:
            logger.error(f"[CameraAnalyzer] 帧分析失败: {e}")
            return {
                "error": str(e),
                "description": "分析失败",
                "timestamp": datetime.now().isoformat()
            }
    
    async def analyze_stream(
        self, 
        frame_generator: AsyncGenerator[str, None],
        prompt: str = "请描述这个画面中的内容",
        interval: float = 1.0
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式分析视频帧
        
        Args:
            frame_generator: 帧数据生成器
            prompt: 分析提示词
            interval: 分析间隔（秒）
            
        Yields:
            分析结果
        """
        last_analysis_time = 0
        
        async for frame_data in frame_generator:
            current_time = time.time()
            
            # 控制分析频率
            if current_time - last_analysis_time < interval:
                continue
            
            result = await self.analyze_frame(frame_data, prompt)
            last_analysis_time = current_time
            
            yield result
    
    async def observe(
        self, 
        frame_data: str,
        context: str = ""
    ) -> Dict[str, Any]:
        """
        主动观察模式 - 结合上下文分析画面
        
        Args:
            frame_data: Base64 编码的图片数据
            context: 上下文信息（如当前对话内容）
            
        Returns:
            观察结果
        """
        prompt = "请仔细观察这个画面，描述其中的物体、人物、场景等信息"
        if context:
            prompt += f"。结合上下文：{context}"
        
        result = await self.analyze_frame(frame_data, prompt)
        
        # 添加观察标签
        result["mode"] = "observe"
        return result
    
    async def answer_question(
        self, 
        frame_data: str,
        question: str
    ) -> Dict[str, Any]:
        """
        回答关于画面的问题
        
        Args:
            frame_data: Base64 编码的图片数据
            question: 用户问题
            
        Returns:
            回答结果
        """
        prompt = f"请根据这个画面回答问题：{question}"
        
        result = await self.analyze_frame(frame_data, prompt)
        result["mode"] = "question"
        result["question"] = question
        
        return result
    
    def get_last_analysis(self) -> Optional[Dict[str, Any]]:
        """获取最近一次分析结果"""
        return self._last_analysis
    
    def clear_cache(self):
        """清空分析缓存"""
        self._analysis_cache.clear()


# 全局摄像头分析器实例
camera_analyzer = CameraAnalyzer()
