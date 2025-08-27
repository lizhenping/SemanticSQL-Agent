"""思考工具集（可选）"""

from typing import List
from langchain.tools import BaseTool

from .sequential_thinking_tool import SequentialThinkingTool


def create_thinking_tools(llm) -> List[BaseTool]:
    """创建思考工具集"""
    return [
        SequentialThinkingTool(llm=llm)
    ]


__all__ = [
    "SequentialThinkingTool",
    "create_thinking_tools"
]