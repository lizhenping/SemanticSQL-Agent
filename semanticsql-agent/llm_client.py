"""简化的 LLM 客户端（参考 TRAEAgent）"""

import os
import logging
from typing import List, Optional, Dict, Any
import requests
import json

from .llm_basics import LLMMessage, LLMResponse, LLMUsage
from .config import ModelConfig

logger = logging.getLogger(__name__)


class LLMClient:
    """基础 LLM 客户端，支持 OpenAI 兼容的 API"""
    
    def __init__(self, config: ModelConfig):
        self.config = config
        self.api_key = config.api_key or os.getenv(f"{config.provider.upper()}_API_KEY", "")
        self.base_url = config.base_url or self._get_default_base_url(config.provider)
        
    def _get_default_base_url(self, provider: str) -> str:
        """获取默认的 API 地址"""
        defaults = {
            "openai": "https://api.openai.com/v1",
            "anthropic": "https://api.anthropic.com/v1",
            "azure": None,  # Azure 需要自定义 URL
        }
        return defaults.get(provider, "http://localhost:8000/v1")
    
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
            "model": self.config.model,
            "messages": formatted_messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        
        try:
            # 发送请求
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=60
            )
            response.raise_for_status()
            
            # 解析响应
            result = response.json()
            choice = result["choices"][0]
            
            # 构建响应
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
                model=result.get("model"),
                finish_reason=choice.get("finish_reason")
            )
            
        except requests.exceptions.RequestException as e:
            logger.error(f"LLM 请求失败: {e}")
            raise RuntimeError(f"LLM 请求失败: {e}")
        except (KeyError, json.JSONDecodeError) as e:
            logger.error(f"响应解析失败: {e}")
            raise RuntimeError(f"响应解析失败: {e}")
    
    def complete(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """简单的文本补全接口"""
        messages = []
        if system_prompt:
            messages.append(LLMMessage(role="system", content=system_prompt))
        messages.append(LLMMessage(role="user", content=prompt))
        
        response = self.chat(messages)
        return response.content