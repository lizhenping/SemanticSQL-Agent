"""SemanticSQL-Agent: 简化的 NL2SQL 智能体

基于 TRAEAgent 设计理念，使用模块化的 CLI 和 LLM 客户端。
"""

__version__ = "0.3.0"
__author__ = "lizhenping18@mails.ucas.ac.cn"

# 简化导入，只保留必要的组件
from .config.trae_config import TraeConfig

__all__ = [
    "TraeConfig"
]