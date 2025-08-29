"""CLI Console 基类（参考 TRAEAgent）"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Dict, Any


class ConsoleMode(Enum):
    """控制台操作模式"""
    RUN = "run"  # 执行单个任务并退出
    INTERACTIVE = "interactive"  # 交互式多任务


class ConsoleType(Enum):
    """控制台类型"""
    SIMPLE = "simple"  # 简单文本控制台
    RICH = "rich"  # Rich 文本控制台


class CLIConsole(ABC):
    """CLI 控制台基类"""
    
    def __init__(self, mode: ConsoleMode = ConsoleMode.RUN):
        self.mode = mode
    
    @abstractmethod
    def start(self):
        """启动控制台显示"""
        pass
    
    @abstractmethod
    def print(self, message: str, style: Optional[str] = None):
        """打印消息到控制台
        
        Args:
            message: 要打印的消息
            style: 样式（如 'error', 'success', 'info'）
        """
        pass
    
    @abstractmethod
    def print_table(self, data: list, headers: list):
        """打印表格
        
        Args:
            data: 表格数据
            headers: 表头
        """
        pass
    
    @abstractmethod
    def get_user_input(self, prompt: str = "> ") -> Optional[str]:
        """获取用户输入（交互模式）
        
        Returns:
            用户输入的字符串，或 None 表示退出
        """
        pass
    
    @abstractmethod
    def clear(self):
        """清屏"""
        pass
    
    @abstractmethod
    def print_status(self, status: str, message: str):
        """打印状态消息
        
        Args:
            status: 状态类型（'thinking', 'executing', 'completed', 'error'）
            message: 状态消息
        """
        pass