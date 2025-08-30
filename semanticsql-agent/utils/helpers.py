"""
通用辅助函数
"""

import re
import hashlib
import json
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, date, timedelta
import unicodedata
from pathlib import Path


def sanitize_sql(sql: str) -> str:
    """
    清理和规范化SQL语句
    
    Args:
        sql: 原始SQL语句
        
    Returns:
        清理后的SQL语句
    """
    # 移除多余空白
    sql = re.sub(r'\s+', ' ', sql.strip())
    
    # 移除注释
    sql = re.sub(r'--[^\n]*', '', sql)
    sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
    
    # 确保分号结尾
    if not sql.endswith(';'):
        sql += ';'
    
    return sql


def extract_table_names(sql: str) -> List[str]:
    """
    从SQL语句中提取表名
    
    Args:
        sql: SQL语句
        
    Returns:
        表名列表
    """
    tables = []
    
    # FROM子句
    from_pattern = r'FROM\s+([^\s,]+)(?:\s+AS\s+\w+)?'
    tables.extend(re.findall(from_pattern, sql, re.IGNORECASE))
    
    # JOIN子句
    join_pattern = r'JOIN\s+([^\s,]+)(?:\s+AS\s+\w+)?'
    tables.extend(re.findall(join_pattern, sql, re.IGNORECASE))
    
    # INTO子句 (INSERT)
    into_pattern = r'INTO\s+([^\s(]+)'
    tables.extend(re.findall(into_pattern, sql, re.IGNORECASE))
    
    # UPDATE子句
    update_pattern = r'UPDATE\s+([^\s]+)'
    tables.extend(re.findall(update_pattern, sql, re.IGNORECASE))
    
    # DELETE FROM子句
    delete_pattern = r'DELETE\s+FROM\s+([^\s]+)'
    tables.extend(re.findall(delete_pattern, sql, re.IGNORECASE))
    
    # 去重并移除引号
    tables = list(set(t.strip('`"[]') for t in tables))
    
    return tables


def normalize_string(text: str) -> str:
    """
    规范化字符串（用于比较）
    
    Args:
        text: 输入文本
        
    Returns:
        规范化后的文本
    """
    # 转小写
    text = text.lower()
    
    # 移除重音符号
    text = ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )
    
    # 移除多余空白
    text = re.sub(r'\s+', ' ', text.strip())
    
    return text


def calculate_hash(data: Any, algorithm: str = 'sha256') -> str:
    """
    计算数据的哈希值
    
    Args:
        data: 数据
        algorithm: 哈希算法
        
    Returns:
        哈希值字符串
    """
    if not isinstance(data, (str, bytes)):
        data = json.dumps(data, sort_keys=True, ensure_ascii=False)
    
    if isinstance(data, str):
        data = data.encode('utf-8')
    
    if algorithm == 'md5':
        hasher = hashlib.md5()
    elif algorithm == 'sha1':
        hasher = hashlib.sha1()
    elif algorithm == 'sha256':
        hasher = hashlib.sha256()
    elif algorithm == 'sha512':
        hasher = hashlib.sha512()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")
    
    hasher.update(data)
    return hasher.hexdigest()


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    截断字符串
    
    Args:
        text: 原始文本
        max_length: 最大长度
        suffix: 后缀
        
    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def format_duration(seconds: float) -> str:
    """
    格式化持续时间
    
    Args:
        seconds: 秒数
        
    Returns:
        格式化的时间字符串
    """
    if seconds < 1:
        return f"{seconds*1000:.2f}ms"
    elif seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.0f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def parse_bool(value: Union[str, bool, int]) -> bool:
    """
    解析布尔值
    
    Args:
        value: 输入值
        
    Returns:
        布尔值
    """
    if isinstance(value, bool):
        return value
    
    if isinstance(value, int):
        return value != 0
    
    if isinstance(value, str):
        value = value.lower().strip()
        if value in ('true', 'yes', '1', 'on', 'y', 't'):
            return True
        elif value in ('false', 'no', '0', 'off', 'n', 'f'):
            return False
    
    raise ValueError(f"Cannot parse '{value}' as boolean")


def deep_merge(dict1: Dict, dict2: Dict) -> Dict:
    """
    深度合并两个字典
    
    Args:
        dict1: 第一个字典
        dict2: 第二个字典（优先级更高）
        
    Returns:
        合并后的字典
    """
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    
    return result


def chunk_list(lst: List, chunk_size: int) -> List[List]:
    """
    将列表分块
    
    Args:
        lst: 原始列表
        chunk_size: 块大小
        
    Returns:
        分块后的列表
    """
    chunks = []
    for i in range(0, len(lst), chunk_size):
        chunks.append(lst[i:i + chunk_size])
    return chunks


