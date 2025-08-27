"""分析相关的数据模型

参考 nl2sql_pipeline 的数据模型设计，用于智能体工具的输入输出。
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Set
from enum import Enum
from datetime import datetime


# ==================== 基础枚举和模型 ====================

class FieldCategory(str, Enum):
    """字段类别枚举"""
    IDENTIFIER = "identifier"  # 标识符（如ID、编号）
    MEASURE = "measure"       # 度量（可计算的数值）
    DIMENSION = "dimension"   # 维度（分类、分组字段）
    TIMESTAMP = "timestamp"   # 时间戳
    DESCRIPTION = "description"  # 描述文本
    OTHER = "other"          # 其他


class RelationshipType(str, Enum):
    """关系类型枚举"""
    ONE_TO_ONE = "one-to-one"
    ONE_TO_MANY = "one-to-many"
    MANY_TO_ONE = "many-to-one"
    MANY_TO_MANY = "many-to-many"
    UNKNOWN = "unknown"


class RelationSource(str, Enum):
    """关系来源枚举"""
    FOREIGN_KEY = "foreign_key"
    NAMING_CONVENTION = "naming_convention"
    COMMON_FIELD = "common_field"
    DATA_CORRELATION = "data_correlation"
    LLM_INFERRED = "llm_inferred"


# ==================== Schema 提取相关模型 ====================

class SchemaExtractionInput(BaseModel):
    """Schema 提取工具的输入"""
    tables: Optional[List[str]] = Field(
        default=None,
        description="要提取的表名列表，为空则提取所有表"
    )
    include_row_count: bool = Field(
        default=True,
        description="是否包含表的行数统计"
    )
    include_foreign_keys: bool = Field(
        default=True,
        description="是否包含外键关系"
    )
    include_indexes: bool = Field(
        default=False,
        description="是否包含索引信息"
    )


class ColumnDetail(BaseModel):
    """列的详细信息"""
    name: str = Field(description="列名")
    data_type: str = Field(description="数据类型")
    is_nullable: bool = Field(default=True, description="是否可空")
    default_value: Optional[str] = Field(default=None, description="默认值")
    is_primary_key: bool = Field(default=False, description="是否主键")
    is_unique: bool = Field(default=False, description="是否唯一")
    is_foreign_key: bool = Field(default=False, description="是否外键")
    comment: Optional[str] = Field(default=None, description="列注释")


class ForeignKeyInfo(BaseModel):
    """外键信息"""
    constraint_name: str = Field(description="约束名称")
    column: str = Field(description="本表列名")
    referenced_table: str = Field(description="引用表名")
    referenced_column: str = Field(description="引用列名")


class IndexInfo(BaseModel):
    """索引信息"""
    name: str = Field(description="索引名称")
    unique: bool = Field(description="是否唯一索引")
    columns: List[str] = Field(description="索引列")


class TableDetail(BaseModel):
    """表的详细信息"""
    name: str = Field(description="表名")
    comment: Optional[str] = Field(default=None, description="表注释")
    columns: List[ColumnDetail] = Field(description="列信息")
    primary_keys: List[str] = Field(description="主键列表")
    foreign_keys: List[ForeignKeyInfo] = Field(default_factory=list, description="外键列表")
    indexes: List[IndexInfo] = Field(default_factory=list, description="索引列表")
    row_count: Optional[int] = Field(default=None, description="行数")


class SchemaExtractionOutput(BaseModel):
    """Schema 提取工具的输出"""
    database_name: str = Field(description="数据库名称")
    tables_count: int = Field(description="表数量")
    tables: List[TableDetail] = Field(description="表详情列表")
    extraction_config: Dict[str, bool] = Field(description="提取配置")
    summary: Dict[str, Any] = Field(description="提取摘要")


# ==================== 领域分析相关模型 ====================

class DomainAnalysisInput(BaseModel):
    """领域分析工具的输入"""
    schema_info: SchemaExtractionOutput = Field(
        description="数据库结构信息，通常来自 extract_database_schema 工具"
    )
    focus_tables: Optional[List[str]] = Field(
        default=None,
        description="需要重点分析的表，为空则分析所有表"
    )
    include_sample_data: bool = Field(
        default=True,
        description="是否包含样本数据以增强分析"
    )


class DomainCharacteristics(BaseModel):
    """领域特征"""
    data_volume: str = Field(description="数据量特征（大/中/小）")
    update_frequency: str = Field(description="更新频率（高/中/低）")
    data_quality: str = Field(description="数据质量评估")


class DomainKnowledge(BaseModel):
    """领域知识"""
    domain: str = Field(description="业务领域类型")
    domain_description: str = Field(description="领域的详细描述")
    core_entities: List[str] = Field(description="核心实体列表")
    entity_descriptions: Dict[str, str] = Field(default_factory=dict, description="实体描述")
    business_processes: List[str] = Field(default_factory=list, description="业务流程")
    business_rules: List[str] = Field(default_factory=list, description="业务规则")
    terminology: Dict[str, str] = Field(default_factory=dict, description="术语解释")
    data_characteristics: DomainCharacteristics = Field(description="数据特征")


class DomainAnalysisOutput(BaseModel):
    """领域分析工具的输出"""
    success: bool = Field(description="是否成功")
    database_name: str = Field(description="数据库名称")
    domain_analysis: DomainKnowledge = Field(description="领域分析结果")
    domain_knowledge: Dict[str, Any] = Field(description="领域知识详情")
    analyzed_tables: int = Field(description="分析的表数量")
    summary: str = Field(description="分析摘要")
    error: Optional[str] = Field(default=None, description="错误信息")


# ==================== 字段分类相关模型 ====================

class FieldClassificationInput(BaseModel):
    """字段分类工具的输入"""
    schema_info: SchemaExtractionOutput = Field(
        description="数据库结构信息"
    )
    domain_knowledge: Optional[DomainAnalysisOutput] = Field(
        default=None,
        description="领域知识，来自 analyze_business_domain"
    )
    sample_size: int = Field(
        default=100,
        description="每个字段的采样数量"
    )
    focus_tables: Optional[List[str]] = Field(
        default=None,
        description="需要重点分析的表"
    )


class FieldStatistics(BaseModel):
    """字段统计信息"""
    value_distribution: Dict[str, int] = Field(default_factory=dict, description="值分布")
    numeric_stats: Optional[Dict[str, float]] = Field(default=None, description="数值统计")
    length_stats: Optional[Dict[str, float]] = Field(default=None, description="长度统计")


class FieldClassification(BaseModel):
    """字段分类结果"""
    field_name: str = Field(description="字段全名（表名.列名）")
    table_name: str = Field(description="表名")
    column_name: str = Field(description="列名")
    category: FieldCategory = Field(description="字段类别")
    confidence: float = Field(description="分类置信度")
    reason: str = Field(description="分类理由")
    data_type: str = Field(description="数据类型")
    entropy: float = Field(description="熵值")
    unique_ratio: float = Field(description="唯一值比例")
    null_ratio: float = Field(description="空值比例")
    statistics: FieldStatistics = Field(description="统计信息")


class TableFieldReport(BaseModel):
    """表的字段分类报告"""
    fields: List[FieldClassification] = Field(description="字段分类列表")
    summary: Dict[str, Any] = Field(description="分类摘要")


class FieldClassificationOutput(BaseModel):
    """字段分类工具的输出"""
    success: bool = Field(description="是否成功")
    total_fields: int = Field(description="总字段数")
    classifications: Dict[str, FieldClassification] = Field(description="分类结果")
    report: Dict[str, TableFieldReport] = Field(description="表级报告")
    statistics: Dict[str, Any] = Field(description="统计信息")
    error: Optional[str] = Field(default=None, description="错误信息")


# ==================== 实体关系分析相关模型 ====================

class ERAnalysisInput(BaseModel):
    """ER 分析工具的输入"""
    schema_info: SchemaExtractionOutput = Field(
        description="数据库结构信息"
    )
    domain_knowledge: Optional[DomainAnalysisOutput] = Field(
        default=None,
        description="领域知识，来自 analyze_business_domain"
    )
    field_classifications: Optional[FieldClassificationOutput] = Field(
        default=None,
        description="字段分类结果，来自 classify_table_fields"
    )
    analyze_implicit: bool = Field(
        default=True,
        description="是否分析隐式关系（基于命名和数据）"
    )


class Relationship(BaseModel):
    """关系定义"""
    from_table: str = Field(description="源表")
    from_column: Optional[str] = Field(default=None, description="源列")
    to_table: str = Field(description="目标表")
    to_column: Optional[str] = Field(default=None, description="目标列")
    type: RelationSource = Field(description="关系来源")
    relationship_type: RelationshipType = Field(description="关系类型")
    confidence: float = Field(default=1.0, description="置信度")
    constraint_name: Optional[str] = Field(default=None, description="约束名称")
    description: Optional[str] = Field(default=None, description="关系描述")


class RelationshipGraph(BaseModel):
    """关系图谱"""
    nodes: List[str] = Field(description="节点（表）列表")
    edges: List[Dict[str, Any]] = Field(description="边（关系）列表")
    node_degrees: Dict[str, int] = Field(description="节点连接度")
    core_nodes: List[str] = Field(description="核心节点")


class RelationshipPattern(BaseModel):
    """关系模式"""
    star_schema: Optional[Dict[str, Any]] = Field(default=None, description="星型模式")
    snowflake_schema: Optional[Dict[str, Any]] = Field(default=None, description="雪花模式")
    junction_tables: List[str] = Field(default_factory=list, description="连接表")
    isolated_tables: List[str] = Field(default_factory=list, description="孤立表")
    table_clusters: List[Dict[str, Any]] = Field(default_factory=list, description="表簇")


class ERAnalysisReport(BaseModel):
    """ER 分析报告"""
    summary: Dict[str, int] = Field(description="摘要统计")
    key_findings: List[str] = Field(description="关键发现")
    recommendations: List[str] = Field(description="建议")


class ERAnalysisOutput(BaseModel):
    """ER 分析工具的输出"""
    success: bool = Field(description="是否成功")
    relationships: Dict[str, List[Relationship]] = Field(description="关系分类")
    relationship_graph: RelationshipGraph = Field(description="关系图谱")
    patterns: RelationshipPattern = Field(description="关系模式")
    report: ERAnalysisReport = Field(description="分析报告")
    statistics: Dict[str, Any] = Field(description="统计信息")
    error: Optional[str] = Field(default=None, description="错误信息")