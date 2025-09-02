"""命令基类定义

定义所有命令的基础接口和通用功能
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging
from dataclasses import dataclass


@dataclass
class CommandResult:
    """命令执行结果"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    exit_code: int = 0


class Command(ABC):
    """命令基类
    
    所有命令处理器都应该继承此类并实现execute方法
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """初始化命令
        
        Args:
            logger: 日志记录器，如果为None则使用默认logger
        """
        self.logger = logger or logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def execute(self, args: Dict[str, Any]) -> CommandResult:
        """执行命令
        
        Args:
            args: 命令参数字典
            
        Returns:
            CommandResult: 命令执行结果
        """
        pass
    
    def validate_args(self, args: Dict[str, Any], required_fields: list) -> Optional[str]:
        """验证必要参数
        
        Args:
            args: 参数字典
            required_fields: 必要字段列表
            
        Returns:
            如果验证失败返回错误消息，否则返回None
        """
        missing_fields = [field for field in required_fields if not args.get(field)]
        
        if missing_fields:
            return f"缺少必要参数: {', '.join(missing_fields)}"
        
        return None