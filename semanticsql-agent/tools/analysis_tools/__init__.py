"""分析工具集

基于 nl2sql_pipeline 的分析逻辑，但使用智能体工具模式实现。
"""

from typing import List
from langchain.tools import BaseTool

from .schema_extraction_tool import SchemaExtractionTool
from .domain_analysis_tool import DomainAnalysisTool
from .field_classification_tool import FieldClassificationTool
from .er_analysis_tool import ERAnalysisTool


def create_analysis_tools(db, llm) -> List[BaseTool]:
    """创建分析工具集
    
    按照 nl2sql_pipeline 的分析流程顺序：
    1. Schema 提取
    2. 领域分析
    3. 字段分类
    4. 实体关系分析
    """
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