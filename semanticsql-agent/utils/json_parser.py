"""简单的 JSON 解析工具"""

import json
import re
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    """从文本中提取 JSON
    
    尝试多种方式：
    1. 直接解析
    2. 提取 ```json 代码块
    3. 提取 {} 包围的内容
    """
    # 1. 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # 2. 提取 JSON 代码块
    json_match = re.search(r'```json\s*\n(.*?)\n```', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # 3. 提取大括号内容
    brace_match = re.search(r'\{[^{}]*\}', text)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass
    
    return None


def extract_code(text: str, language: str = "sql") -> Optional[str]:
    """从文本中提取代码块
    
    Args:
        text: 输入文本
        language: 代码语言（sql, python 等）
    
    Returns:
        提取的代码，如果没有找到返回 None
    """
    # 查找指定语言的代码块
    pattern = rf'```{language}\s*\n(.*?)\n```'
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # 查找通用代码块
    match = re.search(r'```\s*\n(.*?)\n```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    return None


def parse_list(text: str) -> List[str]:
    """从文本中解析列表
    
    支持：
    - 数字列表（1. item）
    - 无序列表（- item 或 * item）
    """
    items = []
    lines = text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        
        # 数字列表
        num_match = re.match(r'^\d+[\.)]\s*(.+)$', line)
        if num_match:
            items.append(num_match.group(1).strip())
            continue
        
        # 无序列表
        bullet_match = re.match(r'^[-*•]\s*(.+)$', line)
        if bullet_match:
            items.append(bullet_match.group(1).strip())
    
    return items