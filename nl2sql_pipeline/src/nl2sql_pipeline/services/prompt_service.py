"""提示词服务

管理和渲染Jinja2提示词模板。
"""

import os
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader, Template
import logging

logger = logging.getLogger(__name__)


class PromptService:
    """提示词服务
    
    负责加载、管理和渲染Jinja2提示词模板。
    """
    
    def __init__(self, template_dir: Optional[str] = None):
        """初始化提示词服务
        
        参数:
            template_dir: 模板目录路径，默认使用内置模板目录
        """
        if template_dir is None:
            # 使用默认的模板目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            template_dir = os.path.join(
                os.path.dirname(current_dir), 
                'prompts', 
                'templates'
            )
        
        self.template_dir = template_dir
        
        # 初始化Jinja2环境
        self.env = Environment(
            loader=FileSystemLoader(self.template_dir),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True
        )
        
        # 添加自定义过滤器
        self._register_filters()
        
        logger.info(f"提示词服务初始化完成，模板目录: {self.template_dir}")
    
    def render(self, template_name: str, **kwargs) -> str:
        """渲染提示词模板
        
        参数:
            template_name: 模板文件名（相对于模板目录）
            **kwargs: 模板变量
            
        返回:
            渲染后的提示词文本
        """
        try:
            template = self.env.get_template(template_name)
            rendered = template.render(**kwargs)
            return rendered.strip()
        except Exception as e:
            logger.error(f"渲染模板 {template_name} 失败: {e}")
            raise
    
    def render_string(self, template_string: str, **kwargs) -> str:
        """渲染字符串模板
        
        参数:
            template_string: 模板字符串
            **kwargs: 模板变量
            
        返回:
            渲染后的文本
        """
        try:
            template = Template(template_string)
            rendered = template.render(**kwargs)
            return rendered.strip()
        except Exception as e:
            logger.error(f"渲染字符串模板失败: {e}")
            raise
    
    def list_templates(self) -> list:
        """列出所有可用的模板
        
        返回:
            模板文件路径列表
        """
        templates = []
        for root, dirs, files in os.walk(self.template_dir):
            for file in files:
                if file.endswith('.j2'):
                    # 计算相对路径
                    rel_path = os.path.relpath(
                        os.path.join(root, file), 
                        self.template_dir
                    )
                    templates.append(rel_path)
        return sorted(templates)
    
    def _register_filters(self):
        """注册自定义Jinja2过滤器"""
        
        def format_list(items, separator=", "):
            """格式化列表为字符串"""
            if not items:
                return ""
            return separator.join(str(item) for item in items)
        
        def format_dict(d, item_format="{key}: {value}"):
            """格式化字典为字符串"""
            if not d:
                return ""
            items = []
            for key, value in d.items():
                items.append(item_format.format(key=key, value=value))
            return "\n".join(items)
        
        def truncate(text, length=100, suffix="..."):
            """截断文本"""
            if len(text) <= length:
                return text
            return text[:length - len(suffix)] + suffix
        
        # 注册过滤器
        self.env.filters['format_list'] = format_list
        self.env.filters['format_dict'] = format_dict
        self.env.filters['truncate'] = truncate