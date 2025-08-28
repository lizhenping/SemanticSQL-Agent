"""简化的输出解析器"""

import json
import re
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def parse_json_output(text: str) -> Dict[str, Any]:
    """从 LLM 输出中解析 JSON
    
    Args:
        text: LLM 的输出文本
        
    Returns:
        解析后的字典，失败时返回空字典
    """
    # 1. 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # 2. 查找 JSON 代码块
    json_block_match = re.search(r'```json\s*\n(.*?)\n```', text, re.DOTALL)
    if json_block_match:
        try:
            return json.loads(json_block_match.group(1).strip())
        except json.JSONDecodeError:
            pass
    
    # 3. 查找大括号包围的内容
    brace_match = re.search(r'\{.*\}', text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass
    
    # 4. 返回空字典
    logger.warning(f"无法从文本中解析 JSON: {text[:100]}...")
    return {}


def parse_list_output(text: str) -> list:
    """从文本中解析列表
    
    支持多种格式：
    - JSON 数组
    - 编号列表（1. item）
    - 无序列表（- item 或 * item）
    """
    # 1. 尝试 JSON 解析
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass
    
    # 2. 查找 JSON 数组
    array_match = re.search(r'\[.*\]', text, re.DOTALL)
    if array_match:
        try:
            return json.loads(array_match.group(0))
        except json.JSONDecodeError:
            pass
    
    # 3. 解析文本列表
    lines = text.strip().split('\n')
    items = []
    
    for line in lines:
        line = line.strip()
        # 匹配编号列表
        num_match = re.match(r'^\d+[\.)]\s*(.+)$', line)
        if num_match:
            items.append(num_match.group(1).strip())
            continue
        
        # 匹配无序列表
        bullet_match = re.match(r'^[-*•]\s*(.+)$', line)
        if bullet_match:
            items.append(bullet_match.group(1).strip())
            continue
    
    return items if items else []


def create_structured_output_parser(expected_keys: list) -> callable:
    """创建一个简单的结构化输出解析器
    
    Args:
        expected_keys: 期望的字段列表
        
    Returns:
        解析函数
    """
    def parser(text: str) -> Dict[str, Any]:
        # 先尝试 JSON 解析
        result = parse_json_output(text)
        if result:
            return result
        
        # 否则尝试从文本中提取
        extracted = {}
        for key in expected_keys:
            # 查找 "key: value" 格式
            pattern = rf'{key}[:：]\s*([^\n]+)'
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted[key] = match.group(1).strip()
        
        return extracted
    
    return parser