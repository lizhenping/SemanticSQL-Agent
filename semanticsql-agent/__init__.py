"""SemanticSQL-Agent: 基于 LangChain 的 NL2SQL 智能体

简洁设计，参考 TRAEAgent。
"""

__version__ = "0.2.0"
__author__ = "lizhenping18@mails.ucas.ac.cn"

from .agent import SQLAgent
from .config import Config
from .utils.shared_types import QueryResult

__all__ = ["SQLAgent", "Config", "QueryResult"]