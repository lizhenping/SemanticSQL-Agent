"""
基础分析工具类 - 提供通用的输入处理和验证
"""

import json
from typing import Dict, Any, Type, Union
from langchain.tools import BaseTool
from pydantic import BaseModel, Field, validator, field_validator

from models.exceptions import DataValidationError


class AnalysisToolInput(BaseModel):
    """分析工具基础输入类"""
    
    @field_validator('*', mode='before')
    @classmethod
    def parse_json_strings(cls, v):
        """解析JSON字符串为字典（处理LangChain序列化问题）"""
        if isinstance(v, str):
            try:
                import json
                parsed = json.loads(v)
                if isinstance(parsed, dict):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass
        return v


class BaseAnalysisTool(BaseTool):
    """分析工具基类"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 使用object.__setattr__避开Pydantic验证
        object.__setattr__(self, '_agent_memory', None)
    
    def set_memory_reference(self, memory):
        """设置Agent memory引用"""
        object.__setattr__(self, '_agent_memory', memory)
    
    def get_current_memory(self) -> Dict[str, Any]:
        """获取当前Agent memory状态"""
        if self._agent_memory:
            return self._agent_memory.load_memory_variables({}).get("db_analysis", {})
        return {}
    
    def get_data_from_memory_or_param(self, param_value: Any, memory_key: str) -> Dict[str, Any]:
        """从参数或memory中获取数据
        
        支持多种参数格式：
        1. 直接字典参数
        2. LangChain JSON字符串包装（处理 {"input": "{JSON_STRING}"} 格式）
        3. 纯JSON字符串
        4. 从Agent memory获取
        """
        # 处理直接字典参数
        if param_value and isinstance(param_value, dict) and param_value:
            # 检查是否包含目标key
            if memory_key in param_value:
                return param_value[memory_key]
            # 检查是否是LangChain包装格式：{"input": "{JSON_STRING}"}
            elif "input" in param_value and isinstance(param_value["input"], str):
                try:
                    import json
                    nested_data = json.loads(param_value["input"])
                    if isinstance(nested_data, dict):
                        if memory_key in nested_data:
                            return nested_data[memory_key]
                        # 如果nested_data本身就是目标数据
                        return nested_data
                except (json.JSONDecodeError, TypeError):
                    pass
            # 如果都不匹配，返回整个字典
            return param_value
        
        # 处理纯JSON字符串参数
        if param_value and isinstance(param_value, str):
            try:
                import json
                parsed_data = json.loads(param_value)
                if isinstance(parsed_data, dict) and parsed_data:
                    # 优先返回目标key的值
                    if memory_key in parsed_data:
                        return parsed_data[memory_key]
                    # 否则返回整个解析的数据
                    return parsed_data
            except (json.JSONDecodeError, TypeError):
                pass
        
        # 从memory获取
        if self._agent_memory:
            current_memory = self.get_current_memory()
            return self.get_analysis_from_memory(current_memory, memory_key)
        
        return {}
    
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