"""Phase 1 分析工具包（tools/analysis/）

K1~K6 六阶段知识抽取工具，全部继承 BaseSemanticTool，依赖注入：
    SchemaExtractionTool  -> K1 SchemaMetadata
    DomainAnalysisTool    -> K2 DomainKnowledge
    FieldAnalysisTool     -> K3 list[FieldClassification]
    ColumnAnalysisTool    -> K4 list[ColumnSemantics]
    TableAnalysisTool     -> K5 list[TableSemantics]
    ERAnalysisTool        -> K6 list[CrossTableRelation]

旧版 tools/analysis_tools/* 仍保留供对照，最终会在 S8 清理删除。
"""

from tools.analysis.schema_extraction import SchemaExtractionTool
from tools.analysis.domain_analysis import DomainAnalysisTool
from tools.analysis.field_analysis import FieldAnalysisTool
from tools.analysis.column_analysis import ColumnAnalysisTool
from tools.analysis.table_analysis import TableAnalysisTool
from tools.analysis.er_analysis import ERAnalysisTool

__all__ = [
    "SchemaExtractionTool",
    "DomainAnalysisTool",
    "FieldAnalysisTool",
    "ColumnAnalysisTool",
    "TableAnalysisTool",
    "ERAnalysisTool",
]
