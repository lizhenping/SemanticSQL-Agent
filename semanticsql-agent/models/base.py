"""
基础模型定义 - 公用的基础类和枚举
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any, Dict, Optional
from enum import Enum


class DifficultyLevel(Enum):
    """查询难度级别"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


class SQLOperation(Enum):
    """SQL操作类型"""
    SELECT = "SELECT"
    JOIN = "JOIN"
    GROUP = "GROUP"
    SUBQUERY = "SUBQUERY"
    WINDOW = "WINDOW"
    CTE = "CTE"
    UNION = "UNION"


class BaseToolInput(BaseModel):
    """工具输入基类"""
    pass


class BaseToolOutput(BaseModel):
    """工具输出基类"""
    success: bool
    data: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)