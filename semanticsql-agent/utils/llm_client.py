"""LLM 客户端工具函数"""

from typing import Optional
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_community.chat_models import ChatOllama

from config import ModelConfig


def create_llm_client(config: ModelConfig) -> BaseChatModel:
    """创建 LLM 客户端
    
    Args:
        config: 模型配置
        
    Returns:
        LLM 客户端实例
    """
    provider = config.provider.lower()
    
    if provider == "openai":
        return ChatOpenAI(
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            api_key=config.api_key
        )
    elif provider == "anthropic":
        return ChatAnthropic(
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            anthropic_api_key=config.api_key
        )
    elif provider == "ollama":
        return ChatOllama(
            model=config.model,
            temperature=config.temperature,
            base_url=config.api_base
        )
    elif provider == "vllm":
        # vLLM 兼容 OpenAI API
        return ChatOpenAI(
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            openai_api_base=config.api_base,
            openai_api_key=config.api_key or "EMPTY"
        )
    else:
        raise ValueError(f"不支持的 LLM 提供商: {provider}")