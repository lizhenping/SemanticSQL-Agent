"""数据模型包

包含所有 Pydantic 数据模型定义。
"""

# 从 schemas.py 导出基础模型
from .schemas import (
    FieldType,
    ColumnInfo,
    TableInfo,
    DomainAnalysis,
    SQLValidationResult,
    QueryExecutionResult,
    QueryResult
)

# 从 analysis_models.py 导出分析相关模型
from .analysis_models import (
    # 枚举
    FieldCategory,
    RelationshipType,
    RelationSource,
    # Schema 提取
    SchemaExtractionInput,
    SchemaExtractionOutput,
    ColumnDetail,
    TableDetail,
    ForeignKeyInfo,
    IndexInfo,
    # 领域分析
    DomainAnalysisInput,
    DomainAnalysisOutput,
    DomainKnowledge,
    DomainCharacteristics,
    # 字段分类
    FieldClassificationInput,
    FieldClassificationOutput,
    FieldClassification,
    FieldStatistics,
    TableFieldReport,
    # ER 分析
    ERAnalysisInput,
    ERAnalysisOutput,
    Relationship,
    RelationshipGraph,
    RelationshipPattern,
    ERAnalysisReport
)

# 从 generation_models.py 导出生成相关模型
from .generation_models import (
    # SQL 生成
    SQLGenerationInput,
    SQLGenerationOutput,
    # SQL 验证
    SQLValidationType,
    SQLValidationInput,
    SQLValidationOutput,
    ValidationIssue,
    # SQL 执行
    SQLExecutionInput,
    SQLExecutionOutput,
    # 思考工具
    ThinkingInput,
    ThinkingOutput,
    ThinkingStep
)

__all__ = [
    # 基础模型
    "FieldType",
    "ColumnInfo",
    "TableInfo",
    "DomainAnalysis",
    "SQLValidationResult",
    "QueryExecutionResult",
    "QueryResult",
    # 分析模型
    "FieldCategory",
    "RelationshipType",
    "RelationSource",
    "SchemaExtractionInput",
    "SchemaExtractionOutput",
    "ColumnDetail",
    "TableDetail",
    "ForeignKeyInfo",
    "IndexInfo",
    "DomainAnalysisInput",
    "DomainAnalysisOutput",
    "DomainKnowledge",
    "DomainCharacteristics",
    "FieldClassificationInput",
    "FieldClassificationOutput",
    "FieldClassification",
    "FieldStatistics",
    "TableFieldReport",
    "ERAnalysisInput",
    "ERAnalysisOutput",
    "Relationship",
    "RelationshipGraph",
    "RelationshipPattern",
    "ERAnalysisReport"
]