"""OpenAI 客户端"""

from .openai_compatible_base import OpenAICompatibleClient


class OpenAIClient(OpenAICompatibleClient):
    """OpenAI API 客户端"""
    
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4",
        temperature: float = 0.0,
        max_tokens: int = 2000
    ):
        super().__init__(
            api_key=api_key,
            model=model,
            base_url="https://api.openai.com/v1",
            temperature=temperature,
            max_tokens=max_tokens
        )