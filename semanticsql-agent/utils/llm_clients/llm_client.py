"""LLM 客户端 - 支持本地 Qwen 和 tool calling"""

import json
import logging
import uuid
from typing import List, Optional, Dict, Any
import requests

from .llm_basics import LLMMessage, LLMResponse, LLMUsage, ToolCall, ToolResult

logger = logging.getLogger(__name__)


class LLMClient:
    """本地 Qwen 模型客户端（支持 tool calling）"""
    
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
        """发送聊天请求（支持 tool calling）"""
        # 转换消息格式
        if reuse_history:
            # 使用历史消息
            formatted_messages = self.message_history.copy()
            # 添加新消息
            formatted_messages.extend(self._convert_messages(messages))
        else:
            formatted_messages = self._convert_messages(messages)
        
        # 更新历史
        self.message_history = formatted_messages
        
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
        
        # 如果提供了工具，添加到请求中
        if tools:
            data["tools"] = self._format_tools(tools)
            data["tool_choice"] = "auto"  # 让模型自动决定是否调用工具
        
        url = f"{self.base_url}/chat/completions"
        
        try:
            logger.debug(f"发送请求到: {url}")
            logger.debug(f"消息数: {len(formatted_messages)}")
            if tools:
                logger.debug(f"工具数: {len(tools)}")
            
            response = requests.post(url, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            return self._parse_response(result)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"LLM 请求失败: {e}")
            raise RuntimeError(f"LLM 请求失败: {e}")
        except Exception as e:
            logger.error(f"处理响应失败: {e}")
            raise RuntimeError(f"处理响应失败: {e}")
    
    def _convert_messages(self, messages: List[LLMMessage]) -> List[Dict[str, Any]]:
        """转换消息格式为 OpenAI 格式"""
        formatted = []
        
        for msg in messages:
            if msg.tool_call:
                # 工具调用消息（assistant 发起的）
                formatted.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": msg.tool_call.call_id,
                        "type": "function",
                        "function": {
                            "name": msg.tool_call.name,
                            "arguments": json.dumps(msg.tool_call.arguments)
                        }
                    }]
                })
            elif msg.tool_result:
                # 工具结果消息
                formatted.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_result.call_id,
                    "name": msg.tool_result.name,
                    "content": msg.tool_result.result or msg.tool_result.error or "No result"
                })
            else:
                # 普通消息
                formatted.append({
                    "role": msg.role,
                    "content": msg.content
                })
        
        return formatted
    
    def _format_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """格式化工具定义为 OpenAI 格式"""
        formatted_tools = []
        
        for tool in tools:
            formatted_tool = {
                "type": "function",
                "function": {
                    "name": tool.get("name"),
                    "description": tool.get("description"),
                    "parameters": tool.get("parameters", {
                        "type": "object",
                        "properties": {},
                        "required": []
                    })
                }
            }
            formatted_tools.append(formatted_tool)
        
        return formatted_tools
    
    def _parse_response(self, result: Dict[str, Any]) -> LLMResponse:
        """解析 API 响应"""
        choice = result["choices"][0]
        message = choice["message"]
        
        # 解析内容
        content = message.get("content", "")
        
        # 解析 tool calls
        tool_calls = None
        if "tool_calls" in message and message["tool_calls"]:
            tool_calls = []
            for tc in message["tool_calls"]:
                # 解析参数
                try:
                    arguments = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    arguments = {}
                
                tool_call = ToolCall(
                    name=tc["function"]["name"],
                    call_id=tc.get("id", str(uuid.uuid4())),
                    arguments=arguments
                )
                tool_calls.append(tool_call)
                
                # 如果有工具调用，content 可能为空
                if not content:
                    content = f"[调用工具: {tool_call.name}]"
        
        # 解析 token 使用
        usage = None
        if "usage" in result:
            usage = LLMUsage(
                input_tokens=result["usage"].get("prompt_tokens", 0),
                output_tokens=result["usage"].get("completion_tokens", 0),
                total_tokens=result["usage"].get("total_tokens", 0)
            )
        
        # 更新消息历史（添加 assistant 的回复）
        if tool_calls:
            # 有工具调用
            self.message_history.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tc.call_id,
                        "type": "function", 
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)
                        }
                    }
                    for tc in tool_calls
                ]
            })
        else:
            # 普通回复
            self.message_history.append({
                "role": "assistant",
                "content": content
            })
        
        return LLMResponse(
            content=content,
            usage=usage,
            model=result.get("model", self.model),
            finish_reason=choice.get("finish_reason"),
            tool_calls=tool_calls
        )
    
    def complete(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """简单的文本补全接口（不支持 tool calling）"""
        messages = []
        if system_prompt:
            messages.append(LLMMessage(role="system", content=system_prompt))
        messages.append(LLMMessage(role="user", content=prompt))
        
        response = self.chat(messages, tools=None, reuse_history=False)
        return response.content