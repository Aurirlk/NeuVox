"""
配置加载器
统一加载 YAML 配置文件和环境变量
支持热更新和远程配置拉取
"""
import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from dotenv import load_dotenv

from app.utils.logger import logger

# 加载 .env 文件
load_dotenv()


class ConfigLoader:
    """
    配置加载器
    
    支持：
    1. 统一配置文件: configs/.config.yaml
    2. 热更新：运行时修改配置
    3. 远程配置拉取：从 manager-api 获取配置
    """
    
    _instance = None
    _config: Dict[str, Any] = {}
    _selected_modules: Dict[str, str] = {}
    _config_callbacks: List[Callable] = []
    
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
        
        # 加载统一配置文件
        unified_config = configs_dir / ".config.yaml"
        if unified_config.exists():
            try:
                with open(unified_config, "r", encoding="utf-8") as f:
                    self._config = yaml.safe_load(f) or {}
                self._selected_modules = self._config.get("selected_module", {})
                logger.info("[Config] 加载统一配置: .config.yaml")
            except Exception as e:
                logger.error(f"[Config] 加载统一配置失败: {e}")
    
    def get(self, *keys, default: Any = None) -> Any:
        """获取配置值（支持嵌套键）"""
        value = self._config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
        return value if value is not None else default
    
    def set(self, *keys, value: Any):
        """设置配置值（热更新）"""
        if len(keys) == 0:
            return
        
        target = self._config
        for key in keys[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]
        
        target[keys[-1]] = value
        
        for callback in self._config_callbacks:
            try:
                callback(keys, value)
            except Exception as e:
                logger.error(f"[Config] 配置回调失败: {e}")
        
        logger.info(f"[Config] 配置已更新: {'.'.join(keys)} = {value}")
    
    def register_callback(self, callback: Callable):
        """注册配置更新回调"""
        self._config_callbacks.append(callback)
    
    def resolve_env_vars(self, value: Any) -> Any:
        """解析环境变量引用 ${VAR}"""
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_var = value[2:-1]
            return os.getenv(env_var, value)
        return value
    
    def get_resolved(self, *keys, default: Any = None) -> Any:
        """获取配置值并解析环境变量"""
        value = self.get(*keys, default=default)
        return self.resolve_env_vars(value)
    
    def get_selected_module(self, module_type: str) -> Optional[str]:
        return self._selected_modules.get(module_type)
    
    def get_llm_provider(self) -> str:
        return self.get_selected_module("LLM") or "DeepSeekLLM"
    
    def get_asr_provider(self) -> str:
        return self.get_selected_module("ASR") or "MiniMaxASR"
    
    def get_tts_provider(self) -> str:
        return self.get_selected_module("TTS") or "MiMoTTS"
    
    def get_llm_config(self, provider: str = None) -> Dict[str, Any]:
        if provider is None:
            provider = self.get_llm_provider()
        config = self.get("LLM", provider, default={})
        if "api_key" in config:
            config["api_key"] = self.resolve_env_vars(config["api_key"])
        return config
    
    def get_asr_config(self, provider: str = None) -> Dict[str, Any]:
        if provider is None:
            provider = self.get_asr_provider()
        config = self.get("ASR", provider, default={})
        if "api_key" in config:
            config["api_key"] = self.resolve_env_vars(config["api_key"])
        return config
    
    def get_tts_config(self, provider: str = None) -> Dict[str, Any]:
        if provider is None:
            provider = self.get_tts_provider()
        config = self.get("TTS", provider, default={})
        if "api_key" in config:
            config["api_key"] = self.resolve_env_vars(config["api_key"])
        return config
    
    def get_tool_config(self, tool_name: str) -> Dict[str, Any]:
        config = self.get("Tools", tool_name, default={})
        for key, value in list(config.items()):
            if isinstance(value, str):
                config[key] = self.resolve_env_vars(value)
        return config
    
    def get_weather_config(self) -> Dict[str, Any]:
        return self.get_tool_config("get_weather")
    
    def get_news_config(self) -> Dict[str, Any]:
        return self.get_tool_config("get_trending_news")
    
    def get_search_config(self) -> Dict[str, Any]:
        return self.get_tool_config("web_search")
    
    def get_knowledge_tool_config(self) -> Dict[str, Any]:
        return self.get_tool_config("query_knowledge")
    
    def get_intent_config(self) -> Dict[str, Any]:
        return self.get("Intent", "IntentRouter", default={})
    
    def get_crm_config(self) -> Dict[str, Any]:
        return self.get("CRM", "CRMAnalyzer", default={})
    
    def get_knowledge_config(self) -> Dict[str, Any]:
        return self.get("Knowledge", "RAGService", default={})
    
    def get_coze_config(self) -> Dict[str, Any]:
        config = self.get("Coze", default={})
        if "api_key" in config:
            config["api_key"] = self.resolve_env_vars(config["api_key"])
        return config
    
    def get_server_config(self) -> Dict[str, Any]:
        return self.get("server", default={"host": "0.0.0.0", "port": 8000, "debug": True})
    
    def get_database_config(self) -> Dict[str, Any]:
        config = self.get("database", default={"type": "sqlite", "url": "sqlite+aiosqlite:///./xiaozhi.db"})
        if "url" in config:
            config["url"] = self.resolve_env_vars(config["url"])
        return config
    
    def get_cost_config(self) -> Dict[str, Any]:
        return self.get("cost", default={"daily_limit": 10.0, "monthly_limit": 200.0, "warn_threshold": 0.8})


# 全局配置加载器实例
config = ConfigLoader()
