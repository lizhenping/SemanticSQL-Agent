"""生成工具集"""

from typing import List
from langchain.tools import BaseTool

from .sql_generation_tool import SQLGenerationTool


def create_generation_tools(llm) -> List[BaseTool]:
    """创建生成工具集"""
    return [
        SQLGenerationTool(llm=llm)
    ]


__all__ = [
    "SQLGenerationTool",
    "create_generation_tools"
]