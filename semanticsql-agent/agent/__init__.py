"""智能体模块

基于 TRAEAgent 设计理念的 SQL 查询智能体。
"""

# 基础定义
from .agent_basics import (
    AgentStepState,
    AgentState,
    AgentStep,
    AgentExecution,
    AgentError,
    ToolExecutionError,
    MaxStepsExceededError,
    LLMError,
    LLMUsage,
    LLMResponse,
    ToolCall,
    ToolResult
)

# 轨迹记录
from .trajectory_recorder import TrajectoryRecorder

# 智能体实现
from .base_agent import BaseAgent
from .sql_agent import SQLAgent
from .agent_executor import SQLAgentExecutor

__all__ = [
    # 基础类型
    "AgentStepState",
    "AgentState",
    "AgentStep",
    "AgentExecution",
    "LLMUsage",
    "LLMResponse", 
    "ToolCall",
    "ToolResult",
    # 错误类型
    "AgentError",
    "ToolExecutionError",
    "MaxStepsExceededError",
    "LLMError",
    # 轨迹记录
    "TrajectoryRecorder",
    # 智能体
    "BaseAgent",
    "SQLAgent",
    "SQLAgentExecutor"
]