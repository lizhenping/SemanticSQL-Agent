"""工具基类（tools/base_tool.py）

设计原则：
- 可测试性：依赖通过 __init__ 注入，不再内部 create_llm()
- DRY：database_manager / llm / kbase 不再每个工具各自初始化
- 关注点分离：工具只依赖 infra/models 抽象，不依赖 core/cli

所有工具继承此类，通过 run() 统一入口。
"""

import logging
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from infra.llm import LLMClient
    from infra.database import DatabaseManager
    from core.knowledge_store import KnowledgeBase
    from prompts.template_manager import PromptManager


class BaseSemanticTool:
    """所有工具的基类。

    依赖通过 __init__ 注入（可测试性）：
        llm: LLM 客户端（可注入 FakeLLM）
        db:  数据库管理器（可注入 FakeDB）
        kbase: 知识库（K 唯一真相源）
        prompt_manager: 提示词渲染器
    """

    def __init__(
        self,
        llm: Optional["LLMClient"] = None,
        db: Optional["DatabaseManager"] = None,
        kbase: Optional["KnowledgeBase"] = None,
        prompt_manager: Optional["PromptManager"] = None,
        name: str = "",
    ):
        self.llm = llm
        self.db = db
        self.kbase = kbase
        self.prompt_manager = prompt_manager
        self._name = name or self.__class__.__name__
        self.logger = logging.getLogger(self._name)

    @property
    def name(self) -> str:
        """工具名称"""
        return self._name

    def run(self, *args, **kwargs) -> Any:
        """子类实现的统一入口（替代散乱的 _run 签名）"""
        raise NotImplementedError(f"{self._name} 未实现 run()")

    def _render_prompt(self, template: str, **kwargs) -> str:
        """渲染提示词模板（template 为相对 templates/ 的路径，如 'analysis/domain_analysis.j2'）

        对应 PromptManager.render_template。
        """
        if self.prompt_manager is None:
            raise RuntimeError(f"{self._name} 未注入 prompt_manager")
        return self.prompt_manager.render_template(template, **kwargs)

    def _render_tool_prompt(self, tool_name: str, **kwargs) -> str:
        """渲染 tools/<tool_name>.j2 提示词（对应 PromptManager.get_tool_prompt）"""
        if self.prompt_manager is None:
            raise RuntimeError(f"{self._name} 未注入 prompt_manager")
        return self.prompt_manager.get_tool_prompt(tool_name, **kwargs)

    def _llm_generate(self, prompt: str) -> str:
        """调 LLM 生成文本"""
        if self.llm is None:
            raise RuntimeError(f"{self._name} 未注入 llm")
        return self.llm.generate(prompt)

    def _llm_generate_json(self, prompt: str) -> dict:
        """调 LLM 生成 JSON"""
        if self.llm is None:
            raise RuntimeError(f"{self._name} 未注入 llm")
        return self.llm.generate_json(prompt)
