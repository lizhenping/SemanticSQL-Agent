"""LLM 客户端 - 使用标准 OpenAI 客户端"""

from .openai_client import OpenAILLMClient

# 为了保持向后兼容，将 LLMClient 指向新的 OpenAILLMClient
LLMClient = OpenAILLMClient