def flatten_dict(d: Dict, parent_key: str = '', sep: str = '.') -> Dict:
    """
    扁平化嵌套字典
    
    Args:
        d: 嵌套字典
        parent_key: 父键
        sep: 分隔符
        
    Returns:
        扁平化的字典
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def unflatten_dict(d: Dict, sep: str = '.') -> Dict:
    """
    反扁平化字典
    
    Args:
        d: 扁平字典
        sep: 分隔符
        
    Returns:
        嵌套字典
    """
    result = {}
    for key, value in d.items():
        parts = key.split(sep)
        current = result
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
    return result


def safe_get(d: Dict, path: str, default: Any = None, sep: str = '.') -> Any:
    """
    安全获取嵌套字典值
    
    Args:
        d: 字典
        path: 路径
        default: 默认值
        sep: 分隔符
        
    Returns:
        值或默认值
    """
    keys = path.split(sep)
    current = d
    
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    
    return current


def format_table_name(name: str, dialect: str = 'mysql') -> str:
    """
    格式化表名（添加引号）
    
    Args:
        name: 表名
        dialect: SQL方言
        
    Returns:
        格式化的表名
    """
    if dialect == 'mysql':
        return f"`{name}`"
    elif dialect == 'postgresql':
        return f'"{name}"'
    elif dialect == 'sqlite':
        return f'"{name}"'
    elif dialect == 'mssql':
        return f"[{name}]"
    else:
        return name


def is_valid_identifier(name: str) -> bool:
    """
    检查是否为有效的SQL标识符
    
    Args:
        name: 标识符名称
        
    Returns:
        是否有效
    """
    # 基本规则：字母开头，包含字母、数字、下划线
    pattern = r'^[a-zA-Z][a-zA-Z0-9_]*$'
    return bool(re.match(pattern, name))


def camel_to_snake(name: str) -> str:
    """
    驼峰命名转蛇形命名
    
    Args:
        name: 驼峰命名字符串
        
    Returns:
        蛇形命名字符串
    """
    # 在大写字母前插入下划线
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def snake_to_camel(name: str, upper_first: bool = False) -> str:
    """
    蛇形命名转驼峰命名
    
    Args:
        name: 蛇形命名字符串
        upper_first: 首字母是否大写
        
    Returns:
        驼峰命名字符串
    """
    components = name.split('_')
    if upper_first:
        return ''.join(x.title() for x in components)
    else:
        return components[0] + ''.join(x.title() for x in components[1:])


def estimate_token_count(text: str) -> int:
    """
    估算文本的token数量
    
    Args:
        text: 文本
        
    Returns:
        估算的token数
    """
    # 简单估算：平均每4个字符一个token
    # 对中文，平均每个字符一个token
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    other_chars = len(text) - chinese_chars
    
    return chinese_chars + other_chars // 4


def create_backup_name(filename: str, timestamp: bool = True) -> str:
    """
    创建备份文件名
    
    Args:
        filename: 原始文件名
        timestamp: 是否添加时间戳
        
    Returns:
        备份文件名
    """
    path = Path(filename)
    
    if timestamp:
        time_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"{path.stem}_backup_{time_str}{path.suffix}"
    else:
        backup_name = f"{path.stem}_backup{path.suffix}"
    
    if path.parent != Path('.'):
        backup_name = str(path.parent / backup_name)
    
    return backup_name


def format_size(bytes_size: int) -> str:
    """
    格式化文件大小
    
    Args:
        bytes_size: 字节大小
        
    Returns:
        格式化的大小字符串
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"


def mask_sensitive_data(text: str, mask_char: str = '*') -> str:
    """
    掩码敏感数据
    
    Args:
        text: 原始文本
        mask_char: 掩码字符
        
    Returns:
        掩码后的文本
    """
    # 掩码密码
    text = re.sub(
        r'(password|passwd|pwd)(["\':=\s]+)([^"\'\s]+)',
        lambda m: f"{m.group(1)}{m.group(2)}{mask_char * len(m.group(3))}",
        text,
        flags=re.IGNORECASE
    )
    
    # 掩码API密钥
    text = re.sub(
        r'(api[_-]?key|apikey|token)(["\':=\s]+)([^"\'\s]+)',
        lambda m: f"{m.group(1)}{m.group(2)}{mask_char * len(m.group(3))}",
        text,
        flags=re.IGNORECASE
    )
    
    # 掩码邮箱
    text = re.sub(
        r'([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
        lambda m: f"{m.group(1)[:2]}{mask_char * (len(m.group(1))-2)}@{m.group(2)}",
        text
    )
    
    return text


def retry_with_backoff(func, max_retries: int = 3, backoff_factor: float = 2.0):
    """
    带退避的重试装饰器
    
    Args:
        func: 要执行的函数
        max_retries: 最大重试次数
        backoff_factor: 退避因子
        
    Returns:
        装饰后的函数
    """
    import time
    import functools
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        retry_count = 0
        delay = 1.0
        
        while retry_count < max_retries:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                retry_count += 1
                if retry_count >= max_retries:
                    raise
                
                time.sleep(delay)
                delay *= backoff_factor
        
        return None
    
    return wrapper