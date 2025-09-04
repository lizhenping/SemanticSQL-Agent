# LLM 使用规范

## 统一使用 LangChain

本项目统一使用 LangChain 的 LLM 接口，不直接使用 OpenAI SDK。

### 标准用法

```python
from langchain_openai import ChatOpenAI

# 在 Agent 或工具中初始化
llm = ChatOpenAI(
    model=settings.llm_model,
    base_url=settings.llm_base_url,
    api_key=settings.llm_api_key,
    temperature=settings.llm_temperature,
    max_tokens=settings.llm_max_tokens,
    timeout=settings.llm_timeout
)
```

### 为什么使用 LangChain？

1. **统一接口** - 可以轻松切换不同的 LLM 提供商
2. **丰富功能** - 内置重试、回调、流式输出等功能
3. **生态系统** - 与 Agent、Chain、Memory 等组件无缝集成
4. **标准化** - 遵循 LangChain 生态的最佳实践

### 配置说明

在 `config/settings.py` 中配置 LLM 参数：

```python
class LLMConfig(BaseModel):
    """LLM配置"""
    model: str = "qwen2.5-coder:32b"
    base_url: str = "http://127.0.0.1:9991/v1"
    api_key: str = "sk-not-needed"
    temperature: float = 0.1
    max_tokens: int = 4096
    timeout: int = 300
```

### 在工具中使用

所有需要 LLM 的工具都应该在初始化时接收 LLM 实例：

```python
class MyTool(BaseTool):
    llm: Optional[ChatOpenAI] = Field(default=None, exclude=True)
    
    def __init__(self, llm: ChatOpenAI):
        super().__init__()
        self.llm = llm
```

### 注意事项

1. **不要直接导入 openai** - 使用 `langchain_openai`
2. **不要创建全局 LLM 实例** - 通过依赖注入传递
3. **使用 LangChain 的特性** - 如输出解析器、回调等

### 已删除的文件

- `utils/llm_client.py` - 独立的 OpenAI 客户端实现（未使用）

这个文件与项目的 LangChain 架构不一致，已被删除以避免混淆。