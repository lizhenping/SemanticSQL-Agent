"""
trae_agent风格的智能体模块
"""

# 最简单的同步实现
from .base_agent import SyncBaseAgent as BaseAgent, AgentState, StepState, AgentStep, AgentExecution
from .sql_agent import SQLAgent
from .sql_result import SQLQueryResult
from .smart_sql_agent import SmartSQLAgent, SmartAnalysisResult

# 从基础模块导入需要的类型
from utils.llm_clients.llm_basics import LLMUsage, LLMResponse, ToolCall, ToolResult

__all__ = [
    # 新的trae_agent组件
    "BaseAgent",
    "AgentState",
    "StepState", 
    "AgentStep",
    "AgentExecution",
    "SQLAgent",
    "SQLQueryResult",
    "SmartSQLAgent",
    "SmartAnalysisResult",
    
    # LLM相关类型
    "LLMUsage",
    "LLMResponse",
    "ToolCall",
    "ToolResult"
]