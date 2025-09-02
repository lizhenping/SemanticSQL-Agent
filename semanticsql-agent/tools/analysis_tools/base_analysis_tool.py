"""
基础分析工具类 - 提供通用的输入处理和验证
"""

import json
from typing import Dict, Any, Type
from langchain.tools import BaseTool
from pydantic import BaseModel, Field, validator


class AnalysisToolInput(BaseModel):
    """分析工具基础输入类"""
    memory: Dict[str, Any] = Field(description="包含数据库分析结果的记忆")
    
    @validator('memory', pre=True)
    def validate_memory(cls, v):
        """验证并转换memory参数"""
        if isinstance(v, str):
            try:
                # 尝试解析JSON字符串
                return json.loads(v)
            except json.JSONDecodeError:
                raise ValueError(f"Invalid JSON string for memory: {v}")
        elif isinstance(v, dict):
            return v
        else:
            raise ValueError(f"Memory must be a dict or JSON string, got {type(v)}")


class BaseAnalysisTool(BaseTool):
    """分析工具基类"""
    
    def get_analysis_from_memory(self, memory: Dict[str, Any], analysis_type: str) -> Dict[str, Any]:
        """从memory中获取特定类型的分析结果
        
        Args:
            memory: 输入的memory参数
            analysis_type: 分析类型，如 'schema_info', 'domain_info' 等
            
        Returns:
            分析结果字典，如果不存在则返回空字典
        """
        # memory参数可能是完整的分析结果字典
        if isinstance(memory, dict) and analysis_type in memory:
            return memory[analysis_type]
        
        # 或者memory可能包含db_analysis结构
        if isinstance(memory, dict) and "db_analysis" in memory:
            return memory["db_analysis"].get(analysis_type, {})
        
        # 如果都没有，返回空字典
        return {}