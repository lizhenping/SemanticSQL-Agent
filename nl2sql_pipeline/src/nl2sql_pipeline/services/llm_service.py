"""LLM服务接口

提供大语言模型调用的统一接口，支持多种LLM后端。
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class LLMService(ABC):
    """LLM服务抽象基类
    
    定义与大语言模型交互的接口。
    """
    
    def __init__(self, config: Dict[str, Any]):
        """初始化LLM服务
        
        参数:
            config: LLM配置字典
        """
        self.config = config
    
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """生成文本
        
        参数:
            prompt: 提示词
            **kwargs: 其他参数，如temperature、max_tokens等
            
        返回:
            生成的文本
        """
        pass
    
    @abstractmethod
    def generate_json(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """生成JSON格式的响应
        
        参数:
            prompt: 提示词
            **kwargs: 其他参数
            
        返回:
            解析后的JSON对象
        """
        pass
    
    @abstractmethod
    def batch_generate(self, prompts: List[str], **kwargs) -> List[str]:
        """批量生成文本
        
        参数:
            prompts: 提示词列表
            **kwargs: 其他参数
            
        返回:
            生成的文本列表
        """
        pass
    
    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息
        
        返回:
            包含模型名称、版本等信息的字典
        """
        pass