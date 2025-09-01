"""
Custom exception classes for SemanticSQL Agent
所有异常都继承自 SemanticSQLException 基类
文件位置：models/exceptions.py
"""

from typing import Any, Dict, Optional


class SemanticSQLException(Exception):
    """SemanticSQL 基础异常类"""
    def __init__(self, message: str, error_code: str = None, details: Dict[str, Any] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "UNKNOWN"
        self.details = details or {}


# 配置相关异常
class ConfigurationError(SemanticSQLException):
    """配置错误"""
    pass


class MissingConfigError(ConfigurationError):
    """缺少必需配置"""
    def __init__(self, config_name: str):
        super().__init__(
            f"Missing required configuration: {config_name}",
            error_code="CONFIG_001"
        )


class InvalidConfigError(ConfigurationError):
    """配置值无效"""
    def __init__(self, config_name: str, value: Any, expected: str):
        super().__init__(
            f"Invalid configuration value for {config_name}: {value} (expected: {expected})",
            error_code="CONFIG_002"
        )


# 数据库相关异常
class DatabaseError(SemanticSQLException):
    """数据库操作错误基类"""
    pass


class DatabaseConnectionError(DatabaseError):
    """数据库连接错误"""
    def __init__(self, host: str, database: str, original_error: Exception):
        super().__init__(
            f"Failed to connect to database {database} at {host}",
            error_code="DB_001",
            details={"host": host, "database": database, "error": str(original_error)}
        )


class SQLExecutionError(DatabaseError):
    """SQL 执行错误"""
    def __init__(self, sql: str, error: str):
        super().__init__(
            f"SQL execution failed: {error}",
            error_code="DB_002",
            details={"sql": sql, "error": error}
        )


class SchemaExtractionError(DatabaseError):
    """Schema 提取错误"""
    def __init__(self, database: str = None, error: str = None):
        message = "Failed to extract schema"
        if database:
            message += f" for database {database}"
        if error:
            message += f": {error}"
        super().__init__(message, error_code="DB_003")


# LLM 相关异常
class LLMError(SemanticSQLException):
    """LLM 调用错误基类"""
    def __init__(self, model: str, reason: str, **kwargs):
        super().__init__(
            f"LLM call failed for model {model}: {reason}",
            error_code="LLM_001",
            details={"model": model, **kwargs}
        )


class LLMConnectionError(LLMError):
    """LLM 连接错误"""
    def __init__(self, model: str, endpoint: str, error: str):
        super().__init__(
            model=model,
            reason=f"Connection to {endpoint} failed: {error}",
            endpoint=endpoint
        )
        self.error_code = "LLM_002"


class LLMResponseError(LLMError):
    """LLM 响应错误"""
    def __init__(self, model: str, status_code: int, error: str):
        super().__init__(
            model=model,
            reason=f"Invalid response (status {status_code}): {error}",
            status_code=status_code
        )
        self.error_code = "LLM_003"


class LLMTimeoutError(LLMError):
    """LLM 超时错误"""
    def __init__(self, model: str, timeout: int):
        super().__init__(
            model=model,
            reason=f"Request timeout after {timeout} seconds",
            timeout=timeout
        )
        self.error_code = "LLM_004"


# 工具相关异常
class ToolError(SemanticSQLException):
    """工具执行错误基类"""
    pass


class ToolExecutionError(ToolError):
    """工具执行失败"""
    def __init__(self, tool_name: str, reason: str, original_error: Exception = None):
        super().__init__(
            f"Tool '{tool_name}' failed: {reason}",
            error_code="TOOL_001",
            details={"tool": tool_name, "original_error": str(original_error) if original_error else None}
        )
        self.tool_name = tool_name
        self.original_error = original_error


class ToolParameterError(ToolError):
    """工具参数错误"""
    def __init__(self, tool_name: str, param_name: str, message: str):
        super().__init__(
            f"Invalid parameter '{param_name}' for tool '{tool_name}': {message}",
            error_code="TOOL_002",
            details={"tool": tool_name, "parameter": param_name}
        )


# Agent 相关异常
class AgentError(SemanticSQLException):
    """Agent 执行错误基类"""
    pass


class AgentExecutionError(AgentError):
    """Agent 执行失败"""
    def __init__(self, step: str, reason: str, **kwargs):
        super().__init__(
            f"Agent execution failed at step '{step}': {reason}",
            error_code="AGENT_001",
            details={"step": step, **kwargs}
        )


class MaxIterationsError(AgentError):
    """达到最大迭代次数"""
    def __init__(self, max_iterations: int):
        super().__init__(
            f"Agent reached maximum iterations limit: {max_iterations}",
            error_code="AGENT_002"
        )


# 验证相关异常
class ValidationError(SemanticSQLException):
    """验证错误基类"""
    pass


class SQLValidationError(ValidationError):
    """SQL 验证失败"""
    def __init__(self, sql: str, errors: list):
        super().__init__(
            f"SQL validation failed with {len(errors)} errors",
            error_code="VAL_001",
            details={"sql": sql, "errors": errors}
        )


class DataValidationError(ValidationError):
    """数据验证失败"""
    def __init__(self, field: str, value: Any, expected: str):
        super().__init__(
            f"Data validation failed for field '{field}': expected {expected}, got {type(value).__name__}",
            error_code="VAL_002"
        )