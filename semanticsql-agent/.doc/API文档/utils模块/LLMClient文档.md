# LLMClient API 文档

## 概述
`LLMClient` 是统一的大语言模型客户端，支持 OpenAI API 兼容的模型。提供了聊天、补全、函数调用等功能的封装。

## 类定义
```python
class LLMClient:
    """统一的LLM客户端"""
```

## 构造函数
```python
def __init__(self, 
             model: str = "gpt-3.5-turbo",
             base_url: str = None,
             api_key: str = None,
             temperature: float = 0.7,
             max_tokens: int = 2000,
             timeout: int = 30,
             max_retries: int = 3)
```

**参数：**
- `model` (str): 模型名称
- `base_url` (str): API 基础 URL
- `api_key` (str): API 密钥
- `temperature` (float): 生成温度（0-2）
- `max_tokens` (int): 最大 token 数
- `timeout` (int): 请求超时时间（秒）
- `max_retries` (int): 最大重试次数

## 数据类

### LLMResponse
LLM 响应数据类。

```python
@dataclass
class LLMResponse:
    content: str              # 响应内容
    model: str               # 使用的模型
    usage: Dict[str, int]    # token 使用情况
    finish_reason: str       # 结束原因
    raw_response: Any = None # 原始响应
```

## 主要方法

### `chat(messages: List[Dict[str, str]], ...) -> LLMResponse`
发送聊天请求。

**参数：**
- `messages` (List[Dict[str, str]]): 消息列表
- `temperature` (float): 温度（可选，覆盖默认值）
- `max_tokens` (int): 最大 token 数（可选）
- `stream` (bool): 是否流式输出
- `**kwargs`: 其他参数

**消息格式：**
```python
messages = [
    {"role": "system", "content": "你是一个SQL专家"},
    {"role": "user", "content": "如何优化查询性能？"}
]
```

**返回：**
- `LLMResponse`: 包含响应内容和元数据

### `complete(prompt: str, ...) -> LLMResponse`
发送补全请求。

**参数：**
- `prompt` (str): 提示文本
- `temperature` (float): 温度（可选）
- `max_tokens` (int): 最大 token 数（可选）
- `stop` (List[str]): 停止标记（可选）

### `chat_with_functions(messages: List[Dict], functions: List[Dict], ...) -> LLMResponse`
带函数调用的聊天。

**参数：**
- `messages` (List[Dict]): 消息列表
- `functions` (List[Dict]): 函数定义列表
- `function_call` (Union[str, Dict]): 函数调用策略

**函数定义格式：**
```python
functions = [{
    "name": "get_weather",
    "description": "获取天气信息",
    "parameters": {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "城市名称"
            }
        },
        "required": ["location"]
    }
}]
```

### `parse_function_call(response: LLMResponse) -> Optional[Dict[str, Any]]`
解析函数调用。

**返回：**
```python
{
    "name": "function_name",
    "arguments": {"arg1": "value1", ...}
}
```

### `format_messages(system_prompt: str, user_prompt: str, ...) -> List[Dict[str, str]]`
格式化消息列表。

**参数：**
- `system_prompt` (str): 系统提示（可选）
- `user_prompt` (str): 用户提示
- `assistant_prompt` (str): 助手提示（可选）
- `history` (List[Dict]): 历史消息（可选）

### `count_tokens(text: str) -> int`
估算文本的 token 数。

**注意：** 这是一个近似估算，实际 token 数可能有差异。

### `get_model_info() -> Dict[str, Any]`
获取模型信息。

**返回：**
```python
{
    "model": "gpt-3.5-turbo",
    "context_window": 4096,
    "max_output_tokens": 4096,
    "supports_functions": True,
    "supports_vision": False
}
```

## 内部方法

### `_make_request(request_func, *args, **kwargs) -> Any`
发送请求的内部方法，包含重试逻辑。

**重试策略：**
- 指数退避：2^n 秒（n 为重试次数）
- 最大重试次数：由 `max_retries` 参数控制

## 使用示例

