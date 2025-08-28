# Tool Calling 深度解析：不仅仅是返回格式

## 🤔 Tool Calling 到底是什么？

Tool Calling 是一个**协议**，包含：

### 1. LLM 侧的能力
- **理解工具定义**：LLM 需要理解每个工具的功能和参数
- **决策何时调用**：LLM 自主判断是否需要使用工具
- **生成正确参数**：LLM 构造符合工具要求的参数

### 2. 客户端侧的实现
- **工具注册**：告诉 LLM 有哪些工具可用
- **消息协议**：正确处理工具调用和结果消息
- **执行管理**：实际执行工具并返回结果

## 📋 具体工作流程

### Step 1: 告诉 LLM 有哪些工具

```python
# 发送给 LLM 的请求
{
    "model": "Qwen3-14B",
    "messages": [...],
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "获取指定城市的天气",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "城市名称"
                        }
                    },
                    "required": ["city"]
                }
            }
        }
    ],
    "tool_choice": "auto"  # 让 LLM 自己决定
}
```

### Step 2: LLM 的决策过程

LLM 内部会进行推理：
```
用户问："北京天气怎么样？"

LLM 思考：
1. 用户想知道北京的天气
2. 我有 get_weather 工具可以获取天气
3. 需要传入 city 参数
4. 决定：调用 get_weather(city="北京")
```

### Step 3: LLM 返回特定格式

```json
{
    "choices": [{
        "message": {
            "role": "assistant",
            "content": "我来帮您查询北京的天气。",  // 可选的思考过程
            "tool_calls": [{
                "id": "call_abc123",
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "arguments": "{\"city\": \"北京\"}"
                }
            }]
        }
    }]
}
```

### Step 4: 客户端执行工具

```python
# 客户端解析 tool_calls
for tool_call in response.tool_calls:
    if tool_call.name == "get_weather":
        # 执行实际的工具
        result = weather_api.get(city="北京")
        # 返回：{"temperature": 25, "condition": "晴"}
```

### Step 5: 将结果发回给 LLM

```json
{
    "role": "tool",
    "tool_call_id": "call_abc123",
    "name": "get_weather",
    "content": "{\"temperature\": 25, \"condition\": \"晴\"}"
}
```

### Step 6: LLM 生成最终回答

```json
{
    "role": "assistant",
    "content": "北京今天的天气是晴天，温度为 25°C，很适合外出。"
}
```

## 🎯 关键点

### 1. **这不是简单的文本替换**

❌ 错误理解：
```python
# 这不是 Tool Calling
if "天气" in user_input:
    return "调用天气API..."
```

✅ 正确的 Tool Calling：
- LLM 理解语义，而不是关键词匹配
- LLM 可以处理复杂推理：
  - "明天去北京需要带伞吗？" → 需要查天气
  - "比较北京和上海的气温" → 需要调用两次

### 2. **LLM 需要特殊训练**

不是所有 LLM 都支持 Tool Calling：
- ✅ GPT-4, GPT-3.5-turbo (with functions)
- ✅ Claude (with tools)
- ✅ Qwen-Plus, Qwen-Max
- ❌ 一些基础模型可能不支持

### 3. **协议的标准化**

OpenAI 建立的标准被广泛采用：
- 工具定义格式（JSON Schema）
- 消息角色（assistant, tool）
- 调用 ID 关联机制

## 🔍 在 SemanticSQL-Agent 中的实现

### 1. 工具定义
```python
class Tool:
    def get_schema(self):
        # 生成 OpenAI 格式的工具定义
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {...},
                "required": [...]
            }
        }
```

### 2. LLM 客户端
```python
class LLMClient:
    def chat(self, messages, tools=None):
        # 1. 发送工具定义给 LLM
        # 2. 解析返回的 tool_calls
        # 3. 维护消息历史
```

### 3. Agent 执行循环
```python
class BaseAgent:
    def _run_react_step(self):
        # 1. 发送消息（带工具定义）
        response = llm.chat(messages, tools=self.tools)
        
        # 2. 如果有 tool_calls，执行它们
        if response.tool_calls:
            for tool_call in response.tool_calls:
                result = self.execute_tool(tool_call)
                # 3. 将结果作为 tool 消息发回
                messages.append(tool_message)
```

## 💡 总结

Tool Calling 是：
1. **一种协议** - LLM 和应用程序之间的约定
2. **一种能力** - LLM 需要理解何时、如何调用工具
3. **一种模式** - 让 LLM 能够访问外部功能

不仅仅是：
- ❌ 简单的返回格式
- ❌ 关键词匹配
- ❌ 硬编码的规则

这就是为什么需要：
- 支持 Tool Calling 的 LLM（如 Qwen）
- 正确的消息协议实现
- 完整的执行管理机制