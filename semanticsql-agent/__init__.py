"""SemanticSQL-Agent: 简化的 NL2SQL 智能体

基于 TRAEAgent 设计理念，不依赖 LangChain。
"""

__version__ = "0.3.0"
__author__ = "lizhenping18@mails.ucas.ac.cn"

from .config import Config
from .llm_client import LLMClient
from .llm_basics import LLMMessage, LLMResponse, LLMUsage
from .utils.shared_types import QueryResult

__all__ = [
    "Config", 
    "LLMClient",
    "LLMMessage",
    "LLMResponse", 
    "LLMUsage",
    "QueryResult"
]