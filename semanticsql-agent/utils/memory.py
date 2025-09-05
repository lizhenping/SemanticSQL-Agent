"""
记忆管理模块 - 优化版本
设计类型安全的分析上下文容器，替代字典式记忆系统
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from langchain_core.memory import BaseMemory
from pydantic import Field
import logging


# ========== 类型安全的分析结果容器 ==========
@dataclass
class SchemaInfo:
    """数据库结构信息"""
    database_name: str
    tables: Dict[str, Any] = field(default_factory=dict)
    total_tables: int = 0
    total_columns: int = 0
    relationships: List[Dict[str, Any]] = field(default_factory=list)


@dataclass 
class DomainInfo:
    """业务领域信息"""
    primary_domain: str = ""
    secondary_domains: List[str] = field(default_factory=list)
    business_concepts: List[str] = field(default_factory=list)
    confidence_score: float = 0.0


@dataclass
class FieldClassification:
    """字段分类信息"""
    field_classifications: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    classification_stats: Dict[str, int] = field(default_factory=dict)
    important_fields: List[str] = field(default_factory=list)


@dataclass
class ColumnMeanings:
    """列语义信息"""
    column_meanings: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    business_meanings: Dict[str, str] = field(default_factory=dict)
    semantic_groups: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class TableMeanings:
    """表语义信息"""
    table_meanings: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    table_relationships: List[Dict[str, Any]] = field(default_factory=list)
    core_tables: List[str] = field(default_factory=list)


@dataclass
class ERRelations:
    """实体关系信息"""
    relationships: List[Dict[str, Any]] = field(default_factory=list)
    entities: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    relationship_matrix: Dict[str, Dict[str, str]] = field(default_factory=dict)


@dataclass
class ScenarioCombinations:
    """场景组合信息"""
    combinations: List[Dict[str, Any]] = field(default_factory=list)
    total_combinations: int = 0
    generation_strategy: str = ""


@dataclass
class AnalysisContext:
    """类型安全的分析上下文容器 - 替代字典式记忆
    
    职责：
    - 存储所有分析阶段的结果
    - 提供类型安全的数据访问
    - 支持分析完整性检查
    
    设计原则：
    - 类型安全：使用强类型数据类
    - 单一职责：专门存储分析数据
    - 不可变性：通过dataclass确保数据一致性
    """
    
    # 核心分析数据
    schema_info: Optional[SchemaInfo] = None
    domain_info: Optional[DomainInfo] = None
    field_classification: Optional[FieldClassification] = None
    column_meanings: Optional[ColumnMeanings] = None
    table_meanings: Optional[TableMeanings] = None
    er_relations: Optional[ERRelations] = None
    
    # 生成相关数据
    scenario_combinations: Optional[ScenarioCombinations] = None
    current_question: str = ""
    current_sql: str = ""
    
    # 元数据
    analysis_timestamp: str = ""
    database_name: str = ""
    
    def is_analysis_complete(self) -> bool:
        """检查分析是否完整"""
        return all([
            self.schema_info is not None,
            self.domain_info is not None,
            self.field_classification is not None,
            self.column_meanings is not None,
            self.table_meanings is not None,
            self.er_relations is not None
        ])
    
    def get_completion_status(self) -> Dict[str, bool]:
        """获取各项分析的完成状态"""
        return {
            "schema_info": self.schema_info is not None,
            "domain_info": self.domain_info is not None,
            "field_classification": self.field_classification is not None,
            "column_meanings": self.column_meanings is not None,
            "table_meanings": self.table_meanings is not None,
            "er_relations": self.er_relations is not None,
            "scenario_combinations": self.scenario_combinations is not None
        }
    
    def get_summary(self) -> str:
        """获取分析上下文摘要"""
        if not any([self.schema_info, self.domain_info]):
            return "分析上下文为空"
        
        summary_parts = []
        
        # 数据库结构信息
        if self.schema_info:
            summary_parts.append(f"数据库: {self.schema_info.database_name}")
            summary_parts.append(f"表数量: {self.schema_info.total_tables}")
        
        # 业务领域信息
        if self.domain_info and self.domain_info.primary_domain:
            summary_parts.append(f"领域: {self.domain_info.primary_domain}")
        
        # 完成状态
        completed_count = sum(1 for completed in self.get_completion_status().values() if completed)
        summary_parts.append(f"完成度: {completed_count}/7")
        
        return " | ".join(summary_parts)


class DatabaseAnalysisMemory(BaseMemory):
    """基于类型安全容器的记忆管理器
    
    职责：
    - 兼容 LangChain BaseMemory 接口
    - 提供类型安全的数据存储和访问
    - 支持工具结果到类型化容器的转换
    
    设计原则：
    - 类型安全：内部使用 AnalysisContext
    - 兼容性：保持 LangChain 接口
    - 简化映射：直接的工具名到数据类型映射
    """
    
    # LangChain 要求的字段
    memories: Dict[str, Any] = Field(default_factory=dict)
    memory_key: str = "db_analysis"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, 'logger', logging.getLogger(__name__))
        object.__setattr__(self, 'context', AnalysisContext())
    
    # ========== LangChain 接口实现 ==========
    @property
    def memory_variables(self) -> List[str]:
        """返回记忆变量列表"""
        return [self.memory_key]
    
    def clear(self) -> None:
        """清空记忆"""
        self.memories = {}
        object.__setattr__(self, 'context', AnalysisContext())
    
    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """加载记忆变量 - 保持向后兼容"""
        # 为了兼容现有代码，同时提供字典格式和类型化格式
        return {
            self.memory_key: self.memories,
            "typed_context": self.context
        }
    
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> None:
        """保存上下文 - 转换为类型化容器
        
        Args:
            inputs: 输入参数
            outputs: 工具输出结果
        """
        tool_name = self._extract_tool_name(inputs)
        if not tool_name:
            return
        
        data = self._extract_output_data(outputs)
        
        # 更新类型化容器
        self._update_typed_context(tool_name, data)
        
        # 保持向后兼容的字典格式
        self._update_legacy_memory(tool_name, data)
        
        self.logger.info(f"💾 Saved {tool_name} to typed context")
    
    # ========== 内部辅助方法 ==========
    def _extract_tool_name(self, inputs: Dict[str, Any]) -> Optional[str]:
        """提取工具名称"""
        return inputs.get("tool_name") or inputs.get("action", {}).get("tool")
    
    def _extract_output_data(self, outputs: Dict[str, Any]) -> Any:
        """提取输出数据"""
        return outputs.get("output", outputs) if isinstance(outputs, dict) else outputs
    
    def _update_typed_context(self, tool_name: str, data: Any) -> None:
        """更新类型化上下文"""
        try:
            if tool_name == "schema_extraction":
                self._update_schema_info(data)
            elif tool_name == "domain_analysis":
                self._update_domain_info(data)
            elif tool_name == "field_analysis":
                self._update_field_classification(data)
            elif tool_name == "column_analysis":
                self._update_column_meanings(data)
            elif tool_name == "table_analysis":
                self._update_table_meanings(data)
            elif tool_name == "er_analysis":
                self._update_er_relations(data)
            elif tool_name == "scenario_operation_generation":
                self._update_scenario_combinations(data)
            elif tool_name == "question_generation":
                self._update_current_question(data)
            elif tool_name == "sql_generation":
                self._update_current_sql(data)
        except Exception as e:
            self.logger.warning(f"Failed to update typed context for {tool_name}: {e}")
    
    def _update_legacy_memory(self, tool_name: str, data: Any) -> None:
        """更新传统字典格式记忆（向后兼容）"""
        memory_mapping = {
            "schema_extraction": "schema_info",
            "domain_analysis": "domain_info",
            "field_analysis": "field_classification",
            "column_analysis": "column_meanings",
            "table_analysis": "table_meanings",
            "er_analysis": "er_relations",
            "scenario_operation_generation": "all_scenario_combinations",
            "question_generation": "current_question",
            "sql_generation": "current_sql"
        }
        
        if tool_name in memory_mapping:
            memory_key = memory_mapping[tool_name]
            self.memories[memory_key] = data
    
    # ========== 类型化数据更新方法 ==========
    def _update_schema_info(self, data: Dict[str, Any]) -> None:
        """更新数据库结构信息"""
        schema_info = SchemaInfo(
            database_name=data.get("database_name", ""),
            tables=data.get("tables", {}),
            total_tables=len(data.get("tables", {})),
            total_columns=sum(len(table.get("columns", [])) for table in data.get("tables", {}).values()),
            relationships=data.get("relationships", [])
        )
        object.__setattr__(self.context, 'schema_info', schema_info)
    
    def _update_domain_info(self, data: Dict[str, Any]) -> None:
        """更新业务领域信息"""
        domain_info = DomainInfo(
            primary_domain=data.get("primary_domain", ""),
            secondary_domains=data.get("secondary_domains", []),
            business_concepts=data.get("business_concepts", []),
            confidence_score=data.get("confidence_score", 0.0)
        )
        object.__setattr__(self.context, 'domain_info', domain_info)
    
    def _update_field_classification(self, data: Dict[str, Any]) -> None:
        """更新字段分类信息"""
        field_classification = FieldClassification(
            field_classifications=data.get("field_classifications", {}),
            classification_stats=data.get("classification_stats", {}),
            important_fields=data.get("important_fields", [])
        )
        object.__setattr__(self.context, 'field_classification', field_classification)
    
    def _update_column_meanings(self, data: Dict[str, Any]) -> None:
        """更新列语义信息"""
        column_meanings = ColumnMeanings(
            column_meanings=data.get("column_meanings", {}),
            business_meanings=data.get("business_meanings", {}),
            semantic_groups=data.get("semantic_groups", {})
        )
        object.__setattr__(self.context, 'column_meanings', column_meanings)
    
    def _update_table_meanings(self, data: Dict[str, Any]) -> None:
        """更新表语义信息"""
        table_meanings = TableMeanings(
            table_meanings=data.get("table_meanings", {}),
            table_relationships=data.get("table_relationships", []),
            core_tables=data.get("core_tables", [])
        )
        object.__setattr__(self.context, 'table_meanings', table_meanings)
    
    def _update_er_relations(self, data: Dict[str, Any]) -> None:
        """更新实体关系信息"""
        er_relations = ERRelations(
            relationships=data.get("relationships", []),
            entities=data.get("entities", {}),
            relationship_matrix=data.get("relationship_matrix", {})
        )
        object.__setattr__(self.context, 'er_relations', er_relations)
    
    def _update_scenario_combinations(self, data: Dict[str, Any]) -> None:
        """更新场景组合信息"""
        scenario_combinations = ScenarioCombinations(
            combinations=data.get("combinations", []),
            total_combinations=data.get("total_combinations", 0),
            generation_strategy=data.get("generation_strategy", "")
        )
        object.__setattr__(self.context, 'scenario_combinations', scenario_combinations)
    
    def _update_current_question(self, data: Any) -> None:
        """更新当前问题"""
        question = data.get("question", "") if isinstance(data, dict) else str(data)
        object.__setattr__(self.context, 'current_question', question)
    
    def _update_current_sql(self, data: Any) -> None:
        """更新当前SQL"""
        sql = data.get("sql", "") if isinstance(data, dict) else str(data)
        object.__setattr__(self.context, 'current_sql', sql)
    
    # ========== 公共访问方法 ==========
    def get_typed_context(self) -> AnalysisContext:
        """获取类型化上下文"""
        return self.context
    
    def update_analysis(self, analysis_type: str, result: Dict[str, Any]) -> None:
        """更新特定类型的分析结果（向后兼容）"""
        self.memories[analysis_type] = result
        self.logger.info(f"Updated {analysis_type} in memory")
    
    def get_analysis(self, analysis_type: str) -> Dict[str, Any]:
        """获取特定类型的分析结果（向后兼容）"""
        return self.memories.get(analysis_type, {})
    
    def has_complete_analysis(self) -> bool:
        """检查是否有完整的数据库分析结果"""
        return self.context.is_analysis_complete()
    
    def get_summary(self) -> str:
        """获取记忆摘要"""
        return self.context.get_summary()