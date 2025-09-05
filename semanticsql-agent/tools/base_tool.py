"""
基础工具类 - 基于 LangChain BaseTool
简化设计，提供记忆访问功能
"""
from typing import Dict, Any
from langchain.tools import BaseTool
import logging


class BaseSemanticSQLTool(BaseTool):
    """SemanticSQL工具基类
    
    提供记忆访问功能，让工具能够从Agent记忆中获取和保存数据
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Use object.__setattr__ to bypass Pydantic validation for these internal attributes
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
    
    def get_schema_info(self) -> Dict[str, Any]:
        """获取数据库结构信息"""
        return self.get_from_memory("schema_info")
    
    def get_domain_info(self) -> Dict[str, Any]:
        """获取领域信息"""
        return self.get_from_memory("domain_info")
    
    def get_field_classification(self) -> Dict[str, Any]:
        """获取字段分类信息"""
        return self.get_from_memory("field_classification")
    
    def get_column_meanings(self) -> Dict[str, Any]:
        """获取列含义信息"""
        return self.get_from_memory("column_meanings")
    
    def get_table_meanings(self) -> Dict[str, Any]:
        """获取表含义信息"""
        return self.get_from_memory("table_meanings")
    
    def get_er_relations(self) -> Dict[str, Any]:
        """获取ER关系信息"""
        return self.get_from_memory("er_relations")
    
    def run(self, *args, **kwargs) -> Any:
        """执行工具并清理输出"""
        self.logger.info(f"Tool '{self.name}' called with args: {args}, kwargs: {kwargs}")
        
        try:
            result = self._run(*args, **kwargs)
            self.logger.info(f"Tool '{self.name}' executed successfully")
            return result
        except Exception as e:
            self.logger.error(f"Tool '{self.name}' failed with error: {str(e)}")
            raise