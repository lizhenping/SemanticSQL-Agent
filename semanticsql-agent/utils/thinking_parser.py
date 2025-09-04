"""LangChain Thinking 输出解析器"""

import re
from typing import Dict, Any

from langchain.schema import BaseOutputParser
from langchain.schema.output_parser import T


class ThinkingOutputParser(BaseOutputParser[Dict[str, Any]]):
    """解析包含<think>或<thinking>标签的LLM输出"""
    
    def parse(self, text: str) -> Dict[str, Any]:
        """
        解析LLM输出，分离思考过程和最终答案
        
        Args:
            text: LLM的原始输出
            
        Returns:
            包含thinking和answer的字典
        """
        # 支持<think>和<thinking>两种标签
        think_pattern = re.compile(
            r'<(?:think|thinking)>(.*?)</(?:think|thinking)>', 
            re.DOTALL | re.IGNORECASE
        )
        
        # 提取所有思考内容
        thinking_matches = think_pattern.findall(text)
        thinking_content = '\n'.join(thinking_matches) if thinking_matches else ""
        
        # 移除thinking标签，获取最终答案
        final_answer = think_pattern.sub('', text).strip()
        
        return {
            "thinking": thinking_content.strip(),
            "answer": final_answer,
            "has_thinking": bool(thinking_matches)
        }
    
    @property
    def _type(self) -> str:
        """返回解析器类型"""
        return "thinking"
    
    def get_format_instructions(self) -> str:
        """返回格式说明"""
        return """
你可以使用<thinking>标签来记录你的思考过程。
例如：
<thinking>
这里是我的分析和推理过程...
</thinking>

这是我的最终答案。
"""

