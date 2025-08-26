"""管道上下文模型定义

本模块集中定义所有分析管道使用的上下文类，
避免在各个管道中重复定义，提高代码的可维护性。
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set, TYPE_CHECKING

from .database import DatabaseSchema, TableInfo, ColumnInfo
from .analysis import (
    DomainKnowledge,
    FieldClassification,
    FieldEntropyInfo,
    ColumnDescription,
    TableDescription,
    ERRelationship
)

if TYPE_CHECKING:
    from ..services import DatabaseService, LLMService, PromptService
    from .pipeline_common import FieldInfo


@dataclass
class BaseContext:
    """所有管道上下文的基类
    
    包含所有管道共享的基础字段，如数据库信息和服务引用。
    """
    database_name: str
    
    # 服务引用（可选，因为某些管道可能不需要所有服务）
    database_service: Optional['DatabaseService'] = None
    llm_service: Optional['LLMService'] = None
    prompt_service: Optional['PromptService'] = None


@dataclass
class SchemaExtractionContext:
    """架构提取管道的上下文
    
    注意：这个上下文不继承 BaseContext，因为在架构提取时还没有 database_name
    """
    database_config: Dict[str, Any]
    database_service: Optional['DatabaseService'] = None
    database_schema: Optional[DatabaseSchema] = None
    raw_schema_info: Optional[Dict[str, Any]] = None


@dataclass
class DomainAnalysisContext(BaseContext):
    """领域分析管道的上下文
    
    用于分析数据库的业务领域和生成领域知识。
    """
    database_schema: Optional[DatabaseSchema] = None
    
    # 中间结果
    database_ddl: str = ""
    table_summaries: Dict[str, str] = field(default_factory=dict)
    field_statistics: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # 最终结果
    domain_knowledge: Optional[DomainKnowledge] = None


@dataclass
class FieldClassificationContext(BaseContext):
    """字段分类管道的上下文
    
    用于对数据库字段进行分类和熵值计算。
    """
    database_schema: Optional[DatabaseSchema] = None
    domain_knowledge: Optional[DomainKnowledge] = None
    
    # 字段信息
    field_infos: List['FieldInfo'] = field(default_factory=list)
    
    # 分类结果
    field_classifications: List[FieldClassification] = field(default_factory=list)
    classification_stats: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ColumnDescriptionContext(BaseContext):
    """列描述生成管道的上下文
    
    用于为数据库列生成业务描述。
    """
    database_schema: Optional[DatabaseSchema] = None
    domain_knowledge: Optional[DomainKnowledge] = None
    field_classifications: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    field_entropy_info: Dict[str, FieldEntropyInfo] = field(default_factory=dict)
    column_descriptions: Dict[str, ColumnDescription] = field(default_factory=dict)
    table_descriptions: Dict[str, TableDescription] = field(default_factory=dict)
    batch_size: int = 10
    
    # 中间数据
    table_ddls: Dict[str, str] = field(default_factory=dict)
    field_examples: Dict[str, List[Any]] = field(default_factory=dict)


@dataclass
class ColumnCorrectionContext(BaseContext):
    """列描述修正管道的上下文
    
    用于修正和优化生成的列描述。
    """
    database_schema: Optional[DatabaseSchema] = None
    domain_knowledge: Optional[DomainKnowledge] = None
    column_descriptions: Dict[str, ColumnDescription] = field(default_factory=dict)
    field_classifications: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # 修正相关
    correction_candidates: Set[str] = field(default_factory=set)
    corrected_columns: Set[str] = field(default_factory=set)
    correction_stats: Dict[str, int] = field(default_factory=dict)


@dataclass
class TableDescriptionContext(BaseContext):
    """表描述生成管道的上下文
    
    用于为数据库表生成业务描述。
    """
    database_schema: Optional[DatabaseSchema] = None
    domain_knowledge: Optional[DomainKnowledge] = None
    column_descriptions: Dict[str, ColumnDescription] = field(default_factory=dict)
    table_descriptions: Dict[str, TableDescription] = field(default_factory=dict)
    table_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class DomainOptimizationContext(BaseContext):
    """领域优化管道的上下文
    
    用于基于生成的描述优化领域知识。
    """
    database_schema: Optional[DatabaseSchema] = None
    initial_domain_knowledge: Optional[DomainKnowledge] = None
    table_descriptions: Dict[str, TableDescription] = field(default_factory=dict)
    column_descriptions: Dict[str, ColumnDescription] = field(default_factory=dict)
    field_classifications: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # 优化结果
    optimized_domain_knowledge: Optional[DomainKnowledge] = None
    optimization_insights: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ERAnalysisContext(BaseContext):
    """ER关系分析管道的上下文
    
    用于分析数据库中的实体关系。
    """
    database_schema: Optional[DatabaseSchema] = None
    domain_knowledge: Optional[DomainKnowledge] = None
    field_classifications: Optional[List[FieldClassification]] = None
    table_descriptions: Optional[Dict[str, TableDescription]] = None
    column_descriptions: Optional[Dict[str, Any]] = None
    
    # 分析结果
    physical_relations: List[Any] = field(default_factory=list)
    logical_relations: List[Any] = field(default_factory=list)
    conceptual_relations: List[Any] = field(default_factory=list)
    er_analysis_result: Optional[Any] = None
    er_relationships: Dict[str, List[ERRelationship]] = field(default_factory=dict)
    
    # 中间数据
    relationship_graph: Dict[str, Set[str]] = field(default_factory=dict)
    entity_types: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        """初始化默认值"""
        if self.domain_knowledge is None:
            from .analysis import DomainKnowledge
            self.domain_knowledge = DomainKnowledge(
                domain_type="未知",
                description="待分析"
            )