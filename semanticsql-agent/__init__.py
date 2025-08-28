"""SemanticSQL-Agent: 简化的 NL2SQL 智能体

基于 TRAEAgent 设计理念，使用模块化的 CLI 和 LLM 客户端。
"""

__version__ = "0.3.0"
__author__ = "lizhenping18@mails.ucas.ac.cn"

from .config import Config
from .utils.llm_clients import LLMClient, LLMMessage, LLMResponse, LLMUsage
from .utils.shared_types import QueryResult
from .utils.cli import ConsoleFactory, ConsoleMode, ConsoleType

__all__ = [
    "Config", 
    "LLMClient",
    "LLMMessage",
    "LLMResponse", 
    "LLMUsage",
    "QueryResult",
    "ConsoleFactory",
    "ConsoleMode",
    "ConsoleType"
]