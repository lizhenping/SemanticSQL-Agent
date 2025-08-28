"""智能体基础定义

参考 TRAEAgent 的 agent_basics.py，定义核心数据结构。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any, Union
from datetime import datetime


class AgentStepState(Enum):
    """智能体步骤状态"""
    THINKING = "thinking"
    CALLING_TOOL = "calling_tool"  # 不是 ACTING
    REFLECTING = "reflecting"       # 独立的反思状态
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
    cache_read_tokens: Optional[int] = None
    cache_creation_tokens: Optional[int] = None
    
    def __add__(self, other: 'LLMUsage') -> 'LLMUsage':
        """合并两个使用统计"""
        return LLMUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            cache_read_tokens=(self.cache_read_tokens or 0) + (other.cache_read_tokens or 0),
            cache_creation_tokens=(self.cache_creation_tokens or 0) + (other.cache_creation_tokens or 0)
        )


@dataclass
class LLMResponse:
    """LLM 响应"""
    content: str
    model: str
    finish_reason: str
    usage: Optional[LLMUsage] = None
    tool_calls: Optional[List['ToolCall']] = None
    raw_response: Optional[Any] = None  # 原始响应对象


@dataclass
class ToolCall:
    """工具调用"""
    name: str
    call_id: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    id: Optional[str] = None
    
    def __str__(self) -> str:
        return f"ToolCall(name={self.name}, arguments={self.arguments}, call_id={self.call_id})"


@dataclass
class ToolResult:
    """工具执行结果"""
    call_id: str
    name: str
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    id: Optional[str] = None
    execution_time: float = 0.0
    
    def __str__(self) -> str:
        if self.success:
            return f"ToolResult(name={self.name}, success=True, result={str(self.result)[:100]}...)"
        else:
            return f"ToolResult(name={self.name}, success=False, error={self.error})"


@dataclass
class AgentStep:
    """智能体执行步骤
    
    对应 ReAct 模式的一个循环，但支持批量工具调用和独立反思。
    """
    step_number: int
    state: AgentStepState
    thought: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None      # 支持多个工具调用
    tool_results: Optional[List[ToolResult]] = None  # 支持多个结果
    llm_response: Optional[LLMResponse] = None       # 完整的 LLM 响应
    reflection: Optional[str] = None                 # 反思内容
    error: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None           # 额外信息
    llm_usage: Optional[LLMUsage] = None            # 本步骤的 token 使用
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __repr__(self) -> str:
        return (
            f"<AgentStep #{self.step_number} "
            f"state={self.state.name} "
            f"thought={repr(self.thought)[:40] if self.thought else 'None'}...>"
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "step_number": self.step_number,
            "state": self.state.value,
            "thought": self.thought,
            "tool_calls": [
                {
                    "name": tc.name,
                    "call_id": tc.call_id,
                    "arguments": tc.arguments
                } for tc in (self.tool_calls or [])
            ],
            "tool_results": [
                {
                    "name": tr.name,
                    "call_id": tr.call_id,
                    "success": tr.success,
                    "result": str(tr.result) if tr.result else None,
                    "error": tr.error
                } for tr in (self.tool_results or [])
            ],
            "reflection": self.reflection,
            "error": self.error,
            "llm_usage": {
                "input_tokens": self.llm_usage.input_tokens,
                "output_tokens": self.llm_usage.output_tokens,
                "total_tokens": self.llm_usage.total_tokens
            } if self.llm_usage else None,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class AgentExecution:
    """智能体执行记录
    
    封装整个任务的执行过程。
    """
    task: str
    steps: List[AgentStep] = field(default_factory=list)
    final_result: Optional[str] = None
    success: bool = False
    total_tokens: Optional[LLMUsage] = None
    execution_time: float = 0.0
    agent_state: AgentState = AgentState.IDLE
    error: Optional[str] = None
    
    # 元数据
    provider: Optional[str] = None
    model: Optional[str] = None
    max_steps: int = 10
    
    # 时间戳
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    def __repr__(self) -> str:
        return (
            f"<AgentExecution task={self.task!r} "
            f"steps={len(self.steps)} "
            f"success={self.success}>"
        )
    
    def add_step(self, step: AgentStep) -> None:
        """添加执行步骤"""
        self.steps.append(step)
        
        # 累积 token 使用
        if step.llm_usage:
            if self.total_tokens is None:
                self.total_tokens = LLMUsage()
            self.total_tokens = self.total_tokens + step.llm_usage
    
    def get_last_step(self) -> Optional[AgentStep]:
        """获取最后一个步骤"""
        return self.steps[-1] if self.steps else None
    
    @property
    def total_steps(self) -> int:
        """总步骤数"""
        return len(self.steps)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task": self.task,
            "success": self.success,
            "agent_state": self.agent_state.value,
            "total_steps": self.total_steps,
            "execution_time": self.execution_time,
            "error": self.error,
            "provider": self.provider,
            "model": self.model,
            "max_steps": self.max_steps,
            "final_result": self.final_result,
            "total_tokens": {
                "input_tokens": self.total_tokens.input_tokens,
                "output_tokens": self.total_tokens.output_tokens,
                "total_tokens": self.total_tokens.total_tokens
            } if self.total_tokens else None,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "steps": [step.to_dict() for step in self.steps]
        }


class AgentError(Exception):
    """智能体相关错误的基类"""
    
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)
    
    def __repr__(self) -> str:
        return f"<AgentError message={self.message!r}>"


class ToolExecutionError(AgentError):
    """工具执行错误"""
    pass


class MaxStepsExceededError(AgentError):
    """超过最大步骤数错误"""
    pass


class LLMError(AgentError):
    """LLM 调用错误"""
    pass