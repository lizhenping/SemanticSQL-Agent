"""
trae_agent风格的智能体模块
"""

# 最简单的同步实现
from .base_agent import SyncBaseAgent as BaseAgent, AgentState, StepState, AgentStep, AgentExecution
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