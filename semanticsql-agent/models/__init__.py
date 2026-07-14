"""SemanticSQL Agent Models — 纯数据模型层（零外部依赖）

按论文 §III 三阶段组织：
- knowledge.py:  K1..K6 知识库（Phase 1 产物）
- synthesis.py:  Question/SQL/Rationale/Triple（Phase 2 产物）
- diagnosis.py:  Error/Evidence/Correction（Phase 3 产物）
"""

# K1..K6 知识库模型
from models.knowledge import (
    FieldCategory,
    ColumnInfo,
    TableInfo,
    SchemaMetadata,
    DomainKnowledge,
    FieldClassification,
    ColumnSemantics,
    TableSemantics,
    CrossTableRelation,
)

# Phase 2 生成模型
from models.synthesis import (
    GenerationMetadata,
    TableSelection,
    ColumnOperation,
    SQLStrategy,
    Rationale,
    Question,
    SQLResult,
    Triple,
)

# Phase 3 诊断模型
from models.diagnosis import (
    ErrorType,
    ErrorLocation,
    Error,
    Evidence,
    Correction,
)

__all__ = [
    # knowledge
    "FieldCategory", "ColumnInfo", "TableInfo", "SchemaMetadata",
    "DomainKnowledge", "FieldClassification", "ColumnSemantics",
    "TableSemantics", "CrossTableRelation",
    # synthesis
    "GenerationMetadata", "TableSelection", "ColumnOperation",
    "SQLStrategy", "Rationale", "Question", "SQLResult", "Triple",
    # diagnosis
    "ErrorType", "ErrorLocation", "Error", "Evidence", "Correction",
]
