# BaseTool API 文档

所有工具的基类，继承自 LangChain 的 BaseTool。

## 类定义

```python
from langchain.tools import BaseTool as LangChainBaseTool
from langchain.pydantic_v1 import BaseModel, Field
from typing import Type, Any, Dict, Optional
from abc import abstractmethod

class BaseTool(LangChainBaseTool):
    """
    工具基类
    
    所有 SemanticSQL Agent 的工具都继承自此类。
    提供统一的工具接口和错误处理机制。
    
    Attributes:
        name: 工具名称（必须唯一）
        description: 工具描述（用于 Agent 理解工具用途）
        args_schema: 参数验证模型（基于 Pydantic）
        return_direct: 是否直接返回结果给用户
    """
```

## 核心属性

```python
# 子类必须定义
name: str  # 工具唯一标识
description: str  # 工具功能描述

# 可选属性
args_schema: Type[BaseModel] = None  # 参数模型
return_direct: bool = False  # 是否直接返回
verbose: bool = False  # 详细日志
```

## 抽象方法

### _run

```python
@abstractmethod
def _run(self, **kwargs) -> Any:
    """
    执行工具的核心逻辑
    
    子类必须实现此方法。
    
    Args:
        **kwargs: 工具参数（由 args_schema 验证）
    
    Returns:
        Any: 工具执行结果
    
    Raises:
        ToolExecutionError: 工具执行失败
    """
    pass
```

### _arun (可选)

```python
async def _arun(self, **kwargs) -> Any:
    """
    异步执行工具
    
    默认抛出 NotImplementedError。
    如需异步支持，子类可重写此方法。
    """
    raise NotImplementedError("Async not supported")
```

## 标准方法

### run

```python
def run(self, tool_input: Union[str, Dict], **kwargs) -> Any:
    """
    执行工具（LangChain 调用此方法）
    
    自动处理：
    1. 参数解析和验证
    2. 错误处理和日志
    3. 结果格式化
    
    Args:
        tool_input: 工具输入（字符串或字典）
        **kwargs: 额外参数
    
    Returns:
        Any: 工具执行结果
    """
```

## 实现示例

```python
from typing import Type
from langchain.pydantic_v1 import BaseModel, Field

class MyToolInput(BaseModel):
    """工具输入参数"""
    query: str = Field(description="查询内容")
    limit: int = Field(default=10, description="结果数量")

class MyTool(BaseTool):
    """示例工具"""
    
    name = "my_tool"
    description = "执行某个特定任务"
    args_schema: Type[BaseModel] = MyToolInput
    
    def _run(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """执行核心逻辑"""
        # 实现工具逻辑
        result = process_query(query, limit)
        return {
            "success": True,
            "data": result,
            "count": len(result)
        }
```

## 最佳实践

### 1. 参数验证

```python
class ToolInput(BaseModel):
    """始终定义输入模型"""
    required_field: str = Field(description="必需参数")
    optional_field: int = Field(default=0, description="可选参数")
    
    class Config:
        # 提供示例
        schema_extra = {
            "example": {
                "required_field": "value",
                "optional_field": 10
            }
        }
```

### 2. 错误处理

```python
from semanticsql_agent.models.exceptions import ToolExecutionError

def _run(self, **kwargs):
    try:
        # 执行逻辑
        result = self.execute(**kwargs)
    except SpecificError as e:
        # 提供清晰的错误信息
        raise ToolExecutionError(
            tool_name=self.name,
            reason=str(e)
        )
    
    return result
```

### 3. 返回格式

```python
def _run(self, **kwargs):
    # 返回结构化数据
    return {
        "status": "success",
        "data": result_data,
        "metadata": {
            "timestamp": datetime.now(),
            "version": "1.0"
        }
    }
```

## 工具注册

```python
# 在 Agent 中注册工具
tools = [
    SchemaExtractionTool(),
    DomainAnalysisTool(),
    SQLGenerationTool(),
    # ... 其他工具
]

agent = create_react_agent(
    llm=llm,
    tools=tools,
    prompt=prompt
)
```

## 注意事项

1. **工具名称必须唯一**：在同一个 Agent 中不能有重名工具
2. **描述要清晰**：Agent 依赖描述理解工具用途
3. **参数模型必需**：使用 Pydantic 模型确保参数正确
4. **错误信息友好**：帮助 Agent 理解和处理错误
5. **返回格式一致**：便于 Agent 解析和使用结果

---

相关文档：
- [LangChain BaseTool](https://python.langchain.com/docs/modules/agents/tools/custom_tools)
- [工具开发指南](../LangChain集成指南.md#工具开发)