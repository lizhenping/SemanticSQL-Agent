"""工具模块

提供 SemanticSQL Agent 的所有工具。
"""

from typing import List
from langchain.tools import BaseTool

# 基类
from .base import BaseSemanticSQLTool, ToolExecResult, ToolParameter

# 分析工具
from .analysis_tools import (
    SchemaExtractionTool,
    DomainAnalysisTool,
    FieldClassificationTool,
    ERAnalysisTool,
    create_analysis_tools
)

# 生成工具
from .generation_tools import (
    SQLGenerationTool,
    create_generation_tools
)

# 验证工具
from .validation_tools import (
    SQLValidationTool,
    SQLExecutionTool,
    create_validation_tools
)

# 思考工具
from .thinking_tools import (
    SequentialThinkingTool,
    create_thinking_tools
)


def create_all_tools(db, llm, config: dict) -> List[BaseTool]:
    """创建所有工具"""
    tools = []
    
    # 分析工具
    tools.extend(create_analysis_tools(db, llm))
    
    # 生成工具
    tools.extend(create_generation_tools(db, llm))
    
    # 验证工具
    tools.extend(create_validation_tools(db))
    
    # 思考工具（可选）
    if config.get("agent", {}).get("enable_thinking", True):
        tools.extend(create_thinking_tools(llm))
    
    return tools


__all__ = [
    # 基类
    "BaseSemanticSQLTool",
    "ToolExecResult",
    "ToolParameter",
    # 分析工具
    "SchemaExtractionTool",
    "DomainAnalysisTool", 
    "FieldClassificationTool",
    "ERAnalysisTool",
    # 生成工具
    "SQLGenerationTool",
    # 验证工具
    "SQLValidationTool",
    "SQLExecutionTool",
    # 思考工具
    "SequentialThinkingTool",
    # 工厂函数
    "create_all_tools",
    "create_analysis_tools",
    "create_generation_tools",
    "create_validation_tools",
    "create_thinking_tools"
]