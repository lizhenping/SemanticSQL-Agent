"""
核心模块 - 包含数据模型、异常定义和常量
"""

from .models import (
    AgentStep,
    AgentStepType,
    AgentExecution,
    QueryScenario,
    GeneratedExample,
    TrainingExample,
    SQLOperation,
    DifficultyLevel
)

from .exceptions import (
    SemanticSQLError,
    ConfigurationError,
    ToolExecutionError,
    DatabaseConnectionError,
    ValidationError,
    GenerationError
)

from .constants import (
    SQL_TYPES,
    DIFFICULTY_DISTRIBUTION,
    DEFAULT_MAX_STEPS,
    DEFAULT_TEMPERATURE,
    SUPPORTED_DATABASES
)

__all__ = [
    # Models
    'AgentStep',
    'AgentStepType', 
    'AgentExecution',
    'QueryScenario',
    'GeneratedExample',
    'TrainingExample',
    'SQLOperation',
    'DifficultyLevel',
    
    # Exceptions
    'SemanticSQLError',
    'ConfigurationError',
    'ToolExecutionError',
    'DatabaseConnectionError',
    'ValidationError',
    'GenerationError',
    
    # Constants
    'SQL_TYPES',
    'DIFFICULTY_DISTRIBUTION',
    'DEFAULT_MAX_STEPS',
    'DEFAULT_TEMPERATURE',
    'SUPPORTED_DATABASES'
]