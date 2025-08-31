"""
LLM客户端封装 - 支持OpenAI API兼容的模型
"""

import logging
import time
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from openai import OpenAI
import json

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """LLM响应数据类"""
    content: str
    model: str
    usage: Dict[str, int]
    finish_reason: str
    raw_response: Any = None


class LLMClient:
    """统一的LLM客户端"""
    
    def __init__(self, 
                 model: str = "gpt-3.5-turbo",
                 base_url: str = None,
                 api_key: str = None,
                 temperature: float = 0.7,
                 max_tokens: int = 2000,
                 timeout: int = 30,
                 max_retries: int = 3):
        """
        初始化LLM客户端
        
        Args:
            model: 模型名称
            base_url: API基础URL
            api_key: API密钥
            temperature: 生成温度
            max_tokens: 最大token数
            timeout: 请求超时时间
            max_retries: 最大重试次数
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries
        
        # 初始化OpenAI客户端
        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key or "not-needed",
            timeout=timeout
        )
        
        logger.info(f"LLM client initialized with model: {model}")
    
    def chat(self, 
             messages: List[Dict[str, str]],
             temperature: float = None,
             max_tokens: int = None,
             stream: bool = False,
             **kwargs) -> LLMResponse:
        """
        发送聊天请求
        
        Args:
            messages: 消息列表
            temperature: 温度（覆盖默认值）
            max_tokens: 最大token数（覆盖默认值）
            stream: 是否流式输出
            **kwargs: 其他参数
            
        Returns:
            LLM响应
        """
        temperature = temperature if temperature is not None else self.temperature
        max_tokens = max_tokens if max_tokens is not None else self.max_tokens
        
        # 重试逻辑
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=stream,
                    **kwargs
                )
                
                if stream:
                    return self._handle_stream_response(response)
                else:
                    return self._parse_response(response)
                    
            except Exception as e:
                logger.warning(f"LLM request failed (attempt {attempt + 1}): {e}")
                
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # 指数退避
                else:
                    logger.error(f"LLM request failed after {self.max_retries} attempts")
                    raise
    
    def complete(self, 
                 prompt: str,
                 system_prompt: str = None,
                 **kwargs) -> LLMResponse:
        """
        简化的完成接口
        
        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            **kwargs: 其他参数
            
        Returns:
            LLM响应
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        return self.chat(messages, **kwargs)
    
    def function_call(self,
                     messages: List[Dict[str, str]],
                     functions: List[Dict[str, Any]],
                     function_call: Union[str, Dict] = "auto",
                     **kwargs) -> Dict[str, Any]:
        """
        函数调用接口
        
        Args:
            messages: 消息列表
            functions: 函数定义列表
            function_call: 函数调用策略
            **kwargs: 其他参数
            
        Returns:
            函数调用结果
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                functions=functions,
                function_call=function_call,
                temperature=kwargs.get('temperature', 0.1),  # 函数调用使用低温度
                **kwargs
            )
            
            message = response.choices[0].message
            
            if message.function_call:
                return {
                    "function_name": message.function_call.name,
                    "arguments": json.loads(message.function_call.arguments)
                }
            else:
                return {
                    "content": message.content
                }
                
        except Exception as e:
            logger.error(f"Function call failed: {e}")
            raise
    
    def generate_sql(self, 
                    question: str,
                    schema_info: str,
                    dialect: str = "mysql",
                    **kwargs) -> str:
        """
        生成SQL查询
        
        Args:
            question: 自然语言问题
            schema_info: 数据库结构信息
            dialect: SQL方言
            **kwargs: 其他参数
            
        Returns:
            SQL查询语句
        """
        system_prompt = f"""You are a {dialect} SQL expert. Convert natural language questions to SQL queries.
        
Database Schema:
{schema_info}

Rules:
1. Generate only the SQL query, no explanations
2. Use proper {dialect} syntax
3. Optimize for performance
4. Ensure the query is safe and valid"""
        
        user_prompt = f"Question: {question}\n\nSQL Query:"
        
        response = self.complete(
            user_prompt,
            system_prompt=system_prompt,
            temperature=0.1,  # SQL生成使用低温度
            **kwargs
        )
        
        # 清理SQL
        sql = response.content.strip()
        sql = sql.replace("```sql", "").replace("```", "").strip()
        
        if not sql.endswith(";"):
            sql += ";"
        
        return sql
    
    def analyze_text(self,
                    text: str,
                    analysis_type: str = "general",
                    **kwargs) -> Dict[str, Any]:
        """
        文本分析
        
        Args:
            text: 要分析的文本
            analysis_type: 分析类型
            **kwargs: 其他参数
            
        Returns:
            分析结果
        """
        prompts = {
            "general": "Analyze the following text and provide key insights:",
            "sentiment": "Analyze the sentiment of the following text:",
            "summary": "Provide a concise summary of the following text:",
            "entity": "Extract entities (people, places, organizations) from the text:",
            "classification": "Classify the following text into appropriate categories:"
        }
        
        system_prompt = "You are a text analysis expert."
        user_prompt = f"{prompts.get(analysis_type, prompts['general'])}\n\n{text}"
        
        response = self.complete(
            user_prompt,
            system_prompt=system_prompt,
            **kwargs
        )
        
        return {
            "analysis_type": analysis_type,
            "result": response.content,
            "model": response.model
        }
    
    def _parse_response(self, response) -> LLMResponse:
        """解析响应"""
        choice = response.choices[0]
        
        return LLMResponse(
            content=choice.message.content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            },
            finish_reason=choice.finish_reason,
            raw_response=response
        )
    
    def _handle_stream_response(self, response):
        """处理流式响应"""
        content_parts = []
        
        for chunk in response:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                content_parts.append(content)
                yield content
        
        # 返回完整内容
        full_content = "".join(content_parts)
        return LLMResponse(
            content=full_content,
            model=self.model,
            usage={},  # 流式响应没有usage信息
            finish_reason="stream"
        )
    
    @classmethod
    def from_config(cls, config: Any) -> "LLMClient":
        """
        从配置创建客户端
        
        Args:
            config: 配置对象
            
        Returns:
            LLMClient实例
        """
        if hasattr(config, 'llm'):
            llm_config = config.llm
            return cls(
                model=llm_config.model,
                base_url=llm_config.base_url,
                api_key=llm_config.api_key,
                temperature=llm_config.temperature,
                max_tokens=llm_config.max_tokens,
                timeout=llm_config.timeout,
                max_retries=getattr(llm_config, 'max_retries', 3)
            )
        elif isinstance(config, dict):
            return cls(**config)
        else:
            raise ValueError("Invalid configuration type")


# 全局客户端实例
_global_client = None


def get_llm_client(config: Any = None) -> LLMClient:
    """
    获取全局LLM客户端
    
    Args:
        config: 配置对象（首次调用时需要）
        
    Returns:
        LLMClient实例
    """
    global _global_client
    
    if _global_client is None:
        if config is None:
            raise ValueError("Configuration required for first initialization")
        _global_client = LLMClient.from_config(config)
    
    return _global_client


def set_llm_client(client: LLMClient):
    """设置全局LLM客户端"""
    global _global_client
    _global_client = client