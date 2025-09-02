"""服务容器定义

提供类型安全的服务容器，用于在各个组件之间共享服务实例。
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

# 使用TYPE_CHECKING避免循环导入
if TYPE_CHECKING:
    from .database_service import DatabaseService
    from .llm_service import LLMService  
    from .prompt_service import PromptService
    from .config_service import ConfigService


@dataclass
class ServiceContainer:
    """类型安全的服务容器
    
    用于管理和传递应用程序中的各种服务实例。
    """
    database_service: 'DatabaseService'
    llm_service: 'LLMService'
    prompt_service: 'PromptService'
    config_service: 'ConfigService'