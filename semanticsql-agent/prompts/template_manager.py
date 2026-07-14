"""
提示词管理器 - 管理和加载提示词模板
"""

from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, Template, TemplateNotFound
from langchain_core.prompts import PromptTemplate


class PromptManager:
    """提示词管理器"""

    def __init__(self, template_dir: Optional[str] = None):
        """初始化提示词管理器

        Args:
            template_dir: 模板目录路径，默认为 prompts/templates
        """
        if template_dir is None:
            # 获取当前文件所在目录
            current_dir = Path(__file__).parent
            template_dir = current_dir / "templates"

        self.template_dir = Path(template_dir)

        # 初始化 Jinja2 环境
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def get_template(self, template_path: str) -> Template:
        """获取模板

        Args:
            template_path: 模板路径，如 'system/main.j2'

        Returns:
            Jinja2 模板对象
        """
        return self.env.get_template(template_path)

    def render_template(self, template_path: str, **kwargs) -> str:
        """渲染模板

        Args:
            template_path: 模板路径
            **kwargs: 模板变量

        Returns:
            渲染后的字符串
        """
        template = self.get_template(template_path)
        return template.render(**kwargs)

    def get_system_prompt(self, template_name: str = "main", **kwargs) -> str:
        """获取系统提示词

        Args:
            template_name: 模板名称，默认为'main'，可指定为'semantic_sql_agent'等
            **kwargs: 模板变量

        Returns:
            系统提示词字符串
        """
        template_path = f"system/{template_name}.j2"
        return self.render_template(template_path, **kwargs)

    def get_tool_prompt(self, tool_name: str, **kwargs) -> str:
        """获取工具提示词

        Args:
            tool_name: 工具名称
            **kwargs: 模板变量

        Returns:
            工具提示词字符串
        """
        template_path = f"tools/{tool_name}.j2"
        try:
            return self.render_template(template_path, **kwargs)
        except TemplateNotFound:
            # 如果没有特定的工具模板，返回空字符串
            return ""

    def create_agent_prompt_template(
        self, agent_type: str = "semantic_sql_agent", **kwargs
    ) -> PromptTemplate:
        """创建智能体专用的ReAct格式PromptTemplate

        Args:
            agent_type: 智能体类型，默认为'semantic_sql_agent'
            **kwargs: 模板变量

        Returns:
            LangChain PromptTemplate，专门用于ReAct Agent
        """
        # 获取原始Jinja2模板
        template_path = f"system/{agent_type}.j2"
        jinja_template = self.get_template(template_path)

        # 将Jinja2语法转换为LangChain格式
        # 创建一个包含占位符的基础模板
        langchain_template = jinja_template.render(
            tools="{tools}",
            tool_names="{tool_names}",
            input="{input}",
            agent_scratchpad="{agent_scratchpad}",
        )

        # 创建PromptTemplate，包含ReAct所需的输入变量
        return PromptTemplate(
            template=langchain_template,
            input_variables=["input", "agent_scratchpad", "tools", "tool_names"],
        )
