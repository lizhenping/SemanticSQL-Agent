"""
trae_agent风格的智能体模块
"""

# 新的trae_agent实现
from .trae_base_agent import BaseAgent, AgentState, StepState, AgentStep, AgentExecution
from .sql_agent import SQLAgent, SQLQueryResult

# 兼容旧版本
from .agent_basics import (
    AgentStepState, AgentState as OldAgentState, AgentStep, AgentExecution as OldAgentExecution,
    AgentError, LLMUsage, LLMResponse, ToolCall, ToolResult
)

__all__ = [
    # 新的trae_agent组件
    "BaseAgent",
    "AgentState",
    "StepState", 
    "AgentStep",
    "AgentExecution",
    "SQLAgent",
    "SQLQueryResult",
    
    # 兼容旧版本
    "AgentStepState",
    "OldAgentState",
    "OldAgentExecution",
    "AgentError",
    "LLMUsage",
    "LLMResponse",
    "ToolCall",
    "ToolResult"
]