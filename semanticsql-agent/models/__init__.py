"""
模型包 - 仅导出真正共享的模型

重组后的结构：
- 大部分模型已按就近原则移动到各自使用的模块中
- 仅保留核心共享模型：exceptions 和 schemas 中的三元组相关模型
- 其他模型请直接从使用模块导入
"""

# 训练数据模型
from .training import (
    DifficultyLevel,
    GeneratedExample,
    TrainingExample,
    TrainingDataResult
)

# 异常模型 - 真正的共享模型
from .exceptions import *

# 三元组相关模型 - 核心共享数据结构
from .schemas import (
    PredicateType,
    EntityType,
    SemanticTriple,
    TripleCollection,
    ToolResult,
    create_triple,
    create_triple_collection
)

__all__ = [
    # 训练相关
    "DifficultyLevel",
    "GeneratedExample", 
    "TrainingExample",
    "TrainingDataResult",
    
    # 三元组相关 - 核心共享模型
    "PredicateType",
    "EntityType", 
    "SemanticTriple",
    "TripleCollection",
    "ToolResult",
    "create_triple",
    "create_triple_collection"
    
    # 异常模型通过 * 导入
]