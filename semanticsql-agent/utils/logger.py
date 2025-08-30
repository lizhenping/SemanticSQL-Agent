"""
日志配置和管理
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
import json
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler


class ColoredFormatter(logging.Formatter):
    """带颜色的控制台日志格式化器"""
    
    COLORS = {
        'DEBUG': '\033[36m',    # 青色
        'INFO': '\033[32m',     # 绿色
        'WARNING': '\033[33m',  # 黄色
        'ERROR': '\033[31m',    # 红色
        'CRITICAL': '\033[35m', # 紫色
    }
    RESET = '\033[0m'
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)


class JSONFormatter(logging.Formatter):
    """JSON格式化器"""
    
    def format(self, record):
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        if hasattr(record, 'extra_data'):
            log_data['extra'] = record.extra_data
        
        return json.dumps(log_data, ensure_ascii=False)


class LoggerManager:
    """日志管理器"""
    
    def __init__(self, 
                 name: str = "semanticsql",
                 level: str = "INFO",
                 log_dir: str = "logs",
                 console: bool = True,
                 file: bool = True,
                 json_format: bool = False):
        """
        初始化日志管理器
        
        Args:
            name: 日志器名称
            level: 日志级别
            log_dir: 日志目录
            console: 是否输出到控制台
            file: 是否输出到文件
            json_format: 是否使用JSON格式
        """
        self.name = name
        self.level = getattr(logging, level.upper())
        self.log_dir = Path(log_dir)
        self.console = console
        self.file = file
        self.json_format = json_format
        
        # 创建日志目录
        if file:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 配置根日志器
        self._setup_logger()
    
    def _setup_logger(self):
        """设置日志器"""
        logger = logging.getLogger(self.name)
        logger.setLevel(self.level)
        logger.handlers = []  # 清除已有处理器
        
        # 控制台处理器
        if self.console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(self.level)
            
            if self.json_format:
                console_formatter = JSONFormatter()
            else:
                console_formatter = ColoredFormatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
            
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)
        
        # 文件处理器
        if self.file:
            # 按日期轮转的文件处理器
            log_file = self.log_dir / f"{self.name}.log"
            file_handler = TimedRotatingFileHandler(
                log_file,
                when='midnight',
                interval=1,
                backupCount=30,
                encoding='utf-8'
            )
            file_handler.setLevel(self.level)
            
            if self.json_format:
                file_formatter = JSONFormatter()
            else:
                file_formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
            
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
            
            # 错误日志单独文件
            error_file = self.log_dir / f"{self.name}_error.log"
            error_handler = RotatingFileHandler(
                error_file,
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(file_formatter)
            logger.addHandler(error_handler)
    
    def get_logger(self, name: str = None) -> logging.Logger:
        """
        获取日志器
        
        Args:
            name: 子日志器名称
            
        Returns:
            日志器实例
        """
        if name:
            return logging.getLogger(f"{self.name}.{name}")
        return logging.getLogger(self.name)
    
    def set_level(self, level: str):
        """设置日志级别"""
        self.level = getattr(logging, level.upper())
        logger = logging.getLogger(self.name)
        logger.setLevel(self.level)
        
        for handler in logger.handlers:
            handler.setLevel(self.level)
    
    def add_file_handler(self, filename: str, level: str = None):
        """添加额外的文件处理器"""
        logger = logging.getLogger(self.name)
        
        file_path = self.log_dir / filename
        handler = RotatingFileHandler(
            file_path,
            maxBytes=10*1024*1024,
            backupCount=5,
            encoding='utf-8'
        )
        
        handler.setLevel(getattr(logging, level.upper()) if level else self.level)
        
        if self.json_format:
            handler.setFormatter(JSONFormatter())
        else:
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            ))
        
        logger.addHandler(handler)


# 全局日志管理器
_logger_manager = None


def setup_logger(name: str = "semanticsql",
                level: str = "INFO",
                log_dir: str = "logs",
                console: bool = True,
                file: bool = True,
                json_format: bool = False) -> LoggerManager:
    """
    设置全局日志器
    
    Args:
        name: 日志器名称
        level: 日志级别
        log_dir: 日志目录
        console: 是否输出到控制台
        file: 是否输出到文件
        json_format: 是否使用JSON格式
        
    Returns:
        LoggerManager实例
    """
    global _logger_manager
    
    _logger_manager = LoggerManager(
        name=name,
        level=level,
        log_dir=log_dir,
        console=console,
        file=file,
        json_format=json_format
    )
    
    return _logger_manager


def get_logger(name: str = None) -> logging.Logger:
    """
    获取日志器
    
    Args:
        name: 日志器名称
        
    Returns:
        日志器实例
    """
    global _logger_manager
    
    if _logger_manager is None:
        _logger_manager = setup_logger()
    
    return _logger_manager.get_logger(name)


def log_function_call(func):
    """函数调用日志装饰器"""
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        logger.debug(f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
        
        try:
            result = func(*args, **kwargs)
            logger.debug(f"{func.__name__} returned {result}")
            return result
        except Exception as e:
            logger.error(f"{func.__name__} raised {e}", exc_info=True)
            raise
    
    return wrapper


def log_execution_time(func):
    """执行时间日志装饰器"""
    import time
    
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(f"{func.__name__} executed in {execution_time:.3f} seconds")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"{func.__name__} failed after {execution_time:.3f} seconds: {e}")
            raise
    
    return wrapper


# 日志级别快捷函数
def debug(message: str, **kwargs):
    """记录DEBUG日志"""
    get_logger().debug(message, **kwargs)


def info(message: str, **kwargs):
    """记录INFO日志"""
    get_logger().info(message, **kwargs)


def warning(message: str, **kwargs):
    """记录WARNING日志"""
    get_logger().warning(message, **kwargs)


def error(message: str, **kwargs):
    """记录ERROR日志"""
    get_logger().error(message, **kwargs)


def critical(message: str, **kwargs):
    """记录CRITICAL日志"""
    get_logger().critical(message, **kwargs)