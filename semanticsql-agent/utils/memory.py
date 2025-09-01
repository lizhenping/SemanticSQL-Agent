"""
记忆管理模块 - 基于 LangChain BaseMemory
"""
from typing import Dict, Any, List
from pydantic import Field

try:
    # LangChain 0.2.x
    from langchain_core.memory import BaseMemory
except ImportError:
    try:
        # LangChain 0.1.x fallback
        from langchain.memory.base import BaseMemory
    except ImportError:
        # Another fallback
        from langchain.schema.memory import BaseMemory


class DatabaseAnalysisMemory(BaseMemory):
    """数据库分析结果记忆管理
    
    基于 LangChain BaseMemory 实现，存储数据库分析的所有结果
    """
    
    # 存储的记忆变量
    memories: Dict[str, Any] = Field(default_factory=dict)
    
    # 记忆键
    memory_key: str = "db_analysis"
    
    # 返回的记忆变量键列表
    @property
    def memory_variables(self) -> List[str]:
        """返回记忆变量列表"""
        return [self.memory_key]
    
    def clear(self):
        """清空记忆"""
        self.memories = {}
    
    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """加载记忆变量
        
        Args:
            inputs: 输入参数（LangChain 要求的接口）
            
        Returns:
            包含记忆的字典
        """
        return {self.memory_key: self.memories}
    
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, Any]):
        """保存上下文到记忆
        
        Args:
            inputs: 输入参数，应包含 tool_name
            outputs: 工具的输出结果
        """
        # 根据工具名称更新对应的记忆
        tool_name = inputs.get("tool_name")
        
        if tool_name == "schema_extraction":
            self.memories["schema_info"] = outputs
        elif tool_name == "domain_analysis":
            self.memories["domain_info"] = outputs
        elif tool_name == "field_classification":
            self.memories["field_classification"] = outputs
        elif tool_name == "column_meaning_analysis":
            self.memories["column_meanings"] = outputs
        elif tool_name == "table_meaning_analysis":
            self.memories["table_meanings"] = outputs
        elif tool_name == "er_analysis":
            self.memories["er_relations"] = outputs
        else:
            # 对于其他工具，可以选择保存或忽略
            if tool_name:
                self.memories[f"tool_{tool_name}"] = outputs
    
    def update_analysis(self, analysis_type: str, result: Dict[str, Any]):
        """更新特定类型的分析结果
        
        Args:
            analysis_type: 分析类型
            result: 分析结果
        """
        self.memories[analysis_type] = result
    
    def get_analysis(self, analysis_type: str) -> Dict[str, Any]:
        """获取特定类型的分析结果
        
        Args:
            analysis_type: 分析类型
            
        Returns:
            分析结果，如果不存在返回空字典
        """
        return self.memories.get(analysis_type, {})