"""环境变量配置模块

负责管理和设置LLM相关的环境变量
"""

import os
import logging
from typing import Optional, Dict, Any


class EnvironmentConfig:
    """环境变量配置管理器"""
    
    # 环境变量键名常量
    OPENAI_API_KEY = 'OPENAI_API_KEY'
    OPENAI_BASE_URL = 'OPENAI_BASE_URL'
    OPENAI_MODEL = 'OPENAI_MODEL'
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """初始化环境配置管理器
        
        Args:
            logger: 日志记录器，如果为None则使用默认logger
        """
        self.logger = logger or logging.getLogger(__name__)
    
    def configure_from_args(self, args: Dict[str, Any]) -> None:
        """从命令行参数配置环境变量
        
        Args:
            args: 命令行参数字典
        """
        # 设置API密钥
        if args.get('api_key'):
            self.set_api_key(args['api_key'])
        
        # 设置基础URL
        if args.get('base_url'):
            self.set_base_url(args['base_url'])
        
        # 设置模型名称
        if args.get('model'):
            self.set_model(args['model'])
    
    def set_api_key(self, api_key: str) -> None:
        """设置OpenAI API密钥
        
        Args:
            api_key: API密钥
        """
        os.environ[self.OPENAI_API_KEY] = api_key
        self.logger.debug("已设置OPENAI_API_KEY")
    
    def set_base_url(self, base_url: str) -> None:
        """设置OpenAI基础URL
        
        Args:
            base_url: 基础URL
        """
        os.environ[self.OPENAI_BASE_URL] = base_url
        self.logger.info(f"设置OPENAI_BASE_URL: {base_url}")
    
    def set_model(self, model: str) -> None:
        """设置OpenAI模型名称
        
        Args:
            model: 模型名称
        """
        os.environ[self.OPENAI_MODEL] = model
        self.logger.info(f"设置OPENAI_MODEL: {model}")
    
    def get_api_key(self) -> Optional[str]:
        """获取API密钥"""
        return os.environ.get(self.OPENAI_API_KEY)
    
    def get_base_url(self) -> Optional[str]:
        """获取基础URL"""
        return os.environ.get(self.OPENAI_BASE_URL)
    
    def get_model(self) -> Optional[str]:
        """获取模型名称"""
        return os.environ.get(self.OPENAI_MODEL)