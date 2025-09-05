"""
基础工具类 - 优化版本
简化设计，支持记忆访问和直接参数传递
"""

from typing import Dict, Any, Optional
from langchain.tools import BaseTool
import logging


class BaseSemanticSQLTool(BaseTool):
    """SemanticSQL工具基类 - 简化版本
    
    职责：
    - 提供基础工具接口
    - 支持记忆访问（向后兼容）
    - 统一错误处理和日志记录
    
    设计原则：
    - 简化接口：最小化必要功能
    - 向后兼容：保持现有工具可用
    - 为未来准备：支持参数传递模式
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, 'logger', logging.getLogger(self.__class__.__name__))
        object.__setattr__(self, '_agent_memory', None)
    
    # ========== 记忆访问接口（向后兼容）==========
    def set_memory(self, memory) -> None:
        """设置记忆引用"""
        object.__setattr__(self, '_agent_memory', memory)
    
    def get_from_memory(self, key: str) -> Dict[str, Any]:
        """从记忆中获取数据"""
        if self._agent_memory:
            return self._agent_memory.get_analysis(key)
        return {}
    
    def save_to_memory(self, tool_name: str, data: Any) -> None:
        """保存数据到记忆"""
        if self._agent_memory:
            self._agent_memory.save_context(
                inputs={"tool_name": tool_name},
                outputs=data
            )
    
    # ========== 工具执行接口 ==========
    def run(self, *args, **kwargs) -> Any:
        """执行工具 - 统一的执行入口"""
        self.logger.info(f"Executing tool '{self.name}'")
        
        result = self._run(*args, **kwargs)
        self.logger.info(f"Tool '{self.name}' completed successfully")
        
        return result