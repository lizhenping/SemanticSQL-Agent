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


class ReActThinkingParser(BaseOutputParser[Dict[str, Any]]):
    """专门用于ReAct模式的Thinking解析器"""
    
    def parse(self, text: str) -> Dict[str, Any]:
        """
        解析ReAct格式的输出，同时处理thinking标签
        
        Returns:
            包含action、action_input、thinking等信息的字典
        """
        # 先处理thinking标签
        thinking_parser = ThinkingOutputParser()
        thinking_result = thinking_parser.parse(text)
        
        cleaned_text = thinking_result["answer"]
        
        # 解析ReAct格式
        action_match = re.search(r'Action:\s*(.+)', cleaned_text)
        action_input_match = re.search(r'Action Input:\s*(.+)', cleaned_text)
        thought_match = re.search(r'Thought:\s*(.+?)(?=Action:|$)', cleaned_text, re.DOTALL)
        final_answer_match = re.search(r'Final Answer:\s*(.+)', cleaned_text, re.DOTALL)
        
        return {
            "thinking": thinking_result["thinking"],
            "thought": thought_match.group(1).strip() if thought_match else "",
            "action": action_match.group(1).strip() if action_match else None,
            "action_input": action_input_match.group(1).strip() if action_input_match else None,
            "final_answer": final_answer_match.group(1).strip() if final_answer_match else None,
            "is_final": final_answer_match is not None
        }
    
    @property
    def _type(self) -> str:
        return "react_thinking"