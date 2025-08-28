"""智能体基础定义

参考 TRAEAgent 的 agent_basics.py，保持简洁。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime


class AgentStepState(Enum):
    """智能体步骤状态"""
    THINKING = "thinking"
    CALLING_TOOL = "calling_tool"
    REFLECTING = "reflecting"
    COMPLETED = "completed"
    ERROR = "error"


class AgentState(Enum):
    """智能体执行状态"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class LLMUsage:
    """LLM Token 使用情况"""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LLMResponse:
    """LLM 响应"""
    content: str
    model: str
    finish_reason: str
    usage: Optional[LLMUsage] = None
    tool_calls: Optional[List['ToolCall']] = None


@dataclass
class ToolCall:
    """工具调用"""
    name: str
    call_id: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    id: Optional[str] = None


@dataclass
class ToolResult:
    """工具执行结果"""
    call_id: str
    name: str
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class AgentStep:
    """智能体执行步骤"""
    step_number: int
    state: AgentStepState
    thought: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_results: Optional[List[ToolResult]] = None
    llm_response: Optional[LLMResponse] = None
    reflection: Optional[str] = None
    error: Optional[str] = None
    llm_usage: Optional[LLMUsage] = None


@dataclass
class AgentExecution:
    """智能体执行记录"""
    task: str
    steps: List[AgentStep] = field(default_factory=list)
    final_result: Optional[str] = None
    success: bool = False
    total_tokens: Optional[LLMUsage] = None
    execution_time: float = 0.0
    agent_state: AgentState = AgentState.IDLE


class AgentError(Exception):
    """智能体错误基类"""
    
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)