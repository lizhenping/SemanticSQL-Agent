"""
记忆管理模块 - 基于 LangChain BaseMemory
适配 LangChain 0.3.x 版本
"""
from typing import Dict, Any, List
from langchain_core.memory import BaseMemory
from pydantic import Field


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
    
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> None:
        """保存上下文到记忆
        
        Args:
            inputs: 输入参数，应包含 tool_name 或可以从 inputs 中推断
            outputs: 工具的输出结果
        """
        # 尝试从多个位置获取工具名称
        tool_name = None
        if "tool_name" in inputs:
            tool_name = inputs["tool_name"]
        elif "input" in inputs and isinstance(inputs["input"], dict):
            tool_name = inputs["input"].get("tool_name")
        elif "action" in inputs:
            # 从 LangChain agent 的 action 中获取
            action = inputs["action"]
            if hasattr(action, 'tool'):
                tool_name = action.tool
        
        # 如果仍然没有找到工具名称，尝试从输出中推断
        if not tool_name and isinstance(outputs, dict):
            # 检查输出结构特征来推断工具类型
            if "tables" in outputs and "columns" in outputs:
                tool_name = "schema_extraction"
            elif "primary_domain" in outputs and "entities" in outputs:
                tool_name = "domain_analysis"
            elif "field_classifications" in outputs:
                tool_name = "field_classification"
        
        # 根据工具名称更新对应的记忆
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
        
        schema_info = self.memories.get("schema_info", {})
        domain_info = self.memories.get("domain_info", {})
        
        summary_parts = []
        
        # 数据库结构摘要
        if schema_info:
            tables = schema_info.get("tables", {})
            summary_parts.append(f"数据库包含 {len(tables)} 个表")
            if tables:
                table_names = list(tables.keys())[:3]
                summary_parts.append(f"主要表: {', '.join(table_names)}")
        
        # 业务领域摘要
        if domain_info:
            primary_domain = domain_info.get("primary_domain", "")
            if primary_domain:
                summary_parts.append(f"业务领域: {primary_domain}")
        
        # 分析完整性
        analysis_status = []
        for analysis_name in ["field_classification", "column_meanings", "table_meanings", "er_relations"]:
            if analysis_name in self.memories:
                analysis_status.append(analysis_name.replace("_", " "))
        
        if analysis_status:
            summary_parts.append(f"已完成分析: {', '.join(analysis_status)}")
        
        return "; ".join(summary_parts) if summary_parts else "数据库分析进行中"