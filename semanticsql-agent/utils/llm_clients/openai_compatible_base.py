"""OpenAI 兼容的客户端基类"""

import json
import logging
from typing import List, Dict, Any
import requests

from .base_client import BaseLLMClient
from .llm_basics import LLMMessage, LLMResponse, LLMUsage

logger = logging.getLogger(__name__)


class OpenAICompatibleClient(BaseLLMClient):
    """OpenAI API 兼容的客户端基类
    
    支持 OpenAI、Azure、本地部署等兼容 OpenAI API 的服务
    """
    
    def __init__(
        self, 
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        temperature: float = 0.0,
        max_tokens: int = 2000
    ):
        super().__init__(api_key, base_url)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
    
    def chat(self, messages: List[LLMMessage]) -> LLMResponse:
        """发送聊天请求"""
        # 转换消息格式
        formatted_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        
        # 构建请求
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        data = {
            "model": self.model,
            "messages": formatted_messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        
        # 发送请求
        url = f"{self.base_url}/chat/completions"
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            return self._parse_response(result)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API 请求失败: {e}")
            raise RuntimeError(f"API 请求失败: {e}")
        except (KeyError, json.JSONDecodeError) as e:
            logger.error(f"响应解析失败: {e}")
            raise RuntimeError(f"响应解析失败: {e}")
    
    def _parse_response(self, result: Dict[str, Any]) -> LLMResponse:
        """解析 API 响应"""
        choice = result["choices"][0]
        
        # 解析 token 使用情况
        usage = None
        if "usage" in result:
            usage = LLMUsage(
                input_tokens=result["usage"].get("prompt_tokens", 0),
                output_tokens=result["usage"].get("completion_tokens", 0),
                total_tokens=result["usage"].get("total_tokens", 0)
            )
        
        return LLMResponse(
            content=choice["message"]["content"],
            usage=usage,
            model=result.get("model", self.model),
            finish_reason=choice.get("finish_reason")
        )
    
    def get_model_name(self) -> str:
        """获取模型名称"""
        return self.model