"""SQL查询结果类 - 统一定义"""

from typing import Dict, Any, Optional, List


class SQLQueryResult:
    """SQL查询结果"""
    
    def __init__(
        self,
        success: bool,
        question: str,
        sql: Optional[str] = None,
        answer: Optional[str] = None,
        data: Optional[List[Dict[str, Any]]] = None,
        row_count: int = 0,
        execution_time: float = 0.0,
        error: Optional[str] = None,
        steps: int = 0
    ):
        self.success = success
        self.question = question
        self.sql = sql
        self.answer = answer
        self.data = data or []
        self.row_count = row_count
        self.execution_time = execution_time
        self.error = error
        self.steps = steps
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "question": self.question,
            "sql": self.sql,
            "answer": self.answer,
            "data": self.data,
            "row_count": self.row_count,
            "execution_time": self.execution_time,
            "error": self.error,
            "steps": self.steps
        }