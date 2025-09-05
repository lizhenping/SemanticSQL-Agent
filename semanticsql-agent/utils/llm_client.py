"""
LLM客户端 - 基于LangChain的ChatOpenAI，支持Qwen模型
"""

import logging
from typing import Optional, Dict, Any, List
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)


class LLMClient:
    """LLM客户端，封装对Qwen模型的调用"""
    
    def __init__(
        self,
        model_name: str = "Qwen3-14B",
        base_url: str = "http://localhost:9991/v1",
        api_key: str = "dummy-key",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: int = 60,
        **kwargs
    ):
        """
        初始化LLM客户端
        
        Args:
            model_name: 模型名称
            base_url: API基础URL
            api_key: API密钥
            temperature: 温度参数
            max_tokens: 最大token数
            timeout: 超时时间（秒）
            **kwargs: 其他参数
        """
        self.model_name = model_name
        self.base_url = base_url
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        
        # 创建ChatOpenAI实例
        try:
            self.client = ChatOpenAI(
                model=model_name,
                openai_api_base=base_url,
                openai_api_key=api_key,
                temperature=temperature,
                max_tokens=max_tokens,
                request_timeout=timeout,
                **kwargs
            )
            logger.info(f"LLM客户端初始化成功: {model_name} @ {base_url}")
        except Exception as e:
            logger.error(f"LLM客户端初始化失败: {e}")
            raise
    
    def invoke(
        self, 
        messages: List[BaseMessage],
        **kwargs
    ) -> str:
        """
        调用LLM生成回复
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数
            
        Returns:
            LLM生成的回复文本
        """
        try:
            response = self.client.invoke(messages, **kwargs)
            return response.content
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            raise
    
    def generate(
        self,
        messages_list: List[List[BaseMessage]],
        **kwargs
    ) -> LLMResult:
        """
        批量生成
        
        Args:
            messages_list: 消息列表的列表
            **kwargs: 其他参数
            
        Returns:
            LLM生成结果
        """
        try:
            return self.client.generate(messages_list, **kwargs)
        except Exception as e:
            logger.error(f"LLM批量生成失败: {e}")
            raise
    
    def stream(
        self,
        messages: List[BaseMessage],
        **kwargs
    ):
        """
        流式生成
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数
            
        Yields:
            流式生成的token
        """
        try:
            for chunk in self.client.stream(messages, **kwargs):
                yield chunk
        except Exception as e:
            logger.error(f"LLM流式生成失败: {e}")
            raise
    
    def create_messages(
        self,
        system_prompt: Optional[str] = None,
        user_prompt: str = "",
        **kwargs
    ) -> List[BaseMessage]:
        """
        创建消息列表
        
        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            **kwargs: 其他参数
            
        Returns:
            消息列表
        """
        messages = []
        
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        
        if user_prompt:
            messages.append(HumanMessage(content=user_prompt))
        
        return messages
    
    def simple_invoke(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        简单调用接口
        
        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
            **kwargs: 其他参数
            
        Returns:
            LLM回复
        """
        messages = self.create_messages(
            system_prompt=system_prompt,
            user_prompt=prompt
        )
        return self.invoke(messages, **kwargs)
    
    def get_client(self) -> ChatOpenAI:
        """
        获取底层的ChatOpenAI客户端
        
        Returns:
            ChatOpenAI实例
        """
        return self.client
    
    def test_connection(self) -> bool:
        """
        测试连接
        
        Returns:
            连接是否成功
        """
        try:
            test_messages = [HumanMessage(content="Hello")]
            response = self.invoke(test_messages)
            logger.info("LLM连接测试成功")
            return True
        except Exception as e:
            logger.error(f"LLM连接测试失败: {e}")
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        获取模型信息
        
        Returns:
            模型信息字典
        """
        return {
            "model_name": self.model_name,
            "base_url": self.base_url,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout
        }


def create_llm_client(
    model_name: str = "Qwen3-14B",
    base_url: str = "http://localhost:9991/v1",
    api_key: str = "dummy-key",
    temperature: float = 0.7,
    max_tokens: int = 4096,
    **kwargs
) -> LLMClient:
    """
    创建LLM客户端的工厂函数
    
    Args:
        model_name: 模型名称
        base_url: API基础URL
        api_key: API密钥
        temperature: 温度参数
        max_tokens: 最大token数
        **kwargs: 其他参数
        
    Returns:
        LLM客户端实例
    """
    return LLMClient(
        model_name=model_name,
        base_url=base_url,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs
    )


def create_qwen_client(
    base_url: str = "http://localhost:9991/v1",
    model_name: str = "Qwen3-14B",
    temperature: float = 0.7,
    **kwargs
) -> LLMClient:
    """
    创建Qwen专用客户端
    
    Args:
        base_url: Qwen API地址
        model_name: Qwen模型名称
        temperature: 温度参数
        **kwargs: 其他参数
        
    Returns:
        配置好的Qwen客户端
    """
    return create_llm_client(
        model_name=model_name,
        base_url=base_url,
        api_key="dummy-key",  # Qwen通常不需要真实的API密钥
        temperature=temperature,
        **kwargs
    )
