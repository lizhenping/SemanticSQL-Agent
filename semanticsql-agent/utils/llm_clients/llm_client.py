"""简化的 LLM 客户端 - 仅支持本地 Qwen (OpenAI 兼容接口)"""

import json
import logging
from typing import List, Optional
import requests

from .llm_basics import LLMMessage, LLMResponse, LLMUsage

logger = logging.getLogger(__name__)


class LLMClient:
    """本地 Qwen 模型客户端（OpenAI 兼容接口）"""
    
    def __init__(
        self,
        model: str = "Qwen3-14B",
        base_url: str = "http://192.168.200.216:9009/v1",
        api_key: str = "not-needed",
        temperature: float = 0.1,
        max_tokens: int = 2000
    ):
        self.model = model
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
    
    def chat(self, messages: List[LLMMessage]) -> LLMResponse:
        """发送聊天请求到本地 Qwen 模型"""
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
        
        url = f"{self.base_url}/chat/completions"
        
        try:
            logger.debug(f"发送请求到: {url}")
            response = requests.post(url, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            
            # 解析响应
            choice = result["choices"][0]
            content = choice["message"]["content"]
            
            # 解析 token 使用情况
            usage = None
            if "usage" in result:
                usage = LLMUsage(
                    input_tokens=result["usage"].get("prompt_tokens", 0),
                    output_tokens=result["usage"].get("completion_tokens", 0),
                    total_tokens=result["usage"].get("total_tokens", 0)
                )
            
            return LLMResponse(
                content=content,
                usage=usage,
                model=result.get("model", self.model),
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