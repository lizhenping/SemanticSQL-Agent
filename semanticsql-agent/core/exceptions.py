"""
自定义异常类定义
"""


class SemanticSQLError(Exception):
    """SemanticSQL基础异常类"""
    pass


class ConfigurationError(SemanticSQLError):
    """配置错误"""
    pass


class ToolExecutionError(SemanticSQLError):
    """工具执行错误"""
    def __init__(self, tool_name: str, message: str, original_error: Exception = None):
        self.tool_name = tool_name
        self.original_error = original_error
        super().__init__(f"Tool '{tool_name}' execution failed: {message}")


class DatabaseConnectionError(SemanticSQLError):
    """数据库连接错误"""
    pass


class ValidationError(SemanticSQLError):
    """验证错误"""
    pass


class GenerationError(SemanticSQLError):
    """生成错误"""
    pass


class LLMError(SemanticSQLError):
    """LLM调用错误"""
    pass


class SchemaExtractionError(SemanticSQLError):
    """数据库结构提取错误"""
    pass


class SQLExecutionError(SemanticSQLError):
    """SQL执行错误"""
    def __init__(self, sql: str, message: str, original_error: Exception = None):
        self.sql = sql
        self.original_error = original_error
        super().__init__(f"SQL execution failed: {message}\nSQL: {sql[:200]}...")


class PromptError(SemanticSQLError):
    """提示词相关错误"""
    pass


class AgentExecutionError(SemanticSQLError):
    """智能体执行错误"""
    def __init__(self, step: str, message: str, original_error: Exception = None):
        self.step = step
        self.original_error = original_error
        super().__init__(f"Agent execution failed at step '{step}': {message}")