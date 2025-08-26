"""分析管道共享的工具函数

本模块包含多个分析管道共享的工具函数，
避免在各个管道中重复实现。
"""

import math
from collections import Counter
from typing import List, Any, Optional
import logging

logger = logging.getLogger(__name__)


def calculate_entropy(samples: List[Any]) -> float:
    """计算熵值（归一化到0-1）
    
    使用信息熵公式计算数据的多样性，并归一化到0-1范围。
    
    参数:
        samples: 样本数据列表
        
    返回:
        归一化的熵值（0-1），0表示完全相同，1表示最大多样性
    """
    if not samples:
        return 0.0
    
    # 计算频率
    counter = Counter(samples)
    total = len(samples)
    
    # 计算熵
    entropy = 0.0
    for count in counter.values():
        if count > 0:
            p = count / total
            entropy -= p * math.log2(p)
    
    # 归一化
    if len(counter) > 1:
        max_entropy = math.log2(len(counter))
        normalized_entropy = entropy / max_entropy
    else:
        normalized_entropy = 0.0
    
    return min(max(normalized_entropy, 0.0), 1.0)


def get_entropy_level(entropy: float) -> str:
    """获取熵值级别
    
    参数:
        entropy: 熵值（0-1）
        
    返回:
        熵值级别：low, medium, high
    """
    if entropy < 0.3:
        return 'low'
    elif entropy < 0.7:
        return 'medium'
    else:
        return 'high'


# 黑名单功能已注释，处理完整数据库
# def should_skip_table(table_name: str, blacklist: set) -> bool:
#     """判断是否跳过表
#     
#     参数:
#         table_name: 表名
#         blacklist: 黑名单集合
#         
#     返回:
#         是否应该跳过
#     """
#     return table_name.lower() in blacklist

def should_skip_table(table_name: str, blacklist: set) -> bool:
    """判断是否跳过表（已禁用黑名单功能）
    
    参数:
        table_name: 表名
        blacklist: 黑名单集合
        
    返回:
        始终返回False，不跳过任何表
    """
    return False  # 不跳过任何表，处理完整数据库


def extract_base_type(data_type: str) -> str:
    """提取基本数据类型
    
    从完整的数据类型定义中提取基本类型。
    例如：varchar(100) -> STRING
    
    参数:
        data_type: 完整数据类型
        
    返回:
        基本类型
    """
    base = data_type.split('(')[0].upper()
    
    # 归类
    if base in ['INT', 'BIGINT', 'SMALLINT', 'TINYINT', 'INTEGER']:
        return 'INTEGER'
    elif base in ['VARCHAR', 'CHAR', 'TEXT', 'STRING']:
        return 'STRING'
    elif base in ['DECIMAL', 'FLOAT', 'DOUBLE', 'NUMERIC', 'REAL']:
        return 'NUMERIC'
    elif base in ['DATE', 'DATETIME', 'TIMESTAMP', 'TIME']:
        return 'DATETIME'
    elif base in ['BOOLEAN', 'BOOL']:
        return 'BOOLEAN'
    elif base in ['BINARY', 'VARBINARY', 'BLOB']:
        return 'BINARY'
    else:
        return base


def batch_process_items(items: List[Any], batch_size: int) -> List[List[Any]]:
    """将项目列表分批
    
    参数:
        items: 待处理项目列表
        batch_size: 批大小
        
    返回:
        分批后的列表
    """
    batches = []
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        batches.append(batch)
    return batches


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """安全除法
    
    参数:
        numerator: 分子
        denominator: 分母
        default: 除零时的默认值
        
    返回:
        除法结果或默认值
    """
    if denominator == 0:
        return default
    return numerator / denominator