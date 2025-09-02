"""
基础工具类 - 基于 LangChain BaseTool
参考pipeline的简洁设计，去除冗余验证
"""
from abc import abstractmethod
from typing import Dict, Any, Optional
from langchain.tools import BaseTool
from pydantic import BaseModel
import logging


class BaseSemanticSQLTool(BaseTool):
    """SemanticSQL工具基类
    
    所有工具的基类，提供通用功能：
    - 日志记录
    - 记忆访问
    - 错误处理
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 使用object.__setattr__避开Pydantic验证
        object.__setattr__(self, 'logger', logging.getLogger(self.__class__.__name__))
        object.__setattr__(self, '_agent_memory', None)
    
    def set_memory(self, memory):
        """设置记忆引用"""
        object.__setattr__(self, '_agent_memory', memory)
    
    def get_from_memory(self, key: str) -> Dict[str, Any]:
        """从记忆中获取数据
        
        Args:
            key: 数据键
            
        Returns:
            数据字典，如果不存在返回空字典
        """
        if self._agent_memory:
            return self._agent_memory.get_analysis(key)
        return {}
    
    def save_to_memory(self, tool_name: str, data: Any):
        """保存数据到记忆
        
        Args:
            tool_name: 工具名称
            data: 要保存的数据
        """
        if self._agent_memory:
            try:
                self._agent_memory.save_context(
                    inputs={"tool_name": tool_name},
                    outputs=data
                )
            except Exception as e:
                self.logger.warning(f"Failed to save to memory: {e}")
    
    @abstractmethod
    def _run(self, *args, **kwargs) -> Any:
        """执行工具的核心逻辑"""
        pass
    
    async def _arun(self, *args, **kwargs) -> Any:
        """异步执行（默认调用同步方法）"""
        return self._run(*args, **kwargs)