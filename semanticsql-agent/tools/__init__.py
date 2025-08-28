"""工具模块

提供 SemanticSQL Agent 的所有工具。
"""

# 基类
from .base import Tool, ToolExecResult, ToolParameter

# 工具实现
from .schema_extraction import SchemaExtractionTool
from .domain_analysis import DomainAnalysisTool
from .field_classification import FieldClassificationTool
from .er_analysis import ERAnalysisTool
from .sql_generation import SQLGenerationTool
from .sql_execution import SQLExecutionTool
from .sql_validation import SQLValidationTool
from .sequential_thinking import SequentialThinkingTool


__all__ = [
    # 基类
    "Tool",
    "ToolExecResult",
    "ToolParameter",
    # 工具
    "SchemaExtractionTool",
    "DomainAnalysisTool", 
    "FieldClassificationTool",
    "ERAnalysisTool",
    "SQLGenerationTool",
    "SQLExecutionTool",
    "SQLValidationTool",
    "SequentialThinkingTool",
    # 工具注册表
    "tools_registry"
]

# 工具注册表 - 参考 trae_agent 的设计模式
tools_registry: dict[str, type[Tool]] = {
    "schema_extraction": SchemaExtractionTool,
    "domain_analysis": DomainAnalysisTool,
    "field_classification": FieldClassificationTool,
    "er_analysis": ERAnalysisTool,
    "sql_generation": SQLGenerationTool,
    "sql_execution": SQLExecutionTool,
    "sql_validation": SQLValidationTool,
    "sequential_thinking": SequentialThinkingTool,
}