"""本地模型客户端（如 vLLM、Ollama 等）"""

from .openai_compatible_base import OpenAICompatibleClient


class LocalModelClient(OpenAICompatibleClient):
    """本地模型客户端，支持 vLLM 等 OpenAI 兼容的本地服务"""
    
    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:8000/v1",
        api_key: str = "dummy",  # 本地模型通常不需要真实的 API key
        temperature: float = 0.0,
        max_tokens: int = 2000
    ):
        super().__init__(
            api_key=api_key,
            model=model,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens
        )