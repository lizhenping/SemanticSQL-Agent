"""智能体模块

提供基于 TRAEAgent 设计的 SQL 查询智能体。
"""

from .base_agent import BaseAgent
from .sql_agent import SQLAgent
from .agent_executor import SQLAgentExecutor
from .agent_state import (
    AgentState, StepState, AgentStep, AgentExecution,
    AgentContext, AgentError, MaxStepsExceededError
)
from .trajectory import TrajectoryRecorder

__all__ = [
    # 智能体
    "BaseAgent",
    "SQLAgent",
    "SQLAgentExecutor",
    # 状态管理
    "AgentState",
    "StepState", 
    "AgentStep",
    "AgentExecution",
    "AgentContext",
    # 错误
    "AgentError",
    "MaxStepsExceededError",
    # 轨迹
    "TrajectoryRecorder"
]