"""LangChain LLM服务实现

使用LangChain集成各种LLM提供商。
"""

import logging
import json
import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.outputs import LLMResult

from .llm_service import LLMService

logger = logging.getLogger(__name__)


class LangChainLLMService(LLMService):
    """基于LangChain的LLM服务实现
    
    支持本地LLM API服务（兼容OpenAI格式）。
    """
    
    def __init__(self, config: Dict[str, Any]):
        """初始化LLM服务
        
        参数:
            config: LLM配置字典，包含provider、model等信息
        """
        super().__init__(config)
        self._init_llm()
    
    def _init_llm(self):
        """初始化LLM客户端"""
        import os
        
        # 获取配置参数，支持从配置文件、环境变量或命令行参数动态加载
        model = self.config.get('model') or os.getenv('OPENAI_MODEL', 'Qwen3-14B')
        api_key = self.config.get('api_key') or os.getenv('OPENAI_API_KEY', 'not-needed')
        base_url = self.config.get('base_url') or os.getenv('OPENAI_BASE_URL', 'http://192.168.200.216:9009/v1')
        temperature = self.config.get('temperature', 0.7)
        max_tokens = self.config.get('max_tokens', 4096)
        
        # 构建LLM参数
        llm_params = {
            'model': model,
            'temperature': temperature,
            'max_tokens': max_tokens,
            'api_key': api_key,
            'base_url': base_url
        }
        
        logger.info(f"使用本地LLM配置: model={model}, base_url={base_url}")
        
        # 创建ChatOpenAI实例（兼容本地API）
        self.llm = ChatOpenAI(**llm_params)
        
        logger.info("LLM服务初始化完成")
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """生成文本响应
        
        参数:
            prompt: 用户提示词
            system_prompt: 系统提示词（可选）
            
        返回:
            生成的文本
        """
        try:
            # 处理额外参数
            if 'max_tokens' in kwargs and hasattr(self.llm, 'max_tokens'):
                original_max_tokens = self.llm.max_tokens
                self.llm.max_tokens = kwargs['max_tokens']
            
            # 创建消息
            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.append(HumanMessage(content=prompt))
            
            # 调用LLM
            response = self.llm.invoke(messages)
            
            # 提取响应文本
            if hasattr(response, 'content'):
                raw_response = response.content
            else:
                raw_response = str(response)
            
            # 统一清理响应文本，移除<think>标签等
            cleaned_response = self._clean_llm_response(raw_response)
            return cleaned_response
                
        except Exception as e:
            logger.error(f"LLM生成失败: {e}")
            raise
        finally:
            # 恢复原始的max_tokens设置
            if 'max_tokens' in kwargs and hasattr(self.llm, 'max_tokens'):
                self.llm.max_tokens = original_max_tokens
    
    def generate_json(self, prompt: str, system_prompt: Optional[str] = None,
                     response_model: Optional[BaseModel] = None, **kwargs) -> Dict[str, Any]:
        """生成JSON格式的响应
        
        参数:
            prompt: 用户提示词
            system_prompt: 系统提示词（可选）
            response_model: 期望的响应模型（可选）
            
        返回:
            解析后的JSON对象
        """
        # 在提示词中明确要求JSON格式，并禁止思考标签
        json_prompt = prompt + "\n\n请以有效的JSON格式返回结果。不要包含任何<think>标签或其他解释性文本，直接输出JSON。"
        
        # 生成响应（已经过清理）
        response = self.generate(json_prompt, system_prompt, **kwargs)
        
        # 额外清理：确保移除可能残留的think标签
        response = self._clean_llm_response(response)
        
        # 解析JSON
        try:
            # 尝试直接解析
            return json.loads(response)
        except json.JSONDecodeError:
            # 如果失败，尝试提取JSON部分
            extracted = self._extract_json(response)
            if extracted:
                return extracted
            else:
                logger.warning(f"无法解析LLM响应为JSON，响应内容: {response[:200]}...")
                return {"response": response}
    
    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """从文本中提取JSON内容
        
        参数:
            text: 包含JSON的文本
            
        返回:
            提取的JSON对象或None
        """
        # 尝试找到JSON块
        # 方法1: 查找```json块
        json_match = re.search(r'```json\s*\n(.*?)\n```', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # 方法2: 查找{}或[]包围的内容
        # 找到第一个{或[
        start_idx = -1
        for i, char in enumerate(text):
            if char in '{[':
                start_idx = i
                break
        
        if start_idx >= 0:
            # 找到匹配的结束符
            bracket_count = 0
            end_idx = -1
            in_string = False
            escape_next = False
            
            for i in range(start_idx, len(text)):
                char = text[i]
                
                if escape_next:
                    escape_next = False
                    continue
                
                if char == '\\':
                    escape_next = True
                    continue
                
                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue
                
                if not in_string:
                    if char in '{[':
                        bracket_count += 1
                    elif char in '}]':
                        bracket_count -= 1
                        if bracket_count == 0:
                            end_idx = i + 1
                            break
            
            if end_idx > start_idx:
                try:
                    json_str = text[start_idx:end_idx]
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass
        
        return None
    
    def _clean_llm_response(self, response: str) -> str:
        """清理LLM响应文本
        
        统一处理所有LLM响应，移除<think>标签、多余空白等
        
        参数:
            response: 原始LLM响应
            
        返回:
            清理后的响应文本
        """
        if not response:
            return response
        
        # 移除<think>标签及其内容（包括未闭合的标签）
        cleaned = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL | re.IGNORECASE)
        # 移除未闭合的<think>标签及其后的所有内容
        cleaned = re.sub(r'<think>.*', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
        
        # 移除其他可能的思考标签格式
        cleaned = re.sub(r'<thinking>.*?</thinking>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r'<reasoning>.*?</reasoning>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
        
        # 移除Markdown代码块标记（如果存在）
        cleaned = re.sub(r'^```(?:json)?\s*\n', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'\n```\s*$', '', cleaned, flags=re.MULTILINE)
        
        # 移除多余的空白字符
        cleaned = re.sub(r'\n\s*\n', '\n', cleaned)
        cleaned = cleaned.strip()
        
        return cleaned
    
    def batch_generate(self, prompts: List[str], system_prompt: Optional[str] = None) -> List[str]:
        """批量生成文本
        
        参数:
            prompts: 提示词列表
            system_prompt: 系统提示词（可选）
            
        返回:
            生成的文本列表
        """
        results = []
        
        # 暂时使用串行处理，后续可以优化为并行
        for prompt in prompts:
            try:
                result = self.generate(prompt, system_prompt)
                results.append(result)
            except Exception as e:
                logger.error(f"批量生成中的单个请求失败: {e}")
                results.append("")  # 失败时添加空字符串
        
        return results
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息
        
        返回:
            包含模型信息的字典
        """
        import os
        return {
            'model': self.config.get('model') or os.getenv('OPENAI_MODEL', 'Qwen3-14B'),
            'base_url': self.config.get('base_url') or os.getenv('OPENAI_BASE_URL', 'http://192.168.200.216:9009/v1'),
            'api_key': self.config.get('api_key') or os.getenv('OPENAI_API_KEY', 'not-needed'),
            'temperature': self.config.get('temperature', 0.7),
            'max_tokens': self.config.get('max_tokens', 8192)
        }
    
    def set_temperature(self, temperature: float):
        """设置生成温度
        
        参数:
            temperature: 温度值（0-1）
        """
        if hasattr(self.llm, 'temperature'):
            self.llm.temperature = temperature
        self.config['temperature'] = temperature
    
    def set_max_tokens(self, max_tokens: int):
        """设置最大token数
        
        参数:
            max_tokens: 最大token数
        """
        if hasattr(self.llm, 'max_tokens'):
            self.llm.max_tokens = max_tokens
        self.config['max_tokens'] = max_tokens