"""LLM 客户端基类（参考 TRAEAgent）"""

from abc import ABC, abstractmethod
from typing import List, Optional
from .llm_basics import LLMMessage, LLMResponse


class BaseLLMClient(ABC):
    """LLM 客户端基类"""
    
    def __init__(self, api_key: str, base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url
        self.message_history: List[LLMMessage] = []
    
    def set_message_history(self, messages: List[LLMMessage]):
        """设置消息历史"""
        self.message_history = messages.copy()
    
    @abstractmethod
    def chat(self, messages: List[LLMMessage]) -> LLMResponse:
        """发送聊天消息到 LLM
        
        Args:
            messages: 消息列表
            
        Returns:
            LLM 响应
        """
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """获取模型名称"""
        pass