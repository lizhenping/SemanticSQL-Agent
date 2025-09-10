"""
异常定义 - SemanticSQL Agent统一异常处理
基于架构设计的标准异常体系
完全重构版本，支持极简+自主+记忆驱动架构
"""

from typing import Optional, Dict, Any


class SemanticSQLException(Exception):
    """SemanticSQL Agent基础异常类"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)
    
    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


# ========== Agent相关异常 ==========
class AgentException(SemanticSQLException):
    """Agent执行异常基类"""
    pass


class AgentInitializationError(AgentException):
    """Agent初始化失败"""
    def __init__(self, reason: str, config_details: Optional[Dict[str, Any]] = None):
        super().__init__(f"Agent初始化失败: {reason}", config_details)


class AgentExecutionError(AgentException):
    """Agent执行过程异常"""
    def __init__(self, step: str, reason: str, context: Optional[Dict[str, Any]] = None):
        message = f"Agent执行失败 - 步骤: {step}, 原因: {reason}"
        super().__init__(message, context)


class AgentMaxIterationsExceeded(AgentException):
    """Agent超过最大迭代次数"""
    def __init__(self, max_iterations: int, current_step: str):
        message = f"Agent执行超过最大迭代次数 {max_iterations}，当前步骤: {current_step}"
        super().__init__(message, {"max_iterations": max_iterations, "current_step": current_step})


class ReActParsingError(AgentException):
    """ReAct输出解析错误"""
    def __init__(self, llm_output: str, parsing_stage: str):
        message = f"ReAct输出解析失败 - 阶段: {parsing_stage}"
        super().__init__(message, {"llm_output": llm_output, "parsing_stage": parsing_stage})


# ========== 工具相关异常 ==========
class ToolException(SemanticSQLException):
    """工具执行异常基类"""
    pass


class ToolInitializationError(ToolException):
    """工具初始化失败"""
    def __init__(self, tool_name: str, reason: str):
        message = f"工具 '{tool_name}' 初始化失败: {reason}"
        super().__init__(message, {"tool_name": tool_name})


class ToolExecutionError(ToolException):
    """工具执行失败"""
    def __init__(self, tool_name: str, reason: str, input_data: Optional[Dict[str, Any]] = None):
        message = f"工具 '{tool_name}' 执行失败: {reason}"
        super().__init__(message, {"tool_name": tool_name, "input_data": input_data})


class ToolDependencyError(ToolException):
    """工具依赖缺失"""
    def __init__(self, tool_name: str, required_tool: str, missing_data: str):
        message = f"工具 '{tool_name}' 依赖缺失 - 需要工具 '{required_tool}' 的 '{missing_data}' 数据"
        details = {
            "tool_name": tool_name,
            "required_tool": required_tool, 
            "missing_data": missing_data
        }
        super().__init__(message, details)


class ToolOutputValidationError(ToolException):
    """工具输出验证失败"""
    def __init__(self, tool_name: str, validation_error: str, output_data: Optional[Any] = None):
        message = f"工具 '{tool_name}' 输出验证失败: {validation_error}"
        super().__init__(message, {"tool_name": tool_name, "output_data": str(output_data)})


# ========== 记忆系统相关异常 ==========
class MemoryException(SemanticSQLException):
    """记忆系统异常基类"""
    pass


class MemoryConnectionError(MemoryException):
    """记忆系统连接失败"""
    def __init__(self, connection_type: str, connection_params: Optional[Dict[str, Any]] = None):
        message = f"记忆系统连接失败 - 类型: {connection_type}"
        super().__init__(message, connection_params)


class TripleStorageError(MemoryException):
    """三元组存储失败"""
    def __init__(self, operation: str, reason: str, triple_data: Optional[Dict[str, Any]] = None):
        message = f"三元组 {operation} 操作失败: {reason}"
        super().__init__(message, triple_data)


class MemoryQueryError(MemoryException):
    """记忆查询失败"""
    def __init__(self, query_type: str, reason: str, query_params: Optional[Dict[str, Any]] = None):
        message = f"记忆查询失败 - 类型: {query_type}, 原因: {reason}"
        super().__init__(message, query_params)


# ========== 数据库相关异常 ==========
class DatabaseException(SemanticSQLException):
    """数据库操作异常基类"""
    pass


class DatabaseConnectionError(DatabaseException):
    """数据库连接失败"""
    def __init__(self, db_type: str, connection_params: Optional[Dict[str, Any]] = None):
        message = f"{db_type} 数据库连接失败"
        # 移除敏感信息
        safe_params = {}
        if connection_params:
            safe_params = {k: v for k, v in connection_params.items() if k not in ['password', 'api_key']}
        super().__init__(message, safe_params)


class SQLExecutionError(DatabaseException):
    """SQL执行失败"""
    def __init__(self, sql: str, reason: str, error_code: Optional[str] = None):
        message = f"SQL执行失败: {reason}"
        details = {"sql": sql}
        if error_code:
            details["error_code"] = error_code
        super().__init__(message, details)


class SchemaExtractionError(DatabaseException):
    """数据库结构提取失败"""
    def __init__(self, database_name: str, reason: str):
        message = f"数据库 '{database_name}' 结构提取失败: {reason}"
        super().__init__(message, {"database_name": database_name})


# ========== LLM相关异常 ==========
class LLMException(SemanticSQLException):
    """LLM相关异常基类"""
    pass


class LLMConnectionError(LLMException):
    """LLM连接失败"""
    def __init__(self, provider: str, reason: str):
        message = f"LLM连接失败 - 提供商: {provider}, 原因: {reason}"
        super().__init__(message, {"provider": provider})


class LLMResponseError(LLMException):
    """LLM响应异常"""
    def __init__(self, reason: str, prompt: Optional[str] = None, response: Optional[str] = None):
        message = f"LLM响应异常: {reason}"
        details = {}
        if prompt:
            details["prompt"] = prompt[:500] + "..." if len(prompt) > 500 else prompt
        if response:
            details["response"] = response[:500] + "..." if len(response) > 500 else response
        super().__init__(message, details)


class LLMTimeoutError(LLMException):
    """LLM请求超时"""
    def __init__(self, timeout_seconds: int, operation: str):
        message = f"LLM请求超时 - 操作: {operation}, 超时时间: {timeout_seconds}秒"
        super().__init__(message, {"timeout_seconds": timeout_seconds, "operation": operation})




# ========== 配置相关异常 ==========
class ConfigurationException(SemanticSQLException):
    """配置异常基类"""
    pass


class MissingConfigurationError(ConfigurationException):
    """缺少必需配置"""
    def __init__(self, config_key: str, component: str):
        message = f"组件 '{component}' 缺少必需配置: {config_key}"
        super().__init__(message, {"config_key": config_key, "component": component})


class InvalidConfigurationError(ConfigurationException):
    """无效配置"""
    def __init__(self, config_key: str, value: Any, reason: str):
        message = f"配置 '{config_key}' 值无效: {reason}"
        super().__init__(message, {"config_key": config_key, "value": str(value)})




# ========== 数据验证异常 ==========
class ValidationException(SemanticSQLException):
    """数据验证异常基类"""
    pass


class TripleValidationError(ValidationException):
    """三元组数据验证失败"""
    def __init__(self, field: str, value: Any, reason: str):
        message = f"三元组字段 '{field}' 验证失败: {reason}"
        super().__init__(message, {"field": field, "value": str(value)})


class InputValidationError(ValidationException):
    """输入数据验证失败"""
    def __init__(self, input_type: str, reason: str, input_data: Optional[Any] = None):
        message = f"{input_type} 输入验证失败: {reason}"
        super().__init__(message, {"input_type": input_type, "input_data": str(input_data)})


# ========== 业务逻辑异常 ==========
class BusinessLogicException(SemanticSQLException):
    """业务逻辑异常基类"""
    pass


class SQLGenerationError(BusinessLogicException):
    """SQL生成失败"""
    def __init__(self, question: str, reason: str, context: Optional[Dict[str, Any]] = None):
        message = f"SQL生成失败 - 问题: '{question}', 原因: {reason}"
        super().__init__(message, context)


class QuestionGenerationError(BusinessLogicException):
    """问题生成失败"""
    def __init__(self, scenario: str, reason: str, context: Optional[Dict[str, Any]] = None):
        message = f"问题生成失败 - 场景: '{scenario}', 原因: {reason}"
        super().__init__(message, context)


class QualityAssessmentError(BusinessLogicException):
    """质量评估失败"""
    def __init__(self, item_type: str, reason: str, item_data: Optional[Any] = None):
        message = f"{item_type} 质量评估失败: {reason}"
        super().__init__(message, {"item_type": item_type, "item_data": str(item_data)})


# ========== 便利函数 ==========
def raise_tool_error(tool_name: str, reason: str, input_data: Optional[Dict[str, Any]] = None) -> None:
    """快速抛出工具执行异常"""
    raise ToolExecutionError(tool_name, reason, input_data)


def raise_dependency_error(tool_name: str, required_tool: str, missing_data: str) -> None:
    """快速抛出工具依赖异常"""
    raise ToolDependencyError(tool_name, required_tool, missing_data)


def raise_memory_error(operation: str, reason: str, data: Optional[Dict[str, Any]] = None) -> None:
    """快速抛出记忆系统异常"""
    raise TripleStorageError(operation, reason, data)


def raise_validation_error(field: str, value: Any, reason: str) -> None:
    """快速抛出验证异常"""
    raise TripleValidationError(field, value, reason)