"""智能体状态管理

参考 TRAEAgent 的设计，定义智能体的状态和执行步骤。
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime

from models import QueryExecutionResult
from tools.base import ToolCall, ToolResult


class AgentState(Enum):
    """智能体状态"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


class StepState(Enum):
    """步骤状态 - ReAct 模式"""
    THINKING = "thinking"      # 思考阶段
    ACTING = "acting"         # 执行工具阶段
    OBSERVING = "observing"   # 观察结果阶段
    COMPLETED = "completed"   # 步骤完成
    ERROR = "error"          # 步骤错误


@dataclass
class AgentStep:
    """智能体执行步骤
    
    对应 ReAct 模式的一个完整循环：Thought -> Action -> Observation
    """
    step_number: int
    state: StepState = StepState.THINKING
    thought: Optional[str] = None
    action: Optional[ToolCall] = None
    observation: Optional[ToolResult] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "step_number": self.step_number,
            "state": self.state.value,
            "thought": self.thought,
            "action": self.action.dict() if self.action else None,
            "observation": self.observation.dict() if self.observation else None,
            "error": self.error,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class AgentContext:
    """智能体上下文
    
    保存智能体执行过程中的共享信息
    """
    # 数据库分析结果
    schema_info: Optional[Any] = None
    domain_analysis: Optional[Any] = None
    field_classifications: Optional[Any] = None
    relationships: Optional[Any] = None
    
    # 生成的 SQL 和验证结果
    generated_sql: Optional[str] = None
    validation_result: Optional[Any] = None
    execution_result: Optional[QueryExecutionResult] = None
    
    # 其他上下文信息
    extra_info: Dict[str, Any] = field(default_factory=dict)
    
    def update(self, **kwargs):
        """更新上下文"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                self.extra_info[key] = value


@dataclass
class AgentExecution:
    """智能体执行记录
    
    记录一次完整的任务执行过程
    """
    task: str
    steps: List[AgentStep] = field(default_factory=list)
    state: AgentState = AgentState.IDLE
    context: AgentContext = field(default_factory=AgentContext)
    final_result: Optional[Any] = None
    final_sql: Optional[str] = None
    execution_time: float = 0.0
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    @property
    def success(self) -> bool:
        """是否成功完成"""
        return self.state == AgentState.COMPLETED
    
    @property
    def total_steps(self) -> int:
        """总步骤数"""
        return len(self.steps)
    
    def add_step(self, step: AgentStep):
        """添加步骤"""
        self.steps.append(step)
    
    def get_last_step(self) -> Optional[AgentStep]:
        """获取最后一个步骤"""
        return self.steps[-1] if self.steps else None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task": self.task,
            "state": self.state.value,
            "success": self.success,
            "total_steps": self.total_steps,
            "steps": [step.to_dict() for step in self.steps],
            "final_result": self.final_result,
            "final_sql": self.final_sql,
            "execution_time": self.execution_time,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


class AgentError(Exception):
    """智能体错误"""
    pass


class MaxStepsExceededError(AgentError):
    """超过最大步骤数错误"""
    pass


class ToolExecutionError(AgentError):
    """工具执行错误"""
    pass