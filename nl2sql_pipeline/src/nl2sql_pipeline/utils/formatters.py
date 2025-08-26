"""通用格式化工具

提供JSON、表格、列表等通用格式化功能。
"""

import json
from typing import Any, List, Dict, Optional
from tabulate import tabulate


def format_json(data: Any, indent: int = 2, ensure_ascii: bool = False) -> str:
    """格式化为JSON字符串
    
    Args:
        data: 要格式化的数据
        indent: 缩进空格数
        ensure_ascii: 是否确保ASCII编码
        
    Returns:
        格式化后的JSON字符串
    """
    try:
        return json.dumps(data, indent=indent, ensure_ascii=ensure_ascii, default=str)
    except Exception as e:
        return f"JSON formatting error: {str(e)}"


def format_table(headers: List[str], rows: List[List[Any]], 
                 tablefmt: str = "grid", max_width: Optional[int] = None) -> str:
    """格式化为表格
    
    Args:
        headers: 表头列表
        rows: 数据行列表
        tablefmt: 表格格式 (grid, simple, pretty, etc.)
        max_width: 最大列宽
        
    Returns:
        格式化后的表格字符串
    """
    if not rows:
        return "No data to display"
    
    # 处理列宽限制
    if max_width:
        rows = [
            [_truncate_cell(cell, max_width) for cell in row]
            for row in rows
        ]
    
    try:
        return tabulate(rows, headers=headers, tablefmt=tablefmt)
    except Exception as e:
        return f"Table formatting error: {str(e)}"


def format_list(items: List[Any], bullet: str = "-", indent: int = 2) -> str:
    """格式化为列表
    
    Args:
        items: 列表项
        bullet: 项目符号
        indent: 缩进空格数
        
    Returns:
        格式化后的列表字符串
    """
    if not items:
        return "Empty list"
    
    indent_str = " " * indent
    lines = []
    
    for item in items:
        if isinstance(item, dict):
            # 格式化字典项
            lines.append(f"{bullet} {_format_dict_item(item, indent)}")
        elif isinstance(item, list):
            # 嵌套列表
            lines.append(f"{bullet} [{len(item)} items]")
            sub_list = format_list(item, bullet="  •", indent=indent+2)
            lines.append(indent_str + sub_list)
        else:
            lines.append(f"{bullet} {str(item)}")
    
    return '\n'.join(lines)


def format_dict_as_table(data: Dict[str, Any], key_header: str = "Key", 
                        value_header: str = "Value") -> str:
    """将字典格式化为表格
    
    Args:
        data: 字典数据
        key_header: 键列的表头
        value_header: 值列的表头
        
    Returns:
        格式化后的表格字符串
    """
    if not data:
        return "Empty dictionary"
    
    rows = []
    for key, value in data.items():
        # 处理复杂值
        if isinstance(value, (list, dict)):
            value_str = json.dumps(value, ensure_ascii=False)
            if len(value_str) > 50:
                value_str = value_str[:47] + "..."
        else:
            value_str = str(value)
        
        rows.append([key, value_str])
    
    return format_table([key_header, value_header], rows, tablefmt="simple")


def format_statistics(stats: Dict[str, Any], title: str = "Statistics") -> str:
    """格式化统计信息
    
    Args:
        stats: 统计数据字典
        title: 标题
        
    Returns:
        格式化后的统计信息
    """
    lines = [f"=== {title} ==="]
    
    for key, value in stats.items():
        key_display = key.replace('_', ' ').title()
        
        if isinstance(value, float):
            lines.append(f"{key_display}: {value:.2f}")
        elif isinstance(value, int):
            lines.append(f"{key_display}: {value:,}")
        elif isinstance(value, dict):
            lines.append(f"\n{key_display}:")
            for sub_key, sub_value in value.items():
                lines.append(f"  - {sub_key}: {sub_value}")
        else:
            lines.append(f"{key_display}: {value}")
    
    return '\n'.join(lines)


def format_progress(current: int, total: int, width: int = 50, 
                   prefix: str = "Progress", suffix: str = "") -> str:
    """格式化进度条
    
    Args:
        current: 当前进度
        total: 总数
        width: 进度条宽度
        prefix: 前缀文本
        suffix: 后缀文本
        
    Returns:
        格式化后的进度条
    """
    percent = current / total if total > 0 else 0
    filled = int(width * percent)
    bar = '█' * filled + '░' * (width - filled)
    
    return f"{prefix} |{bar}| {percent*100:.1f}% {suffix}"


# 私有辅助函数

def _truncate_cell(cell: Any, max_width: int) -> str:
    """截断单元格内容"""
    cell_str = str(cell)
    if len(cell_str) > max_width:
        return cell_str[:max_width-3] + "..."
    return cell_str


def _format_dict_item(item: Dict[str, Any], indent: int) -> str:
    """格式化字典项"""
    if len(item) == 1:
        key, value = next(iter(item.items()))
        return f"{key}: {value}"
    else:
        # 多个键值对，缩进显示
        lines = ["{"]
        for key, value in item.items():
            lines.append(f"{' ' * (indent+2)}{key}: {value}")
        lines.append(f"{' ' * indent}")
        return '\n'.join(lines)