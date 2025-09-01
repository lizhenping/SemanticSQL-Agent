"""
记忆管理模块 - 基于 LangChain BaseMemory
"""
from typing import Dict, Any, List
from langchain.memory import BaseMemory
from langchain.schema import BaseMessage
from pydantic import Field


class DatabaseAnalysisMemory(BaseMemory):
    """数据库分析结果记忆管理"""
    
    # 存储的记忆变量
    memories: Dict[str, Any] = Field(default_factory=dict)
    
    # 记忆键
    memory_key: str = "db_analysis"
    
    def clear(self):
        """清空记忆"""
        self.memories = {}
    
    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """加载记忆变量"""
        return {self.memory_key: self.memories}
    
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, Any]):
        """保存上下文到记忆"""
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
    
    def update_analysis(self, analysis_type: str, result: Dict[str, Any]):
        """更新特定类型的分析结果"""
        self.memories[analysis_type] = result
    
    def get_analysis(self, analysis_type: str) -> Dict[str, Any]:
        """获取特定类型的分析结果"""
        return self.memories.get(analysis_type, {})
    
    @property
    def memory_variables(self) -> List[str]:
        """返回记忆变量列表"""
        return [self.memory_key]