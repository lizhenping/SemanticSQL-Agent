"""
SQL执行相关模型
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class ExecutionResult(BaseModel):
    """SQL执行结果"""
    success: bool
    sql: str
    data: List[Dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    execution_time: float = 0.0
    error_message: Optional[str] = None


class ValidationResult(BaseModel):
    """验证结果"""
    sql_id: str
    is_valid: bool
    execution_time: Optional[float] = None
    row_count: Optional[int] = None
    error_message: Optional[str] = None


class SQLQueryResult(BaseModel):
    """SQL查询结果 - 统一的查询结果模型"""
    success: bool
    question: str
    sql: Optional[str] = None
    answer: Optional[str] = None
    data: List[Dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    execution_time: float = 0.0
    error: Optional[str] = None
    steps: int = 0