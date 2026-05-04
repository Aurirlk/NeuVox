"""
日志配置模块
统一日志格式和输出
"""
import logging
import sys
from datetime import datetime
from pathlib import Path


def setup_logger(
    name: str = "xiaozhi",
    level: str = "INFO",
    log_dir: str = "logs"
) -> logging.Logger:
    """
    配置日志
    
    Args:
        name: 日志名称
        level: 日志级别
        log_dir: 日志目录
        
    Returns:
        配置好的 Logger 实例
    """
    # 创建日志目录
    Path(log_dir).mkdir(exist_ok=True)
    
    # 创建 logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # 避免重复添加 handler
    if logger.handlers:
        return logger
    
    # 日志格式
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # 控制台输出
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件输出
    today = datetime.now().strftime("%Y-%m-%d")
    file_handler = logging.FileHandler(
        f"{log_dir}/{name}_{today}.log",
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger


# 全局 logger 实例
logger = setup_logger()