### 基本聊天
```python
# 创建客户端
client = LLMClient(
    model="gpt-3.5-turbo",
    temperature=0.7,
    max_tokens=2000
)

# 发送聊天请求
response = client.chat([
    {"role": "system", "content": "你是一个数据分析专家"},
    {"role": "user", "content": "解释什么是数据归一化"}
])

print(f"回复: {response.content}")
print(f"使用的tokens: {response.usage}")
```

### 文本补全
```python
# 生成SQL查询
prompt = """
表结构：users (id, name, email, created_at)
需求：查询最近7天注册的用户
SQL：
"""

response = client.complete(
    prompt=prompt,
    temperature=0.1,  # 低温度，更确定性
    stop=[";"]        # 遇到分号停止
)

print(f"生成的SQL: {response.content}")
```

### 函数调用
```python
# 定义函数
functions = [{
    "name": "execute_sql",
    "description": "执行SQL查询",
    "parameters": {
        "type": "object",
        "properties": {
            "sql": {
                "type": "string",
                "description": "要执行的SQL语句"
            },
            "database": {
                "type": "string",
                "description": "目标数据库"
            }
        },
        "required": ["sql"]
    }
}]

# 发送请求
response = client.chat_with_functions(
    messages=[
        {"role": "user", "content": "查询所有活跃用户"}
    ],
    functions=functions,
    function_call="auto"
)

# 解析函数调用
if function_call := client.parse_function_call(response):
    print(f"调用函数: {function_call['name']}")
    print(f"参数: {function_call['arguments']}")
```

### 流式输出
```python
# 流式聊天
for chunk in client.chat(
    messages=[{"role": "user", "content": "介绍数据库索引"}],
    stream=True
):
    print(chunk.content, end="", flush=True)
```

### 对话历史管理
```python
# 使用历史消息
history = [
    {"role": "user", "content": "什么是主键？"},
    {"role": "assistant", "content": "主键是..."},
]

messages = client.format_messages(
    system_prompt="你是数据库专家",
    user_prompt="外键和主键有什么区别？",
    history=history
)

response = client.chat(messages)
```

## 错误处理

### 常见异常
- `OpenAIError`: API 调用错误
- `Timeout`: 请求超时
- `RateLimitError`: 速率限制
- `AuthenticationError`: 认证失败

### 错误处理示例
```python
try:
    response = client.chat(messages)
except Exception as e:
    logger.error(f"LLM调用失败: {e}")
    # 使用备用模型或降级处理
    response = client.chat(
        messages,
        model="gpt-3.5-turbo",  # 降级到更小的模型
        temperature=0.5         # 降低温度
    )
```

## 性能优化

### 1. Token 管理
```python
# 检查 token 数量
text = "很长的文本..."
token_count = client.count_tokens(text)

if token_count > 3000:
    # 截断或总结文本
    text = text[:3000]  # 简单截断
```

### 2. 缓存响应
```python
from functools import lru_cache

@lru_cache(maxsize=100)
def cached_chat(prompt: str) -> str:
    response = client.chat([
        {"role": "user", "content": prompt}
    ])
    return response.content
```

### 3. 批量处理
```python
# 批量处理多个请求
prompts = ["问题1", "问题2", "问题3"]
responses = []

for prompt in prompts:
    try:
        response = client.chat([
            {"role": "user", "content": prompt}
        ])
        responses.append(response)
    except Exception as e:
        logger.error(f"处理失败: {prompt}")
        responses.append(None)
```

## 配置建议

### 不同场景的参数设置

1. **SQL 生成**
   ```python
   client = LLMClient(
       temperature=0.1,    # 低温度，确定性输出
       max_tokens=500      # SQL 通常不太长
   )
   ```

2. **自然语言生成**
   ```python
   client = LLMClient(
       temperature=0.7,    # 中等温度，平衡创造性
       max_tokens=2000     # 允许较长输出
   )
   ```

3. **代码生成**
   ```python
   client = LLMClient(
       temperature=0.2,    # 较低温度
       max_tokens=1000     # 适中长度
   )
   ```

## 注意事项

1. API 密钥安全存储
2. 注意 token 使用限制
3. 合理设置超时时间
4. 监控 API 使用量
5. 处理速率限制
6. 考虑响应缓存