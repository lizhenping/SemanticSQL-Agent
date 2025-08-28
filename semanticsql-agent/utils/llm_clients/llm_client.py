"""LLM 客户端 - 直接使用 OpenAI SDK"""

import logging
from typing import List, Optional, Dict, Any
from openai import OpenAI

from .llm_basics import LLMMessage, LLMResponse, LLMUsage, ToolCall, ToolResult

logger = logging.getLogger(__name__)


class LLMClient:
    """使用 OpenAI SDK 调用本地 Qwen 模型"""
    
    def __init__(
        self,
        model: str = "Qwen3-14B",
        base_url: str = "http://192.168.200.216:9009/v1",
        api_key: str = "not-needed",
        temperature: float = 0.1,
        max_tokens: int = 2000
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # 创建 OpenAI 客户端
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        
        self.message_history: List[Dict[str, Any]] = []
    
    def set_message_history(self, messages: List[LLMMessage]):
        """设置消息历史"""
        self.message_history = self._convert_messages(messages)
    
    def chat(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        reuse_history: bool = True
    ) -> LLMResponse:
        """发送聊天请求（使用 OpenAI SDK）"""
        # 准备消息
        if reuse_history:
            formatted_messages = self.message_history.copy()
            formatted_messages.extend(self._convert_messages(messages))
        else:
            formatted_messages = self._convert_messages(messages)
        
        # 更新历史
        self.message_history = formatted_messages
        
        try:
            # 准备参数
            kwargs = {
                "model": self.model,
                "messages": formatted_messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }
            
            # 如果有工具，添加工具定义
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            
            # 调用 OpenAI API
            response = self.client.chat.completions.create(**kwargs)
            
            # 解析响应
            return self._parse_response(response)
            
        except Exception as e:
            logger.error(f"LLM 请求失败: {e}")
            raise RuntimeError(f"LLM 请求失败: {e}")
    
    def _convert_messages(self, messages: List[LLMMessage]) -> List[Dict[str, Any]]:
        """转换消息格式"""
        formatted = []
        
        for msg in messages:
            if msg.tool_call:
                # 工具调用消息
                formatted.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": msg.tool_call.call_id,
                        "type": "function",
                        "function": {
                            "name": msg.tool_call.name,
                            "arguments": str(msg.tool_call.arguments)
                        }
                    }]
                })
            elif msg.tool_result:
                # 工具结果消息
                formatted.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_result.call_id,
                    "name": msg.tool_result.name,
                    "content": msg.tool_result.result or msg.tool_result.error or ""
                })
            else:
                # 普通消息
                formatted.append({
                    "role": msg.role,
                    "content": msg.content
                })
        
        return formatted
    
    def _parse_response(self, response) -> LLMResponse:
        """解析 OpenAI SDK 响应"""
        choice = response.choices[0]
        message = choice.message
        
        # 解析内容
        content = message.content or ""
        
        # 解析 tool calls
        tool_calls = None
        if message.tool_calls:
            tool_calls = []
            for tc in message.tool_calls:
                tool_call = ToolCall(
                    name=tc.function.name,
                    call_id=tc.id,
                    arguments=eval(tc.function.arguments)  # 解析 JSON 字符串
                )
                tool_calls.append(tool_call)
                
                if not content:
                    content = f"[调用工具: {tool_call.name}]"
        
        # 解析 usage
        usage = None
        if response.usage:
            usage = LLMUsage(
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens
            )
        
        # 更新消息历史
        if tool_calls:
            self.message_history.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in message.tool_calls
                ]
            })
        else:
            self.message_history.append({
                "role": "assistant",
                "content": content
            })
        
        return LLMResponse(
            content=content,
            usage=usage,
            model=response.model,
            finish_reason=choice.finish_reason,
            tool_calls=tool_calls
        )
    
    def complete(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """简单的文本补全接口"""
        messages = []
        if system_prompt:
            messages.append(LLMMessage(role="system", content=system_prompt))
        messages.append(LLMMessage(role="user", content=prompt))
        
        response = self.chat(messages, tools=None, reuse_history=False)
        return response.content