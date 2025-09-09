"""
提示词管理器 - 管理和加载提示词模板
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional

from jinja2 import Environment, FileSystemLoader, Template
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, PromptTemplate


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
            lstrip_blocks=True
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
        template_path = f'system/{template_name}.j2'
        return self.render_template(template_path, **kwargs)
    
    def get_tool_prompt(self, tool_name: str, **kwargs) -> str:
        """获取工具提示词
        
        Args:
            tool_name: 工具名称
            **kwargs: 模板变量
            
        Returns:
            工具提示词字符串
        """
        template_path = f'tools/{tool_name}.j2'
        try:
            return self.render_template(template_path, **kwargs)
        except:
            # 如果没有特定的工具模板，返回空字符串
            return ""
    
    
    
    
    def get_thinking_prompt(self, thinking_type: str, **kwargs) -> str:
        """获取思考提示词
        
        Args:
            thinking_type: 思考类型
            **kwargs: 模板变量
            
        Returns:
            思考提示词字符串
        """
        template_path = f'thinking/{thinking_type}.j2'
        try:
            return self.render_template(template_path, **kwargs)
        except:
            return ""
    
    def create_agent_prompt_template(self, agent_type: str = "semantic_sql_agent", **kwargs) -> PromptTemplate:
        """创建智能体专用的ReAct格式PromptTemplate
        
        Args:
            agent_type: 智能体类型，默认为'semantic_sql_agent'
            **kwargs: 模板变量
            
        Returns:
            LangChain PromptTemplate，专门用于ReAct Agent
        """
        # 获取原始Jinja2模板
        template_path = f'system/{agent_type}.j2'
        jinja_template = self.get_template(template_path)
        
        # 将Jinja2语法转换为LangChain格式
        # 创建一个包含占位符的基础模板
        langchain_template = jinja_template.render(
            tools="{tools}",
            tool_names="{tool_names}",
            input="{input}",
            agent_scratchpad="{agent_scratchpad}"
        )
        
        # 创建PromptTemplate，包含ReAct所需的输入变量
        return PromptTemplate(
            template=langchain_template,
            input_variables=["input", "agent_scratchpad", "tools", "tool_names"]
        )
    
    def create_agent_prompt(self, **kwargs) -> ChatPromptTemplate:
        """创建Agent提示词模板
        
        Args:
            **kwargs: 模板变量
            
        Returns:
            LangChain ChatPromptTemplate
        """
        # 获取系统提示词
        system_prompt = self.get_system_prompt(**kwargs)
        
        # 创建提示词模板
        messages = [
            SystemMessagePromptTemplate.from_template(system_prompt),
            HumanMessagePromptTemplate.from_template("{input}"),
            # Agent scratchpad 用于 ReAct 模式
            HumanMessagePromptTemplate.from_template("{agent_scratchpad}")
        ]
        
        return ChatPromptTemplate.from_messages(messages)
    
    def create_tool_prompt_template(self, tool_name: str, **kwargs) -> ChatPromptTemplate:
        """创建工具专用的提示词模板
        
        Args:
            tool_name: 工具名称
            **kwargs: 模板变量
            
        Returns:
            工具专用的 ChatPromptTemplate
        """
        tool_prompt = self.get_tool_prompt(tool_name, **kwargs)
        
        if tool_prompt:
            messages = [
                SystemMessagePromptTemplate.from_template(tool_prompt),
                HumanMessagePromptTemplate.from_template("{input}")
            ]
        else:
            # 使用默认模板
            messages = [
                HumanMessagePromptTemplate.from_template(
                    "Please use the {tool_name} tool to process: {input}"
                )
            ]
        
        return ChatPromptTemplate.from_messages(messages)
    
    def list_templates(self) -> Dict[str, list]:
        """列出所有可用的模板
        
        Returns:
            按类别分组的模板列表
        """
        templates = {
            "system": [],
            "tools": [],
            "generation": [],
            "thinking": []
        }
        
        for category in templates.keys():
            category_dir = self.template_dir / category
            if category_dir.exists():
                templates[category] = [
                    f.name for f in category_dir.glob("*.j2")
                ]
        
        return templates