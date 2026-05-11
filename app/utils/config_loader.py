"""
配置加载器
统一加载 YAML 配置文件和环境变量
支持 xiaozhi-esp32-server 风格的配置格式
"""
import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

from app.utils.logger import logger

# 加载 .env 文件
load_dotenv()


class ConfigLoader:
    """
    配置加载器
    
    支持两种配置格式：
    1. 统一配置文件: configs/.config.yaml
    2. 分离配置文件: configs/*.yaml
    
    优先级：环境变量 > YAML 配置文件 > 默认值
    """
    
    _instance = None
    _config: Dict[str, Any] = {}
    _selected_modules: Dict[str, str] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_all_configs()
        return cls._instance
    
    def _load_all_configs(self):
        """加载所有配置文件"""
        configs_dir = Path("configs")
        
        if not configs_dir.exists():
            logger.warning("[Config] configs/ 目录不存在")
            return
        
        # 优先加载统一配置文件
        unified_config = configs_dir / ".config.yaml"
        if unified_config.exists():
            try:
                with open(unified_config, "r", encoding="utf-8") as f:
                    self._config = yaml.safe_load(f) or {}
                self._selected_modules = self._config.get("selected_module", {})
                logger.info("[Config] 加载统一配置: .config.yaml")
            except Exception as e:
                logger.error(f"[Config] 加载统一配置失败: {e}")
        
        # 加载其他配置文件作为补充
        for yaml_file in configs_dir.glob("*.yaml"):
            if yaml_file.name == ".config.yaml":
                continue
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if data:
                        # 合并到主配置
                        for key, value in data.items():
                            if key not in self._config:
                                self._config[key] = value
                        logger.info(f"[Config] 加载补充配置: {yaml_file.name}")
            except Exception as e:
                logger.error(f"[Config] 加载配置失败 {yaml_file.name}: {e}")
    
    def get(self, *keys, default: Any = None) -> Any:
        """
        获取配置值（支持嵌套键）
        
        用法：
            config.get("LLM", "DeepSeekLLM", "api_key")
            config.get("selected_module", "LLM")
        """
        value = self._config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
        return value if value is not None else default
    
    def resolve_env_vars(self, value: Any) -> Any:
        """
        解析环境变量引用 ${VAR}
        """
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_var = value[2:-1]
            return os.getenv(env_var, value)
        return value
    
    def get_resolved(self, *keys, default: Any = None) -> Any:
        """获取配置值并解析环境变量"""
        value = self.get(*keys, default=default)
        return self.resolve_env_vars(value)
    
    # ==================== 模块选择 ====================
    
    def get_selected_module(self, module_type: str) -> Optional[str]:
        """获取选中的模块名称"""
        return self._selected_modules.get(module_type)
    
    def get_asr_provider(self) -> str:
        """获取 ASR 提供商"""
        return self.get_selected_module("ASR") or "MiniMaxASR"
    
    def get_llm_provider(self) -> str:
        """获取 LLM 提供商"""
        return self.get_selected_module("LLM") or "DeepSeekLLM"
    
    def get_tts_provider(self) -> str:
        """获取 TTS 提供商"""
        return self.get_selected_module("TTS") or "MiMoTTS"
    
    # ==================== LLM 配置 ====================
    
    def get_llm_config(self, provider: str = None) -> Dict[str, Any]:
        """获取 LLM 配置"""
        if provider is None:
            provider = self.get_llm_provider()
        
        config = self.get("LLM", provider, default={})
        
        # 解析环境变量
        if "api_key" in config:
            config["api_key"] = self.resolve_env_vars(config["api_key"])
        
        return config
    
    # ==================== ASR 配置 ====================
    
    def get_asr_config(self, provider: str = None) -> Dict[str, Any]:
        """获取 ASR 配置"""
        if provider is None:
            provider = self.get_asr_provider()
        
        config = self.get("ASR", provider, default={})
        
        if "api_key" in config:
            config["api_key"] = self.resolve_env_vars(config["api_key"])
        
        return config
    
    # ==================== TTS 配置 ====================
    
    def get_tts_config(self, provider: str = None) -> Dict[str, Any]:
        """获取 TTS 配置"""
        if provider is None:
            provider = self.get_tts_provider()
        
        config = self.get("TTS", provider, default={})
        
        if "api_key" in config:
            config["api_key"] = self.resolve_env_vars(config["api_key"])
        
        return config
    
    # ==================== 工具配置 ====================
    
    def get_tool_config(self, tool_name: str) -> Dict[str, Any]:
        """获取工具配置"""
        config = self.get("Tools", tool_name, default={})
        
        # 解析环境变量
        for key, value in config.items():
            if isinstance(value, str):
                config[key] = self.resolve_env_vars(value)
        
        return config
    
    def get_weather_config(self) -> Dict[str, Any]:
        """获取天气工具配置"""
        return self.get_tool_config("get_weather")
    
    def get_news_config(self) -> Dict[str, Any]:
        """获取新闻工具配置"""
        return self.get_tool_config("get_trending_news")
    
    def get_search_config(self) -> Dict[str, Any]:
        """获取搜索工具配置"""
        return self.get_tool_config("web_search")
    
    def get_knowledge_tool_config(self) -> Dict[str, Any]:
        """获取知识库工具配置"""
        return self.get_tool_config("query_knowledge")
    
    # ==================== 意图配置 ====================
    
    def get_intent_config(self) -> Dict[str, Any]:
        """获取意图路由配置"""
        return self.get("Intent", "IntentRouter", default={})
    
    # ==================== CRM 配置 ====================
    
    def get_crm_config(self) -> Dict[str, Any]:
        """获取 CRM 配置"""
        return self.get("CRM", "CRMAnalyzer", default={})
    
    # ==================== 知识库配置 ====================
    
    def get_knowledge_config(self) -> Dict[str, Any]:
        """获取知识库配置"""
        return self.get("Knowledge", "RAGService", default={})
    
    # ==================== Coze 配置 ====================
    
    def get_coze_config(self) -> Dict[str, Any]:
        """获取 Coze 配置"""
        config = self.get("Coze", default={})
        
        if "api_key" in config:
            config["api_key"] = self.resolve_env_vars(config["api_key"])
        
        return config
    
    # ==================== 服务器配置 ====================
    
    def get_server_config(self) -> Dict[str, Any]:
        """获取服务器配置"""
        return self.get("server", default={
            "host": "0.0.0.0",
            "port": 8000,
            "debug": True
        })
    
    def get_database_config(self) -> Dict[str, Any]:
        """获取数据库配置"""
        config = self.get("database", default={
            "type": "sqlite",
            "url": "sqlite+aiosqlite:///./xiaozhi.db"
        })
        
        if "url" in config:
            config["url"] = self.resolve_env_vars(config["url"])
        
        return config
    
    def get_cost_config(self) -> Dict[str, Any]:
        """获取成本控制配置"""
        return self.get("cost", default={
            "daily_limit": 10.0,
            "monthly_limit": 200.0,
            "warn_threshold": 0.8
        })


# 全局配置加载器实例
config = ConfigLoader()
