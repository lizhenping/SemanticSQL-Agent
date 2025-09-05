"""
模型包 - 导出所有公用模型
"""

# 基础模型
from .base import (
    DifficultyLevel,
    SQLOperation,
    BaseToolInput,
    BaseToolOutput
)

# 数据库模型
from .database import (
    ColumnInfo,
    ForeignKey,
    TableInfo,
    TableRelationship,
    DatabaseSchema
)

# Agent模型
from .agent import (
    AgentStepType,
    AgentStep,
    AgentExecution
)

# 注意：分析相关模型已按就近原则移动到各自的工具文件中
# 如需使用，请直接从对应工具导入

# 训练数据模型
from .training import (
    GeneratedExample,
    TrainingExample,
    TrainingDataResult
)

# 执行模型
from .execution import (
    ExecutionResult,
    ValidationResult,
    SQLQueryResult
)

# 异常模型
from .exceptions import *

__all__ = [
    # 基础
    "DifficultyLevel",
    "SQLOperation",
    "BaseToolInput",
    "BaseToolOutput",
    
    # 数据库
    "ColumnInfo",
    "ForeignKey",
    "TableInfo",
    "TableRelationship",
    "DatabaseSchema",
    
    # Agent
    "AgentStepType",
    "AgentStep",
    "AgentExecution",
    
# 分析模型已移至工具文件中
    
    # 训练
    "GeneratedExample",
    "TrainingExample",
    "TrainingDataResult",
    
    # 执行
    "ExecutionResult",
    "ValidationResult",
    "SQLQueryResult"
]