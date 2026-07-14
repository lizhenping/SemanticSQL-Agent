"""
异常定义模块 - SemanticSQL Agent专用异常类
只保留实际使用的异常类和辅助函数
"""

# ========== 基础异常类 ==========


class AgentException(Exception):
    """Agent基础异常类"""

    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


# ========== 具体异常类 ==========


class AgentInitializationError(AgentException):
    """Agent初始化异常"""

    pass


class AgentExecutionError(AgentException):
    """Agent执行异常"""

    def __init__(self, stage: str, message: str, details: dict = None):
        super().__init__(f"Agent执行失败 [{stage}]: {message}", details)
        self.stage = stage


class ToolExecutionError(AgentException):
    """工具执行异常"""

    def __init__(self, tool_name: str, message: str, details: dict = None):
        super().__init__(f"工具执行失败 [{tool_name}]: {message}", details)
        self.tool_name = tool_name


class DatabaseConnectionError(AgentException):
    """数据库连接异常"""

    def __init__(self, db_type: str, details: dict = None):
        super().__init__(f"数据库连接失败 [{db_type}]", details)
        self.db_type = db_type


class SQLExecutionError(AgentException):
    """SQL执行异常"""

    def __init__(self, sql: str, message: str, error_code: str = None):
        super().__init__(
            f"SQL执行失败: {message}", {"sql": sql, "error_code": error_code}
        )
        self.sql = sql
        self.error_code = error_code


class SchemaExtractionError(AgentException):
    """数据库结构提取异常"""

    def __init__(self, database: str, message: str):
        super().__init__(f"数据库结构提取失败 [{database}]: {message}")
        self.database = database


class LLMException(AgentException):
    """LLM相关异常"""

    pass


class MemoryConnectionError(AgentException):
    """记忆系统连接异常"""

    def __init__(self, memory_type: str, details: dict = None):
        super().__init__(f"记忆系统连接失败 [{memory_type}]", details)
        self.memory_type = memory_type


class MemoryQueryError(AgentException):
    """记忆查询异常"""

    def __init__(self, query_type: str, message: str, details: dict = None):
        super().__init__(f"记忆查询失败 [{query_type}]: {message}", details)
        self.query_type = query_type


class TripleStorageError(AgentException):
    """三元组存储异常"""

    def __init__(self, operation: str, message: str, details: dict = None):
        super().__init__(f"三元组存储失败 [{operation}]: {message}", details)
        self.operation = operation


# ========== 辅助函数 ==========


def raise_tool_error(tool_name: str, message: str, details: dict = None):
    """抛出工具执行异常的便利函数"""
    raise ToolExecutionError(tool_name, message, details)


def raise_dependency_error(tool_name: str, dependency: str, message: str):
    """抛出依赖错误的便利函数"""
    raise ToolExecutionError(
        tool_name, f"依赖检查失败 [{dependency}]: {message}", {"dependency": dependency}
    )
