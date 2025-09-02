"""
记忆管理模块 - 基于 LangChain BaseMemory
简化版本，参考pipeline的上下文管理模式
"""
from typing import Dict, Any, List
from langchain_core.memory import BaseMemory
from pydantic import Field
import logging


class DatabaseAnalysisMemory(BaseMemory):
    """数据库分析结果记忆管理
    
    基于 LangChain BaseMemory 实现，存储数据库分析的所有结果
    参考pipeline的上下文管理，简化数据结构
    """
    
    # 存储的记忆变量
    memories: Dict[str, Any] = Field(default_factory=dict)
    
    # 记忆键
    memory_key: str = "db_analysis"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, 'logger', logging.getLogger(__name__))
    
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
            包含记忆的字典，结构为 {memory_key: {analysis_type: analysis_data}}
        """
        return {self.memory_key: self.memories}
    
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> None:
        """保存上下文到记忆
        
        参考pipeline的简洁设计，根据工具名称直接保存结果
        
        Args:
            inputs: 输入参数
            outputs: 工具的输出结果
        """
        # 获取工具名称
        tool_name = inputs.get("tool_name") or inputs.get("action", {}).get("tool")
        
        if not tool_name:
            return
        
        # 获取实际数据
        data = outputs.get("output", outputs) if isinstance(outputs, dict) else outputs
        
        # 根据工具名称保存到对应的键
        memory_mapping = {
            "schema_extraction": "schema_info",
            "domain_analysis": "domain_info", 
            "field_classification": "field_classification",
            "column_meaning_analysis": "column_meanings",
            "table_meaning_analysis": "table_meanings",
            "er_analysis": "er_relations"
        }
        
        if tool_name in memory_mapping:
            self.memories[memory_mapping[tool_name]] = data
            self.logger.debug(f"Saved {tool_name} results to memory")
    
    def update_analysis(self, analysis_type: str, result: Dict[str, Any]):
        """更新特定类型的分析结果
        
        Args:
            analysis_type: 分析类型
            result: 分析结果
        """
        self.memories[analysis_type] = result
        self.logger.info(f"Updated {analysis_type} in memory")
    
    def get_analysis(self, analysis_type: str) -> Dict[str, Any]:
        """获取特定类型的分析结果
        
        Args:
            analysis_type: 分析类型
            
        Returns:
            分析结果，如果不存在返回空字典
        """
        return self.memories.get(analysis_type, {})
    
    def has_complete_analysis(self) -> bool:
        """检查是否有完整的数据库分析结果"""
        required_analyses = [
            "schema_info", "domain_info", "field_classification",
            "column_meanings", "table_meanings", "er_relations"
        ]
        return all(analysis in self.memories for analysis in required_analyses)
    
    def get_summary(self) -> str:
        """获取记忆摘要"""
        if not self.memories:
            return "无数据库分析结果"
        
        summary_parts = []
        
        # 数据库结构摘要
        schema_info = self.memories.get("schema_info", {})
        if schema_info:
            tables = schema_info.get("tables", {})
            summary_parts.append(f"数据库包含 {len(tables)} 个表")
        
        # 业务领域摘要
        domain_info = self.memories.get("domain_info", {})
        if domain_info and domain_info.get("primary_domain"):
            summary_parts.append(f"业务领域: {domain_info['primary_domain']}")
        
        # 分析完整性
        completed = sum(1 for key in self.memories if key in [
            "field_classification", "column_meanings", "table_meanings", "er_relations"
        ])
        if completed > 0:
            summary_parts.append(f"已完成 {completed}/4 项分析")
        
        return "; ".join(summary_parts) if summary_parts else "数据库分析进行中"