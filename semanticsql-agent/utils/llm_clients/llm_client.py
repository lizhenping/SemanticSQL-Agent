"""LLM 客户端工厂（参考 TRAEAgent）"""

from enum import Enum
from typing import Optional
from ..config import ModelConfig
from .base_client import BaseLLMClient
from .openai_client import OpenAIClient
from .local_client import LocalModelClient
from .llm_basics import LLMMessage, LLMResponse


class LLMProvider(Enum):
    """支持的 LLM 提供商"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"
    AZURE = "azure"


class LLMClient:
    """主 LLM 客户端，支持多种提供商"""
    
    def __init__(self, config: ModelConfig):
        self.config = config
        self.provider = LLMProvider(config.provider.lower())
        self.client = self._create_client()
    
    def _create_client(self) -> BaseLLMClient:
        """根据配置创建具体的客户端"""
        if self.provider == LLMProvider.OPENAI:
            return OpenAIClient(
                api_key=self.config.api_key,
                model=self.config.model,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
        elif self.provider == LLMProvider.LOCAL:
            return LocalModelClient(
                model=self.config.model,
                base_url=self.config.base_url,
                api_key=self.config.api_key or "dummy",
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
        elif self.provider == LLMProvider.ANTHROPIC:
            # 可以添加 Anthropic 客户端
            raise NotImplementedError("Anthropic 客户端暂未实现")
        elif self.provider == LLMProvider.AZURE:
            # Azure 使用 OpenAI 兼容接口
            from .openai_compatible_base import OpenAICompatibleClient
            return OpenAICompatibleClient(
                api_key=self.config.api_key,
                model=self.config.model,
                base_url=self.config.base_url,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
        else:
            raise ValueError(f"不支持的 LLM 提供商: {self.provider}")
    
    def chat(self, messages: list[LLMMessage]) -> LLMResponse:
        """发送聊天消息"""
        return self.client.chat(messages)
    
    def complete(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """简单的文本补全接口"""
        messages = []
        if system_prompt:
            messages.append(LLMMessage(role="system", content=system_prompt))
        messages.append(LLMMessage(role="user", content=prompt))
        
        response = self.chat(messages)
        return response.content