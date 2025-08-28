"""LLM 基础类型定义（参考 TRAEAgent）"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any


@dataclass
class LLMMessage:
    """LLM 消息"""
    role: str  # "system", "user", "assistant"
    content: str


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


@dataclass
class LLMResponse:
    """LLM 响应"""
    content: str
    usage: Optional[LLMUsage] = None
    model: Optional[str] = None
    finish_reason: Optional[str] = None