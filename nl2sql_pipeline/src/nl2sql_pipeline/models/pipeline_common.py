"""管道共享的数据模型和常量

本模块定义了多个分析管道共享的数据结构和常量，
避免在各个管道中重复定义。
"""

from dataclasses import dataclass, field
from typing import List, Any


# ========== 共享常量 ==========

# 黑名单机制已删除，aid_info表已在数据库获取源头直接过滤

# 默认配置
DEFAULT_SAMPLE_SIZE = 1000  # 字段采样数量
DEFAULT_MAX_TABLES = 50     # 最大处理表数
DEFAULT_BATCH_SIZE = 10     # 批处理大小


# ========== 共享数据模型 ==========

@dataclass
class FieldInfo:
    """字段信息
    
    用于在字段分类管道中存储字段的基本信息和样本数据。
    包含了计算出的熵值，用于评估字段数据的多样性。
    """
    field_name: str       # 完整字段名（table.column）
    table_name: str       # 表名
    column_name: str      # 列名
    data_type: str        # 数据类型
    samples: List[Any]    # 样本数据
    entropy: float = 0.0  # 熵值（0-1）