"""Jinja2 提示词管理器"""

from jinja2 import Environment, FileSystemLoader, Template
from pathlib import Path
from typing import Dict, Any, Optional
import yaml
import logging

logger = logging.getLogger(__name__)


class PromptManager:
    """提示词管理器"""
    
    def __init__(self, template_dir: Optional[str] = None):
        """初始化提示词管理器
        
        Args:
            template_dir: 模板目录路径，默认为当前目录下的 templates
        """
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"
        
        self.template_dir = Path(template_dir)
        
        # 创建 Jinja2 环境
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True
        )
        
        # 添加自定义过滤器
        self._register_filters()
        
        # 加载配置
        self.config = self._load_config()
        
        logger.info(f"提示词管理器初始化完成，模板目录: {self.template_dir}")
    
    def _register_filters(self):
        """注册自定义 Jinja2 过滤器"""
        # 截断过滤器
        self.env.filters['truncate'] = lambda s, length=50: s[:length] + "..." if len(s) > length else s
        
        # 列表连接过滤器
        self.env.filters['join_list'] = lambda lst, sep=", ": sep.join(str(item) for item in lst)
        
        # 格式化数字
        self.env.filters['format_number'] = lambda n: f"{n:,}" if isinstance(n, (int, float)) else n
    
    def _load_config(self) -> Dict[str, Any]:
        """加载提示词配置"""
        config_file = self.template_dir.parent / "config.yaml"
        
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.warning(f"加载提示词配置失败: {e}")
        
        return {}
    
    def get_prompt(self, template_name: str, **kwargs) -> str:
        """获取渲染后的提示词
        
        Args:
            template_name: 模板名称（相对于模板目录的路径）
            **kwargs: 模板变量
            
        Returns:
            渲染后的提示词
        """
        # 确保模板名称有 .j2 后缀
        if not template_name.endswith('.j2'):
            template_name += '.j2'
        
        try:
            # 获取模板
            template = self.env.get_template(template_name)
            
            # 合并配置和参数
            context = {
                **self.config,
                **kwargs
            }
            
            # 渲染模板
            return template.render(context)
            
        except Exception as e:
            logger.error(f"渲染模板 {template_name} 失败: {e}")
            raise
    
    def get_system_prompt(self, agent_type: str, **kwargs) -> str:
        """获取系统提示词
        
        Args:
            agent_type: 智能体类型
            **kwargs: 额外的模板变量
            
        Returns:
            系统提示词
        """
        template_path = f"system/{agent_type}"
        return self.get_prompt(template_path, **kwargs)
    
    def get_tool_description(self, tool_name: str, **kwargs) -> str:
        """获取工具描述
        
        Args:
            tool_name: 工具名称
            **kwargs: 额外的模板变量
            
        Returns:
            工具描述
        """
        template_path = f"tools/{tool_name}"
        return self.get_prompt(template_path, **kwargs)
    
    def get_analysis_prompt(self, analysis_type: str, **kwargs) -> str:
        """获取分析提示词
        
        Args:
            analysis_type: 分析类型
            **kwargs: 额外的模板变量
            
        Returns:
            分析提示词
        """
        template_path = f"analysis/{analysis_type}"
        return self.get_prompt(template_path, **kwargs)
    
    def list_templates(self) -> List[str]:
        """列出所有可用的模板
        
        Returns:
            模板路径列表
        """
        templates = []
        
        for path in self.template_dir.rglob("*.j2"):
            relative_path = path.relative_to(self.template_dir)
            templates.append(str(relative_path))
        
        return sorted(templates)
    
    def reload_config(self):
        """重新加载配置"""
        self.config = self._load_config()
        logger.info("提示词配置已重新加载")