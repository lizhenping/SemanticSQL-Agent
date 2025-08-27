"""工具模块"""

from typing import List
from langchain.tools import BaseTool

from .analysis_tools import create_analysis_tools
from .generation_tools import create_generation_tools
from .validation_tools import create_validation_tools
from .thinking_tools import create_thinking_tools


def create_all_tools(db, llm, config: dict) -> List[BaseTool]:
    """创建所有工具"""
    tools = []
    
    # 分析工具
    tools.extend(create_analysis_tools(db, llm))
    
    # 生成工具
    tools.extend(create_generation_tools(llm))
    
    # 验证工具
    tools.extend(create_validation_tools(db))
    
    # 思考工具（可选）
    if config.get("agent", {}).get("enable_thinking", True):
        tools.extend(create_thinking_tools(llm))
    
    return tools


__all__ = [
    "create_all_tools",
    "create_analysis_tools",
    "create_generation_tools",
    "create_validation_tools",
    "create_thinking_tools"
]