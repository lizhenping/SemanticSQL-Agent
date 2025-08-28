"""模型模块

逐步迁移到 utils/types.py 和各工具内部定义。
保留向后兼容性。
"""

# 从新位置导入基础类型
from utils.types import QueryResult, QueryExecutionResult

# 暂时保留其他模型的导入（将逐步移除）
from .schemas import *
from .analysis_models import *
from .generation_models import *

# 标记为即将废弃
import warnings

def _deprecated_models_warning():
    warnings.warn(
        "models 目录即将废弃，请使用 utils.types 或在工具内部定义模型",
        DeprecationWarning,
        stacklevel=2
    )

# 在导入时显示警告（开发阶段）
# _deprecated_models_warning()