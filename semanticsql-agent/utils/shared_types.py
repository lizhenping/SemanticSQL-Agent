"""共享的基础类型定义

只包含真正需要跨模块共享的简单类型。
工具特定的模型应该在工具内部定义。
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List


@dataclass
class QueryResult:
    """查询结果 - 用于返回给用户的最终结果"""
    success: bool
    question: str
    sql: Optional[str] = None
    answer: Optional[str] = None
    error: Optional[str] = None
    steps: int = 0
    token_usage: Optional[Dict[str, int]] = None


# 向后兼容的别名
QueryExecutionResult = Dict[str, Any]  # 已经内联到 sql_execution.py