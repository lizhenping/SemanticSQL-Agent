"""数据模型模块"""

from .schemas import (
    FieldType,
    TableInfo,
    ColumnInfo,
    DomainAnalysis,
    QueryResult,
    SQLValidationResult
)

__all__ = [
    "FieldType",
    "TableInfo", 
    "ColumnInfo",
    "DomainAnalysis",
    "QueryResult",
    "SQLValidationResult"
]