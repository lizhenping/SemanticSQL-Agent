# 使用 OpenAI SDK 调用本地 Qwen

## 🎯 设计决策

既然使用的是 vLLM 部署的 Qwen（OpenAI 兼容接口），我们直接使用 OpenAI 官方 SDK，这样：

1. **代码更简洁** - 不需要自己处理 HTTP 请求
2. **功能更完整** - 自动处理重试、流式响应等
3. **维护更容易** - 跟随 OpenAI 的更新

## 📦 安装

```bash
pip install openai
```

## 🔧 基本使用

### 1. 创建客户端
```python
from openai import OpenAI

client = OpenAI(
    api_key="not-needed",  # vLLM 不需要真实的 key
    base_url="http://192.168.200.216:9009/v1"
)
```

### 2. 普通对话
```python
response = client.chat.completions.create(
    model="Qwen3-14B",
    messages=[
        {"role": "user", "content": "你好"}
    ]
)
print(response.choices[0].message.content)
```

### 3. Tool Calling
```python
# 定义工具
tools = [{
    "type": "function",
    "function": {
        "name": "execute_sql",
        "description": "执行 SQL 查询",
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "要执行的 SQL"
                }
            },
            "required": ["sql"]
        }
    }
}]

# 发送请求
response = client.chat.completions.create(
    model="Qwen3-14B",
    messages=[{"role": "user", "content": "查询用户总数"}],
    tools=tools,
    tool_choice="auto"
)

# 检查工具调用
if response.choices[0].message.tool_calls:
    tool_call = response.choices[0].message.tool_calls[0]
    print(f"调用: {tool_call.function.name}")
    print(f"参数: {tool_call.function.arguments}")
```

## 🏗️ 在 SemanticSQL-Agent 中的封装

虽然直接使用 OpenAI SDK，但我们仍然封装了一层，以便：

1. **统一接口** - 与项目其他部分保持一致
2. **消息管理** - 自动维护对话历史
3. **类型转换** - 在内部类型和 OpenAI 类型之间转换

```python
class LLMClient:
    def __init__(self, model="Qwen3-14B", base_url="..."):
        self.client = OpenAI(api_key="not-needed", base_url=base_url)
        self.model = model
    
    def chat(self, messages, tools=None):
        # 1. 转换消息格式
        # 2. 调用 OpenAI SDK
        # 3. 解析响应
        # 4. 维护历史
```

## 💡 优势

1. **标准化** - 使用业界标准的 API 格式
2. **兼容性** - 可以轻松切换到真正的 OpenAI API
3. **功能完整** - 支持所有 OpenAI 的特性（tool calling、streaming 等）
4. **简单直接** - 不需要处理底层 HTTP 细节

## 📝 注意事项

1. **模型名称** - 确保 vLLM 配置的模型名称与代码中一致
2. **API 版本** - OpenAI SDK 会自动处理 API 版本
3. **错误处理** - SDK 会抛出明确的异常类型
4. **参数解析** - `tool_calls` 中的 `arguments` 是字符串，需要解析

## 🚀 完整示例

```python
from openai import OpenAI
import json

# 初始化
client = OpenAI(
    api_key="not-needed",
    base_url="http://192.168.200.216:9009/v1"
)

# 工具定义
tools = [{
    "type": "function", 
    "function": {
        "name": "analyze_database",
        "description": "分析数据库结构",
        "parameters": {
            "type": "object",
            "properties": {
                "table_name": {"type": "string"}
            }
        }
    }
}]

# 对话流程
messages = [
    {"role": "system", "content": "你是 SQL 专家"},
    {"role": "user", "content": "users 表有哪些字段？"}
]

# 第一轮：LLM 决定调用工具
response = client.chat.completions.create(
    model="Qwen3-14B",
    messages=messages,
    tools=tools
)

if response.choices[0].message.tool_calls:
    # 执行工具
    tool_call = response.choices[0].message.tool_calls[0]
    args = json.loads(tool_call.function.arguments)
    
    # 模拟工具执行
    result = {"columns": ["id", "name", "email", "created_at"]}
    
    # 添加消息
    messages.append(response.choices[0].message)
    messages.append({
        "role": "tool",
        "tool_call_id": tool_call.id,
        "content": json.dumps(result)
    })
    
    # 第二轮：获取最终答案
    final_response = client.chat.completions.create(
        model="Qwen3-14B",
        messages=messages
    )
    
    print(final_response.choices[0].message.content)
```

这就是我们使用 OpenAI SDK 的方式！