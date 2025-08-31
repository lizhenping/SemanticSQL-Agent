"""
Custom exception classes for SemanticSQL Agent
"""


class SemanticSQLError(Exception):
    """Base SemanticSQL exception class"""
    pass


class ConfigurationError(SemanticSQLError):
    """Configuration error"""
    pass


class ToolExecutionError(SemanticSQLError):
    """Tool execution error"""
    def __init__(self, tool_name: str, message: str, original_error: Exception = None):
        self.tool_name = tool_name
        self.original_error = original_error
        super().__init__(f"Tool '{tool_name}' execution failed: {message}")


class DatabaseConnectionError(SemanticSQLError):
    """Database connection error"""
    pass


class ValidationError(SemanticSQLError):
    """Validation error"""
    pass


class GenerationError(SemanticSQLError):
    """Generation error"""
    pass


class LLMError(SemanticSQLError):
    """LLM call error"""
    pass


class SchemaExtractionError(SemanticSQLError):
    """Database schema extraction error"""
    pass


class SQLExecutionError(SemanticSQLError):
    """SQL execution error"""
    def __init__(self, sql: str, message: str, original_error: Exception = None):
        self.sql = sql
        self.original_error = original_error
        super().__init__(f"SQL execution failed: {message}\nSQL: {sql[:200]}...")


class PromptError(SemanticSQLError):
    """Prompt related error"""
    pass


class AgentExecutionError(SemanticSQLError):
    """Agent execution error"""
    def __init__(self, step: str, message: str, original_error: Exception = None):
        self.step = step
        self.original_error = original_error
        super().__init__(f"Agent execution failed at step '{step}': {message}")