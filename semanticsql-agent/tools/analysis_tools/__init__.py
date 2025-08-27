"""分析工具集"""

from typing import List
from langchain.tools import BaseTool

from .schema_extraction_tool import SchemaExtractionTool
from .domain_analysis_tool import DomainAnalysisTool
from .field_classification_tool import FieldClassificationTool
from .er_analysis_tool import ERAnalysisTool


def create_analysis_tools(db, llm) -> List[BaseTool]:
    """创建分析工具集"""
    return [
        SchemaExtractionTool(db=db),
        DomainAnalysisTool(db=db, llm=llm),
        FieldClassificationTool(db=db, llm=llm),
        ERAnalysisTool(db=db, llm=llm)
    ]


__all__ = [
    "SchemaExtractionTool",
    "DomainAnalysisTool", 
    "FieldClassificationTool",
    "ERAnalysisTool",
    "create_analysis_tools"
]