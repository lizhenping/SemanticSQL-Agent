"""
工具辅助函数
"""
import json
from typing import Any, Dict, Union


def parse_tool_input(tool_input: Any, expected_params: list = None) -> Dict[str, Any]:
    """
    解析LangChain传递的工具输入参数
    
    LangChain可能以多种方式传递参数：
    1. 直接作为参数：tool(param1=value1, param2=value2)
    2. 作为JSON字符串：tool('{"param1": value1, "param2": value2}')
    3. 混合模式：第一个参数是JSON字符串，其他参数通过kwargs传递
    
    Args:
        tool_input: 工具接收到的输入（可能是字符串、字典或其他）
        expected_params: 期望的参数名列表
        
    Returns:
        解析后的参数字典
    """
    result = {}
    
    # 处理字符串输入
    if isinstance(tool_input, str) and tool_input.strip():
        # 如果是JSON字符串
        if tool_input.strip().startswith('{'):
            try:
                parsed = json.loads(tool_input)
                if isinstance(parsed, dict):
                    result.update(parsed)
            except json.JSONDecodeError:
                # 如果不是有效的JSON，可能是单个值
                if expected_params and len(expected_params) > 0:
                    # 将字符串值赋给第一个期望的参数
                    result[expected_params[0]] = tool_input
        else:
            # 普通字符串，赋给第一个期望的参数
            if expected_params and len(expected_params) > 0:
                result[expected_params[0]] = tool_input
                
    # 处理字典输入
    elif isinstance(tool_input, dict):
        result.update(tool_input)
        
    # 处理其他类型（数字、布尔值等）
    elif tool_input is not None:
        if expected_params and len(expected_params) > 0:
            result[expected_params[0]] = tool_input
            
    return result


def merge_tool_params(primary_input: Any, kwargs: Dict[str, Any], expected_params: list = None) -> Dict[str, Any]:
    """
    合并工具的主要输入和kwargs参数
    
    Args:
        primary_input: 主要输入参数
        kwargs: 其他关键字参数
        expected_params: 期望的参数名列表
        
    Returns:
        合并后的参数字典
    """
    # 先解析主要输入
    params = parse_tool_input(primary_input, expected_params)
    
    # 再合并kwargs（kwargs的优先级更高）
    for key, value in kwargs.items():
        if key not in params or params[key] is None:
            params[key] = value
            
    return params