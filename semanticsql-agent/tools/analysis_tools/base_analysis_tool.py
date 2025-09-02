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
    
    def get_memory_data(self, memory: Dict[str, Any]) -> Dict[str, Any]:
        """从memory中获取累积的分析数据"""
        # 如果memory中包含db_analysis键，说明是累积的数据
        if "db_analysis" in memory:
            return memory
        
        # 否则，将当前数据作为第一步的结果
        return {
            "db_analysis": {
                "schema_info": memory
            }
        }
    
    def merge_results(self, memory: Dict[str, Any], tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """将工具结果合并到memory中"""
        # 获取当前的累积数据
        accumulated_data = self.get_memory_data(memory)
        
        # 将新结果添加到累积数据中
        if "db_analysis" not in accumulated_data:
            accumulated_data["db_analysis"] = {}
        
        accumulated_data["db_analysis"][tool_name] = result
        
        return accumulated_data
    
    def format_accumulated_result(self, memory: Dict[str, Any], current_tool_name: str, current_result: Dict[str, Any]) -> Dict[str, Any]:
        """格式化累积的结果，供下一个工具使用"""
        # 获取累积数据
        accumulated_data = self.merge_results(memory, current_tool_name, current_result)
        
        # 返回完整的累积数据
        return accumulated_data