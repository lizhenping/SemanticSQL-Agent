"""格式化器基类

定义格式化器的接口和通用功能。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseFormatter(ABC):
    """格式化器基类
    
    所有格式化器必须继承此类并实现format方法。
    """
    
    @abstractmethod
    def format(self, data: Any, context: Optional[Dict[str, Any]] = None) -> str:
        """格式化数据
        
        Args:
            data: 要格式化的数据
            context: 格式化上下文，包含额外信息
            
        Returns:
            格式化后的字符串
        """
        pass
    
    def _truncate(self, text: str, max_length: int = 100) -> str:
        """截断文本
        
        Args:
            text: 原始文本
            max_length: 最大长度
            
        Returns:
            截断后的文本
        """
        if len(text) <= max_length:
            return text
        return text[:max_length - 3] + "..."
    
    def _format_list(self, items: list, separator: str = ", ") -> str:
        """格式化列表
        
        Args:
            items: 列表项
            separator: 分隔符
            
        Returns:
            格式化后的字符串
        """
        return separator.join(str(item) for item in items)