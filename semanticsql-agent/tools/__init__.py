"""
trae_agent风格的工具系统
"""

from .trae_base_tool import (
    TraeBaseTool,
    ToolParameter,
    ToolRegistry,
    register_tool,
    get_tool,
    list_tools,
    get_all_schemas
)

from .sql_tools import (
    SchemaExtractionTool,
    SQLGenerationTool,
    SQLValidationTool,
    SQLExecutionTool
)

from .analysis_tools import (
    DomainAnalysisTool,
    FieldClassificationTool,
    ERAnalysisTool,
    SequentialThinkingTool
)

# 工具工厂
class ToolFactory:
    """工具工厂类"""
    
    @staticmethod
    def create_tools(config, enabled_tools: list = None) -> list:
        """根据配置创建工具实例"""
        from ..config.database_models import DatabaseConfig
        import logging
        
        tools = []
        enabled_tools = enabled_tools or [
            "extract_schema",
            "generate_sql",
            "validate_sql",
            "execute_sql",
            "analyze_domain",
            "classify_fields",
            "analyze_relationships",
            "sequential_thinking"
        ]
        
        tool_map = {
            "extract_schema": lambda: SchemaExtractionTool(config.database),
            "generate_sql": lambda: SQLGenerationTool(config.database),
            "validate_sql": lambda: SQLValidationTool(config.database),
            "execute_sql": lambda: SQLExecutionTool(config.database),
            "analyze_domain": lambda: DomainAnalysisTool(config.database),
            "classify_fields": lambda: FieldClassificationTool(config.database),
            "analyze_relationships": lambda: ERAnalysisTool(config.database),
            "sequential_thinking": lambda: SequentialThinkingTool()
        }
        
        for tool_name in enabled_tools:
            if tool_name in tool_map:
                try:
                    tool = tool_map[tool_name]()
                    tools.append(tool)
                except Exception as e:
                    logging.getLogger(__name__).error(f"创建工具 {tool_name} 失败: {e}")
        
        return tools

__all__ = [
    # 基础类
    "TraeBaseTool",
    "ToolParameter",
    "ToolRegistry",
    
    # 工具函数
    "register_tool",
    "get_tool",
    "list_tools",
    "get_all_schemas",
    "ToolFactory",
    
    # SQL工具
    "SchemaExtractionTool",
    "SQLGenerationTool",
    "SQLValidationTool",
    "SQLExecutionTool",
    
    # 分析工具
    "DomainAnalysisTool",
    "FieldClassificationTool",
    "ERAnalysisTool",
    "SequentialThinkingTool"
]