"""LLM 基础类型定义（参考 TRAEAgent，包含 tool calling 支持）"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


# 工具调用相关类型
ToolCallArguments = Dict[str, Any]


@dataclass
class ToolCall:
    """工具调用"""
    name: str
    call_id: str
    arguments: ToolCallArguments = field(default_factory=dict)
    
    def __str__(self) -> str:
        return f"ToolCall(name={self.name}, call_id={self.call_id}, arguments={self.arguments})"


@dataclass
class ToolResult:
    """工具执行结果"""
    call_id: str
    name: str
    success: bool
    result: Optional[str] = None
    error: Optional[str] = None


@dataclass
class LLMMessage:
    """LLM 消息格式"""
    role: str  # "system", "user", "assistant", "tool"
    content: Optional[str] = None
    tool_call: Optional[ToolCall] = None
    tool_result: Optional[ToolResult] = None


@dataclass
class LLMUsage:
    """Token 使用统计"""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    
    def __add__(self, other: "LLMUsage") -> "LLMUsage":
        return LLMUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            total_tokens=self.total_tokens + other.total_tokens
        )
    
    def __str__(self) -> str:
        return f"LLMUsage(input={self.input_tokens}, output={self.output_tokens}, total={self.total_tokens})"


@dataclass
class LLMResponse:
    """LLM 响应格式"""
    content: str
    usage: Optional[LLMUsage] = None
    model: Optional[str] = None
    finish_reason: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None