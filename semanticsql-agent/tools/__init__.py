"""工具包（tools/）

Phase 1~3 工具，全部继承 BaseSemanticTool，依赖注入：
  tools/analysis/   Phase 1 Analysis   (K1~K6)
  tools/synthesis/  Phase 2 Generation  (q, s, r)
  tools/diagnosis/  Phase 3 Diagnosis   (S6 待迁移)
"""

from tools.base_tool import BaseSemanticTool
from tools.analysis import (
    SchemaExtractionTool,
    DomainAnalysisTool,
    FieldAnalysisTool,
    ColumnAnalysisTool,
    TableAnalysisTool,
    ERAnalysisTool,
)
from tools.synthesis import QuestionSynthTool, SQLSynthTool

__all__ = [
    "BaseSemanticTool",
    # Phase 1
    "SchemaExtractionTool",
    "DomainAnalysisTool",
    "FieldAnalysisTool",
    "ColumnAnalysisTool",
    "TableAnalysisTool",
    "ERAnalysisTool",
    # Phase 2
    "QuestionSynthTool",
    "SQLSynthTool",
]
