"""LLM 客户端抽象层（infra/llm.py）

设计原则：
- 可测试性：通过 LLMClient 协议注入，测试时可用 FakeLLM
- DRY：LLM 创建逻辑只此一处，替代各工具各自的 create_llm()
- 依赖方向：infra 层不依赖 tools/core/cli，只依赖 models

用法：
    llm = create_llm_client(settings)
    text = llm.generate("prompt")
    obj = llm.generate_json("prompt")
"""

from typing import Any, Protocol, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from config.settings import Settings


class LLMClient(Protocol):
    """LLM 客户端协议（可注入 FakeLLM 做单测）。

    所有工具依赖此抽象，不再各自 create_llm()。
    """

    def generate(self, prompt: str) -> str:
        """生成文本"""
        ...

    def generate_json(self, prompt: str) -> dict:
        """生成 JSON（返回解析后的 dict）"""
        ...


class ChatOpenAILLMClient:
    """ChatOpenAI 实现（封装现有 utils/llm.py 的 create_llm 逻辑）"""

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str,
        temperature: float = 0.1,
        max_tokens: int = 8000,
        timeout: int = 1200,
        max_retries: int = 1,
        enable_thinking: bool = True,
    ):
        from langchain_openai import ChatOpenAI

        # 关闭思考模式：Qwen3 系列在 vLLM 上通过 chat_template_kwargs 控制，
        # 请求体里直接省掉推理过程（比事后正则剥离更快、更省 token）。
        # 思考模式开启时不传该字段，避免云端 OpenAI 兼容 API 拒绝未知参数。
        extra_body = None
        if not enable_thinking:
            extra_body = {"chat_template_kwargs": {"enable_thinking": False}}

        self._llm = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
            extra_body=extra_body,
        )

    def generate(self, prompt: str) -> str:
        """生成文本"""
        response = self._llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        # 去除 <think> 标签（vLLM thinking 模式的残留）
        if "<think>" in content:
            import re
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
        return content.strip()

    def generate_json(self, prompt: str) -> dict:
        """生成 JSON，自动解析"""
        import json
        text = self.generate(prompt)
        # 尝试提取 JSON 块
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start)
            text = text[start:end].strip()
        return json.loads(text)


class FakeLLMClient:
    """假 LLM 实现（单测用，不连真 LLM）"""

    def __init__(self, responses: Optional[list[str]] = None):
        self._responses = responses or []
        self._call_count = 0
        self.calls: list[str] = []  # 记录所有调用

    def generate(self, prompt: str) -> str:
        self.calls.append(prompt)
        if self._call_count < len(self._responses):
            resp = self._responses[self._call_count]
            self._call_count += 1
            return resp
        return '{"status": "fake"}'

    def generate_json(self, prompt: str) -> dict:
        import json
        text = self.generate(prompt)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"status": "fake"}


def create_llm_client(settings: Optional["Settings"] = None) -> LLMClient:
    """工厂：从 Settings 创建 LLMClient

    替代原有 utils/llm.py 的 create_llm()，集中 LLM 创建逻辑。
    """
    if settings is None:
        from config.settings import Settings
        settings = Settings()

    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Creating LLM client: {settings.llm_model}")

    return ChatOpenAILLMClient(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        timeout=settings.llm_timeout,
        max_retries=settings.llm_max_retries,
        enable_thinking=settings.llm_enable_thinking,
    )
