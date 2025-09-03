"""LLM输出解析工具"""

import re
from typing import Dict, Any, Tuple, Optional


def parse_llm_output(output: str) -> Tuple[str, Optional[str]]:
    """
    解析LLM输出，分离思考内容和实际响应
    
    Args:
        output: LLM的原始输出
        
    Returns:
        (cleaned_output, thinking_content) - 清理后的输出和思考内容
    """
    # 提取<think>标签内的内容
    think_pattern = r'<think>(.*?)</think>'
    think_matches = re.findall(think_pattern, output, re.DOTALL)
    
    # 移除<think>标签及其内容
    cleaned_output = re.sub(think_pattern, '', output, flags=re.DOTALL).strip()
    
    # 合并所有思考内容
    thinking_content = '\n'.join(think_matches) if think_matches else None
    
    return cleaned_output, thinking_content


def clean_tool_response(response: Any) -> Any:
    """
    清理工具响应中的think标签
    
    Args:
        response: 工具的原始响应
        
    Returns:
        清理后的响应
    """
    if isinstance(response, str):
        cleaned, _ = parse_llm_output(response)
        return cleaned
    elif isinstance(response, dict):
        # 递归清理字典中的字符串值
        cleaned_dict = {}
        for key, value in response.items():
            if isinstance(value, str):
                cleaned_dict[key], _ = parse_llm_output(value)
            elif isinstance(value, dict):
                cleaned_dict[key] = clean_tool_response(value)
            elif isinstance(value, list):
                cleaned_dict[key] = [clean_tool_response(item) for item in value]
            else:
                cleaned_dict[key] = value
        return cleaned_dict
    elif isinstance(response, list):
        return [clean_tool_response(item) for item in response]
    else:
        return response


def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """
    从文本中提取JSON内容
    
    Args:
        text: 包含JSON的文本
        
    Returns:
        解析后的JSON对象，如果失败返回None
    """
    import json
    
    # 先清理think标签
    cleaned_text, _ = parse_llm_output(text)
    
    # 尝试找到JSON块
    json_pattern = r'```json\s*(.*?)\s*```'
    json_match = re.search(json_pattern, cleaned_text, re.DOTALL)
    
    if json_match:
        json_str = json_match.group(1)
    else:
        # 尝试找到花括号包围的内容
        brace_pattern = r'\{[^{}]*\}'
        brace_match = re.search(brace_pattern, cleaned_text, re.DOTALL)
        if brace_match:
            json_str = brace_match.group(0)
        else:
            json_str = cleaned_text
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None