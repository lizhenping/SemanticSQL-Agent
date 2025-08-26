"""日志配置模块

负责设置和管理应用程序的日志配置
"""

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[str] = 'nl2sql_pipeline.log',
    log_format: Optional[str] = None
) -> None:
    """设置日志配置
    
    Args:
        level: 日志级别
        log_file: 日志文件路径，如果为None则不写入文件
        log_format: 日志格式字符串，如果为None则使用默认格式
    """
    if log_format is None:
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    handlers = [logging.StreamHandler(sys.stdout)]
    
    if log_file:
        # 确保日志文件目录存在
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding='utf-8'))
    
    logging.basicConfig(
        level=level,
        format=log_format,
        handlers=handlers
    )


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的logger
    
    Args:
        name: logger名称
        
    Returns:
        logging.Logger实例
    """
    return logging.getLogger(name)