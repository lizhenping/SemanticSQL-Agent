"""步骤结果模型

定义工作流中每个步骤的结果数据结构。
每个步骤都有独立的结果类，包含完整的输入、输出和中间数据。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from datetime import datetime

from .database import DatabaseSchema
from .analysis import (
    DomainKnowledge,
    FieldClassification,
    FieldEntropyInfo,
    ColumnDescription,
    TableDescription,
    ERRelationship,
    ConceptualRelationship
)

if TYPE_CHECKING:
    from ..pipelines.analysis.field_classification_pipeline import FieldInfo


@dataclass
class StepResult:
    """步骤结果基类
    
    所有步骤结果的公共属性。
    """
    step_name: str
    start_time: datetime
    end_time: datetime
    status: str  # success, failed, skipped
    error_message: Optional[str] = None
    
    @property
    def duration_seconds(self) -> float:
        """计算步骤执行时长（秒）"""
        return (self.end_time - self.start_time).total_seconds()
    
    def is_success(self) -> bool:
        """检查步骤是否成功"""
        return self.status == "success"


@dataclass
class SchemaExtractionResult(StepResult):
    """步骤1: 架构提取结果
    
    包含数据库架构信息和提取统计。
    """
    # 输出数据
    database_schema: Optional[DatabaseSchema] = None
    raw_schema_info: Optional[Dict[str, Any]] = None
    
    # 统计信息
    table_count: int = 0
    total_columns: int = 0
    extraction_stats: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """初始化后处理"""
        if self.step_name is None:
            self.step_name = "schema_extraction"


@dataclass
class DomainAnalysisResult(StepResult):
    """步骤2: 领域分析结果
    
    包含领域知识和分析过程数据。
    """
    # 输出数据
    domain_knowledge: Optional[DomainKnowledge] = None
    
    # 中间数据
    database_ddl: Optional[str] = None
    table_summaries: Dict[str, str] = field(default_factory=dict)
    field_statistics: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # 分析洞察
    analysis_insights: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """初始化后处理"""
        if self.step_name is None:
            self.step_name = "domain_analysis"


@dataclass
class FieldClassificationResult(StepResult):
    """步骤3: 字段分类结果
    
    包含字段分类、熵值信息和原始字段数据。
    """
    # 原始数据
    field_infos: List['FieldInfo'] = field(default_factory=list)
    
    # 输出数据
    field_classifications: List[FieldClassification] = field(default_factory=list)
    field_classifications_dict: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    field_entropy_info: Dict[str, FieldEntropyInfo] = field(default_factory=dict)
    
    # 统计信息
    classification_stats: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """初始化后处理"""
        if self.step_name is None:
            self.step_name = "field_classification"
    
    @property
    def total_fields(self) -> int:
        """获取字段总数"""
        return len(self.field_infos)
    
    @property
    def classified_fields(self) -> int:
        """获取已分类字段数"""
        return len(self.field_classifications)


@dataclass
class ColumnDescriptionResult(StepResult):
    """步骤4: 列描述生成结果
    
    包含列描述和生成过程数据。
    """
    # 输出数据
    column_descriptions: Dict[str, ColumnDescription] = field(default_factory=dict)
    
    # 中间数据
    table_ddls: Dict[str, str] = field(default_factory=dict)
    field_examples: Dict[str, List[Any]] = field(default_factory=dict)
    
    # 统计信息
    generation_stats: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """初始化后处理"""
        if self.step_name is None:
            self.step_name = "column_description"
    
    @property
    def described_columns(self) -> int:
        """获取已描述的列数"""
        return len(self.column_descriptions)


@dataclass
class ColumnCorrectionResult(StepResult):
    """步骤5: 列描述修正结果
    
    包含修正后的列描述和修正过程信息。
    """
    # 输出数据
    corrected_column_descriptions: Dict[str, ColumnDescription] = field(default_factory=dict)
    
    # 修正信息
    correction_candidates: List[str] = field(default_factory=list)
    corrections_made: Dict[str, str] = field(default_factory=dict)  # old -> new
    
    # 统计信息
    correction_stats: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """初始化后处理"""
        if self.step_name is None:
            self.step_name = "column_correction"
    
    @property
    def corrected_count(self) -> int:
        """获取修正的列数"""
        return len(self.corrections_made)


@dataclass
class TableDescriptionResult(StepResult):
    """步骤6: 表描述生成结果
    
    包含表描述和表关系信息。
    """
    # 输出数据
    table_descriptions: Dict[str, TableDescription] = field(default_factory=dict)
    
    # 中间数据
    table_stats: Dict[str, Any] = field(default_factory=dict)
    table_relationships: Dict[str, List[str]] = field(default_factory=dict)
    
    def __post_init__(self):
        """初始化后处理"""
        if self.step_name is None:
            self.step_name = "table_description"
    
    @property
    def described_tables(self) -> int:
        """获取已描述的表数"""
        return len(self.table_descriptions)


@dataclass
class DomainOptimizationResult(StepResult):
    """步骤7: 领域优化结果
    
    包含优化后的领域知识和优化洞察。
    """
    # 输出数据
    optimized_domain_knowledge: Optional[DomainKnowledge] = None
    
    # 优化信息
    optimization_insights: List[str] = field(default_factory=list)
    improvements_made: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """初始化后处理"""
        if self.step_name is None:
            self.step_name = "domain_optimization"


@dataclass
class ERAnalysisResult(StepResult):
    """步骤8: ER关系分析结果
    
    包含实体关系和概念关系。
    """
    # 输出数据
    er_relationships: Dict[str, List[ERRelationship]] = field(default_factory=dict)
    conceptual_relationships: List[ConceptualRelationship] = field(default_factory=list)
    
    # 统计信息
    relationship_stats: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """初始化后处理"""
        if self.step_name is None:
            self.step_name = "er_analysis"
    
    @property
    def total_relationships(self) -> int:
        """获取关系总数"""
        return sum(len(rels) for rels in self.er_relationships.values())


# 导出所有结果类
__all__ = [
    'StepResult',
    'SchemaExtractionResult',
    'DomainAnalysisResult',
    'FieldClassificationResult',
    'ColumnDescriptionResult',
    'ColumnCorrectionResult',
    'TableDescriptionResult',
    'DomainOptimizationResult',
    'ERAnalysisResult'
]