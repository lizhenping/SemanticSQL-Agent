"""LLM 客户端 - 支持工具调用回退机制"""

import logging
import re
import json
from typing import List, Optional, Dict, Any
from openai import OpenAI

from .llm_basics import LLMMessage, LLMResponse, LLMUsage, ToolCall, ToolResult

logger = logging.getLogger(__name__)


class LLMClient:
    """使用 OpenAI SDK 调用本地 Qwen 模型，支持工具调用回退"""
    
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
        self.use_function_calling = True  # 优先尝试function calling
        
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
        """发送聊天请求，支持工具调用回退"""
        # 如果有工具且启用function calling，先尝试function calling
        if tools and self.use_function_calling:
            try:
                return self._chat_with_function_calling(messages, tools, reuse_history)
            except Exception as e:
                logger.warning(f"Function calling 失败，回退到文本解析模式: {e}")
                self.use_function_calling = False
        
        # 使用文本解析模式
        if tools:
            return self._chat_with_text_parsing(messages, tools, reuse_history)
        else:
            return self._chat_simple(messages, reuse_history)
    
    def _chat_with_function_calling(
        self,
        messages: List[LLMMessage],
        tools: List[Dict[str, Any]],
        reuse_history: bool
    ) -> LLMResponse:
        """使用标准 function calling 方式"""
        # 准备消息
        formatted_messages = self._prepare_messages(messages, reuse_history)
        
        # 调用 OpenAI API with tools
        kwargs = {
            "model": self.model,
            "messages": formatted_messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "tools": tools
        }
        
        response = self.client.chat.completions.create(**kwargs)
        return self._parse_response(response)
    
    def _chat_with_text_parsing(
        self,
        messages: List[LLMMessage],
        tools: List[Dict[str, Any]],
        reuse_history: bool
    ) -> LLMResponse:
        """使用文本解析方式进行工具调用"""
        # 准备消息，添加工具调用指引
        formatted_messages = self._prepare_messages(messages, reuse_history)
        
        # 为第一个system消息添加工具调用指引
        system_message = self._build_tool_instruction_message(tools)
        if formatted_messages and formatted_messages[0]['role'] == 'system':
            formatted_messages[0]['content'] += "\n\n" + system_message
        else:
            formatted_messages.insert(0, {"role": "system", "content": system_message})
        
        # 调用 OpenAI API (不带tools)
        kwargs = {
            "model": self.model,
            "messages": formatted_messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        
        response = self.client.chat.completions.create(**kwargs)
        
        # 解析响应，提取工具调用
        return self._parse_text_response_for_tools(response, tools)
    
    def _chat_simple(self, messages: List[LLMMessage], reuse_history: bool) -> LLMResponse:
        """简单聊天，不使用工具"""
        formatted_messages = self._prepare_messages(messages, reuse_history)
        
        kwargs = {
            "model": self.model,
            "messages": formatted_messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        
        response = self.client.chat.completions.create(**kwargs)
        return self._parse_response(response)
    
    def _prepare_messages(self, messages: List[LLMMessage], reuse_history: bool) -> List[Dict[str, Any]]:
        """准备消息"""
        if reuse_history:
            formatted_messages = self.message_history.copy()
            formatted_messages.extend(self._convert_messages(messages))
        else:
            formatted_messages = self._convert_messages(messages)
        
        # 更新历史
        self.message_history = formatted_messages
        return formatted_messages
    
    def _build_tool_instruction_message(self, tools: List[Dict[str, Any]]) -> str:
        """构建工具调用指引消息"""
        tool_descriptions = []
        for tool in tools:
            if 'function' in tool:
                func_info = tool['function']
                name = func_info['name']
                desc = func_info['description']
                params = func_info.get('parameters', {}).get('properties', {})
                
                param_desc = []
                for param_name, param_info in params.items():
                    param_desc.append(f"  - {param_name} ({param_info.get('type', 'string')}): {param_info.get('description', '')}")
                
                tool_desc = f"""
**{name}**: {desc}
参数:
{chr(10).join(param_desc) if param_desc else "  无参数"}"""
                tool_descriptions.append(tool_desc)
        
        instruction = f"""# 工具调用指引

你有以下工具可用：
{chr(10).join(tool_descriptions)}

当你需要调用工具时，请使用以下格式：

```tool_call
工具名称: tool_name
参数:
- param1: value1
- param2: value2
```

例如：
```tool_call
工具名称: schema_extraction
参数:
- database_type: mysql
```

请根据用户的需求，智能选择合适的工具进行调用。每次只调用一个工具。"""
        
        return instruction
    
    def _parse_text_response_for_tools(self, response, tools: List[Dict[str, Any]]) -> LLMResponse:
        """解析文本响应中的工具调用"""
        content = response.choices[0].message.content or ""
        
        # 查找工具调用模式
        tool_call_pattern = r'```tool_call\s*\n工具名称:\s*(\w+)\s*\n参数:\s*\n(.*?)\n```'
        matches = re.findall(tool_call_pattern, content, re.DOTALL)
        
        tool_calls = []
        if matches:
            for match in matches:
                tool_name = match[0].strip()
                params_text = match[1].strip()
                
                # 解析参数
                params = {}
                for line in params_text.split('\n'):
                    if ':' in line and line.strip().startswith('-'):
                        key_value = line.strip()[1:].strip()  # 移除 '-'
                        if ':' in key_value:
                            key, value = key_value.split(':', 1)
                            params[key.strip()] = value.strip()
                
                # 创建工具调用
                tool_call = ToolCall(
                    name=tool_name,
                    call_id=f"call_{len(tool_calls)}",
                    arguments=params
                )
                tool_calls.append(tool_call)
        
        # 解析 usage
        usage = None
        if response.usage:
            usage = LLMUsage(
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens
            )
        
        # 更新消息历史
        self.message_history.append({
            "role": "assistant",
            "content": content
        })
        
        return LLMResponse(
            content=content,
            usage=usage,
            model=response.model,
            finish_reason=response.choices[0].finish_reason,
            tool_calls=tool_calls
        )
    
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
        if hasattr(message, 'tool_calls') and message.tool_calls:
            tool_calls = []
            for tc in message.tool_calls:
                try:
                    arguments = eval(tc.function.arguments) if tc.function.arguments else {}
                except:
                    arguments = {}
                    
                tool_call = ToolCall(
                    name=tc.function.name,
                    call_id=tc.id,
                    arguments=arguments
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