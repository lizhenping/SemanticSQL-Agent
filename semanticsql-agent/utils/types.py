"""共享的基础类型定义

只包含真正需要跨模块共享的类型。
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


@dataclass
class QueryExecutionResult:
    """SQL 执行结果"""
    success: bool
    row_count: int = 0
    rows: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
    execution_time: float = 0.0