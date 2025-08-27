"""验证工具集"""

from typing import List
from langchain.tools import BaseTool

from .sql_validation_tool import SQLValidationTool
from .sql_execution_tool import SQLExecutionTool


def create_validation_tools(db) -> List[BaseTool]:
    """创建验证工具集"""
    return [
        SQLValidationTool(db=db),
        SQLExecutionTool(db=db)
    ]


__all__ = [
    "SQLValidationTool",
    "SQLExecutionTool",
    "create_validation_tools"
]