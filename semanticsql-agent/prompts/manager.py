"""
提示词管理器 - 统一管理和加载提示词
"""

import yaml
import os
from pathlib import Path
from typing import Dict, Any, Optional
from string import Template
import logging

from core.exceptions import PromptError


class PromptManager:
    """提示词管理器"""
    
    def __init__(self, prompts_dir: str = None):
        """
        初始化提示词管理器
        
        Args:
            prompts_dir: 提示词目录路径
        """
        self.logger = logging.getLogger("PromptManager")
        
        # 确定提示词目录
        if prompts_dir:
            self.prompts_dir = Path(prompts_dir)
        else:
            # 默认使用当前模块所在目录
            self.prompts_dir = Path(__file__).parent
        
        # 缓存加载的提示词
        self._system_prompts = None
        self._tool_prompts = None
        self._custom_prompts = {}
        
        # 加载默认提示词
        self._load_prompts()
    
    def _load_prompts(self):
        """加载提示词文件"""
        try:
            # 加载系统提示词
            system_prompt_file = self.prompts_dir / "system_prompt.yaml"
            if system_prompt_file.exists():
                with open(system_prompt_file, 'r', encoding='utf-8') as f:
                    self._system_prompts = yaml.safe_load(f)
                self.logger.info("System prompts loaded successfully")
            else:
                self.logger.warning(f"System prompt file not found: {system_prompt_file}")
                self._system_prompts = {}
            
            # 加载工具提示词
            tool_prompts_file = self.prompts_dir / "tool_prompts.yaml"
            if tool_prompts_file.exists():
                with open(tool_prompts_file, 'r', encoding='utf-8') as f:
                    self._tool_prompts = yaml.safe_load(f)
                self.logger.info("Tool prompts loaded successfully")
            else:
                self.logger.warning(f"Tool prompts file not found: {tool_prompts_file}")
                self._tool_prompts = {}
                
        except Exception as e:
            raise PromptError(f"Failed to load prompts: {e}")
    
    def get_system_prompt(self, agent_name: str, section: str = None) -> str:
        """
        获取系统提示词
        
        Args:
            agent_name: 智能体名称
            section: 具体章节（如role, instructions等）
            
        Returns:
            提示词文本
        """
        if not self._system_prompts:
            return ""
        
        agent_prompts = self._system_prompts.get("agent", {}).get(agent_name, {})
        
        if section:
            return agent_prompts.get(section, "")
        else:
            # 组合所有部分
            parts = []
            if "role" in agent_prompts:
                parts.append(agent_prompts["role"])
            if "instructions" in agent_prompts:
                parts.append(agent_prompts["instructions"])
            if "capabilities" in agent_prompts:
                parts.append("Capabilities:\n" + "\n".join(f"- {cap}" for cap in agent_prompts["capabilities"]))
            if "output_requirements" in agent_prompts:
                parts.append("Output Requirements:\n" + "\n".join(f"- {req}" for req in agent_prompts["output_requirements"]))
            
            return "\n\n".join(parts)
    
    def get_tool_prompt(self, category: str, tool_name: str, template_name: str = None, **kwargs) -> str:
        """
        获取工具提示词
        
        Args:
            category: 工具类别（analysis/generation/validation/reflection）
            tool_name: 工具名称
            template_name: 模板名称
            **kwargs: 模板变量
            
        Returns:
            格式化后的提示词
        """
        if not self._tool_prompts:
            return ""
        
        tool_prompts = self._tool_prompts.get(category, {}).get(tool_name, {})
        
        if template_name:
            prompt_template = tool_prompts.get(template_name, "")
        else:
            prompt_template = tool_prompts.get("prompt_template", tool_prompts.get("description", ""))
        
        # 如果有变量，进行替换
        if kwargs and prompt_template:
            try:
                # 使用安全的模板替换
                prompt = self._safe_format(prompt_template, **kwargs)
                return prompt
            except Exception as e:
                self.logger.warning(f"Failed to format prompt: {e}")
                return prompt_template
        
        return prompt_template
    
    def get_react_prompt(self, prompt_type: str, **kwargs) -> str:
        """
        获取ReAct模式提示词
        
        Args:
            prompt_type: 提示词类型（thinking/action/observation/reflection）
            **kwargs: 模板变量
            
        Returns:
            格式化后的提示词
        """
        if not self._system_prompts:
            return ""
        
        react_prompts = self._system_prompts.get("react_pattern", {})
        prompt_list = react_prompts.get(f"{prompt_type}_prompts", [])
        
        if not prompt_list:
            return ""
        
        # 随机选择一个提示词
        import random
        prompt_template = random.choice(prompt_list)
        
        # 格式化
        if kwargs:
            return self._safe_format(prompt_template, **kwargs)
        
        return prompt_template
    
    def get_error_prompt(self, error_type: str, **kwargs) -> str:
        """
        获取错误处理提示词
        
        Args:
            error_type: 错误类型（retry/fallback/clarification）
            **kwargs: 模板变量
            
        Returns:
            格式化后的提示词
        """
        if not self._system_prompts:
            return ""
        
        error_prompts = self._system_prompts.get("error_handling", {})
        prompt_template = error_prompts.get(f"{error_type}_prompt", "")
        
        if kwargs and prompt_template:
            return self._safe_format(prompt_template, **kwargs)
        
        return prompt_template
    
    def get_completion_prompt(self, status: str, **kwargs) -> str:
        """
        获取完成提示词
        
        Args:
            status: 完成状态（success/partial_success/failure）
            **kwargs: 模板变量
            
        Returns:
            格式化后的提示词
        """
        if not self._system_prompts:
            return ""
        
        completion_prompts = self._system_prompts.get("completion", {})
        prompt_template = completion_prompts.get(f"{status}_prompt", "")
        
        if kwargs and prompt_template:
            return self._safe_format(prompt_template, **kwargs)
        
        return prompt_template
    
    def load_custom_prompts(self, file_path: str):
        """
        加载自定义提示词文件
        
        Args:
            file_path: 自定义提示词文件路径
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                custom_prompts = yaml.safe_load(f)
                
            # 缓存自定义提示词
            prompt_id = Path(file_path).stem
            self._custom_prompts[prompt_id] = custom_prompts
            
            self.logger.info(f"Custom prompts loaded: {prompt_id}")
            
        except Exception as e:
            raise PromptError(f"Failed to load custom prompts from {file_path}: {e}")
    
    def get_custom_prompt(self, prompt_id: str, path: str, **kwargs) -> str:
        """
        获取自定义提示词
        
        Args:
            prompt_id: 提示词文件ID
            path: 提示词路径（用.分隔）
            **kwargs: 模板变量
            
        Returns:
            格式化后的提示词
        """
        if prompt_id not in self._custom_prompts:
            return ""
        
        # 获取嵌套的提示词
        prompt_data = self._custom_prompts[prompt_id]
        for key in path.split('.'):
            if isinstance(prompt_data, dict):
                prompt_data = prompt_data.get(key, "")
            else:
                return ""
        
        # 格式化
        if kwargs and isinstance(prompt_data, str):
            return self._safe_format(prompt_data, **kwargs)
        
        return str(prompt_data)
    
    def _safe_format(self, template_str: str, **kwargs) -> str:
        """
        安全的字符串格式化
        
        Args:
            template_str: 模板字符串
            **kwargs: 替换变量
            
        Returns:
            格式化后的字符串
        """
        try:
            # 使用Template进行安全替换
            template = Template(template_str.replace('{', '${').replace('}', '}'))
            return template.safe_substitute(**kwargs)
        except Exception as e:
            self.logger.warning(f"Template formatting failed: {e}")
            # 降级到简单替换
            result = template_str
            for key, value in kwargs.items():
                result = result.replace(f"{{{key}}}", str(value))
            return result
    
    def list_available_prompts(self) -> Dict[str, Any]:
        """
        列出所有可用的提示词
        
        Returns:
            提示词清单
        """
        available = {
            "system_prompts": {},
            "tool_prompts": {},
            "custom_prompts": list(self._custom_prompts.keys())
        }
        
        # 系统提示词
        if self._system_prompts:
            available["system_prompts"] = {
                "agents": list(self._system_prompts.get("agent", {}).keys()),
                "react_patterns": list(self._system_prompts.get("react_pattern", {}).keys()),
                "error_handling": list(self._system_prompts.get("error_handling", {}).keys()),
                "completion": list(self._system_prompts.get("completion", {}).keys())
            }
        
        # 工具提示词
        if self._tool_prompts:
            for category, tools in self._tool_prompts.items():
                available["tool_prompts"][category] = list(tools.keys())
        
        return available
    
    def reload_prompts(self):
        """重新加载所有提示词"""
        self._system_prompts = None
        self._tool_prompts = None
        self._custom_prompts = {}
        self._load_prompts()
        self.logger.info("All prompts reloaded")


# 全局提示词管理器实例
_prompt_manager = None


def get_prompt_manager() -> PromptManager:
    """获取全局提示词管理器实例"""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager