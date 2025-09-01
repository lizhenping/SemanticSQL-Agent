# LLMClient API 文档

LLM 客户端，封装 LangChain 的 ChatOpenAI 以支持 Qwen 模型。

## 类定义

```python
from langchain.chat_models import ChatOpenAI
from langchain.schema import BaseMessage
from typing import List, Dict, Any, Optional
from semanticsql_agent.utils.llm_client import LLMClient

class LLMClient:
    """
    LLM 客户端封装
    
    提供统一的接口调用 Qwen 模型（通过 OpenAI 兼容 API）。
    
    LangChain 集成：
    - 使用 ChatOpenAI 作为底层实现
    - 支持 LangChain 的回调机制
    - 兼容 LangChain 的消息格式
    - 可直接用于 LangChain Agent 和 Chain
    
    Attributes:
        llm: LangChain ChatOpenAI 实例
        config: LLM 配置
    """
```

## 构造函数

```python
def __init__(self, config: Settings):
    """
    初始化 LLM 客户端
    
    Args:
        config: 系统配置，包含 LLM 相关设置
    
    Example:
        ```python
        from semanticsql_agent.config import Settings
        
        config = Settings(
            llm_model="Qwen",
            llm_base_url="http://localhost:9991/v1",
            llm_temperature=0.7
        )
        
        llm_client = LLMClient(config)
        ```
    """
```

## 核心方法

### create_llm

```python
def create_llm(
    self,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None
) -> ChatOpenAI:
    """
    创建 LangChain ChatOpenAI 实例
    
    Args:
        temperature: 温度参数（可选，覆盖默认值）
        max_tokens: 最大 token 数（可选）
    
    Returns:
        ChatOpenAI: 配置好的 LLM 实例
    
    Example:
        ```python
        # 创建默认 LLM
        llm = client.create_llm()
        
        # 创建低温度 LLM（更确定的输出）
        llm_precise = client.create_llm(temperature=0.3)
        ```
    """
```

### invoke

```python
def invoke(
    self,
    messages: List[BaseMessage],
    **kwargs
) -> str:
    """
    调用 LLM 生成响应
    
    Args:
        messages: LangChain 消息列表
        **kwargs: 传递给 LLM 的额外参数
    
    Returns:
        str: 生成的响应文本
    
    Example:
        ```python
        from langchain.schema import HumanMessage, SystemMessage
        
        response = client.invoke([
            SystemMessage(content="You are a SQL expert."),
            HumanMessage(content="How to count orders?")
        ])
        ```
    """
```

### create_chain

```python
def create_chain(
    self,
    prompt_template: ChatPromptTemplate,
    output_parser: Optional[BaseOutputParser] = None
) -> LLMChain:
    """
    创建 LangChain Chain
    
    Args:
        prompt_template: 提示词模板
        output_parser: 输出解析器（可选）
    
    Returns:
        LLMChain: 配置好的 Chain
    
    Example:
        ```python
        from langchain.prompts import ChatPromptTemplate
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a SQL generator."),
            ("human", "{question}")
        ])
        
        chain = client.create_chain(prompt)
        result = chain.run(question="Count all orders")
        ```
    """
```

### with_tools

```python
def with_tools(
    self,
    tools: List[BaseTool]
) -> ChatOpenAI:
    """
    创建支持工具调用的 LLM
    
    Args:
        tools: 工具列表
    
    Returns:
        ChatOpenAI: 绑定了工具的 LLM 实例
    
    Example:
        ```python
        from semanticsql_agent.tools import SQLGenerationTool
        
        tools = [SQLGenerationTool()]
        llm_with_tools = client.with_tools(tools)
        ```
    """
```

## 配置选项

```python
class LLMConfig:
    """LLM 配置选项"""
    model: str = "Qwen"
    base_url: str = "http://localhost:9991/v1"
    api_key: str = "dummy"  # Qwen 本地部署不需要真实 key
    temperature: float = 0.7
    max_tokens: int = 2000
    timeout: int = 60
    max_retries: int = 3
```

## 提示词管理

```python
def format_system_prompt(self, template: str, **kwargs) -> str:
    """
    格式化系统提示词
    
    Args:
        template: 提示词模板
        **kwargs: 模板变量
    
    Returns:
        str: 格式化后的提示词
    """

def create_prompt_template(
    self,
    system_template: str,
    human_template: str
) -> ChatPromptTemplate:
    """
    创建提示词模板
    
    Args:
        system_template: 系统消息模板
        human_template: 用户消息模板
    
    Returns:
        ChatPromptTemplate: LangChain 提示词模板
    """
```

## 错误处理

```python
class LLMError(Exception):
    """LLM 调用错误基类"""
    pass

class LLMTimeoutError(LLMError):
    """LLM 调用超时"""
    pass

class LLMRateLimitError(LLMError):
    """LLM 调用频率限制"""
    pass
```

## 使用示例

### 基本使用
```python
# 创建客户端
client = LLMClient(config)

# 简单调用
response = client.invoke([
    HumanMessage(content="What is SQL?")
])

# 使用 Chain
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a SQL expert for {database} database."),
    ("human", "{question}")
])

chain = client.create_chain(prompt)
result = chain.run(
    database="MySQL",
    question="How to create an index?"
)
```

### 高级使用
```python
# 创建 Agent 使用的 LLM
from langchain.agents import create_react_agent

llm = client.create_llm(temperature=0.5)
agent = create_react_agent(
    llm=llm,
    tools=tools,
    prompt=agent_prompt
)

# 流式输出
llm_streaming = client.create_llm()
for chunk in llm_streaming.stream([
    HumanMessage(content="Explain database normalization")
]):
    print(chunk.content, end="")
```

## 性能优化

1. **缓存机制**：相同输入的结果缓存
2. **批量请求**：支持批量消息处理
3. **异步调用**：支持异步 API 调用
4. **重试策略**：自动重试失败请求

## 注意事项

1. 确保 Qwen 服务已启动
2. 使用 OpenAI 兼容的 API 格式
3. 本地部署时 API Key 可以是任意值
4. 支持 LangChain 的所有特性

---

相关文档：
- [Settings 配置](../../config模块/Settings-API.md)
- [BaseAgent API](../../agent模块/BaseAgent-API.md)