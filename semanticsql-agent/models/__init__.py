"""模型模块 - 已废弃

请使用以下替代方案：
- 共享类型：使用 utils.shared_types
- 工具特定模型：在各工具内部定义

此目录将在未来版本中移除。
"""

import warnings

# 显示废弃警告
warnings.warn(
    "models 模块已废弃。"
    "请使用 utils.shared_types 或在工具内部定义模型。"
    "参考 tools/schema_extraction.py 的实现方式。",
    DeprecationWarning,
    stacklevel=2
)

# 临时保留导入以避免破坏现有代码
try:
    from utils.shared_types import QueryResult
    from utils.types import QueryExecutionResult
except ImportError:
    pass

# 为了向后兼容，暂时保留其他导入
from .schemas import *
from .analysis_models import *
from .generation_models import *