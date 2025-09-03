"""
分析工具包 - 数据库分析相关工具

工具执行顺序和Memory依赖关系：
1. SchemaExtractionTool - 提取数据库结构，保存到 memory["schema_info"]
2. DomainAnalysisTool - 分析业务领域，需要 memory["schema_info"]，保存到 memory["domain_info"]
3. FieldClassificationTool - 字段分类，需要 memory["schema_info"] 和 memory["domain_info"]，保存到 memory["field_classification"]
4. ColumnMeaningTool - 列含义分析，需要上述所有memory，保存到 memory["column_meanings"]
5. TableMeaningTool - 表含义分析，需要上述memory，保存到 memory["table_meanings"]
6. ERAnalysisTool - 关系分析，需要所有memory，保存到 memory["er_relations"]
"""

from .schema_extraction_tool import SchemaExtractionTool
from .domain_analysis_tool import DomainAnalysisTool
from .field_classification_tool import FieldClassificationTool
from .column_meaning_tool import ColumnMeaningTool
from .table_meaning_tool import TableMeaningTool
from .er_analysis_tool import ERAnalysisTool

__all__ = [
    "SchemaExtractionTool",
    "DomainAnalysisTool", 
    "FieldClassificationTool",
    "ColumnMeaningTool",
    "TableMeaningTool",
    "ERAnalysisTool"
]