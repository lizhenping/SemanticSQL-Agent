"""
Agent执行相关模型
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional, Any, Dict
from enum import Enum
import uuid


class AgentStepType(Enum):
    """Agent执行步骤类型"""
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"
    REFLECTION = "reflection"


class AgentStep(BaseModel):
    """单个执行步骤"""
    step_type: AgentStepType
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class AgentExecution(BaseModel):
    """完整执行记录"""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task: str = ""
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    steps: List[AgentStep] = Field(default_factory=list)
    final_result: Optional[Any] = None
    status: str = "running"  # running/completed/failed
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def add_step(self, step: AgentStep):
        """添加执行步骤"""
        self.steps.append(step)
    
    def complete(self, result: Any = None, error: str = None):
        """标记执行完成"""
        self.completed_at = datetime.now()
        if error:
            self.status = "failed"
            self.error = error
        else:
            self.status = "completed"
            self.final_result = result
    
    def get_duration(self) -> Optional[float]:
        """获取执行时长（秒）"""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    def get_summary(self) -> Dict[str, Any]:
        """获取执行摘要"""
        return {
            "task_id": self.task_id,
            "task": self.task,
            "status": self.status,
            "total_steps": len(self.steps),
            "duration": self.get_duration(),
            "tools_used": list(set(s.tool_name for s in self.steps if s.tool_name)),
            "error": self.error
        }