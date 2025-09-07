# Core模块极简接口设计

## 1. 基础数据模型 (core/schemas.py)

### 1.1 工具输出模型
```python
from pydantic import BaseModel, Field
from typing import List

class TripleOutput(BaseModel):
    """标准三元组输出结构"""
    subject: str = Field(description="主体")
    predicate: str = Field(description="关系") 
    object: str = Field(description="客体")

class ToolResult(BaseModel):
    """工具统一输出结构"""
    triples: List[TripleOutput] = Field(description="输出的三元组列表", default=[])
    summary: str = Field(description="操作总结")
    tool_name: str = Field(description="工具名称")

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return self.json(ensure_ascii=False)
```

## 2. 智能体状态接口 (core/state.py)

### 2.1 极简状态定义
```python
from typing_extensions import TypedDict
from typing import Any

class AgentState(TypedDict):
    """智能体状态 - 极简设计"""
    memory: Any                         # 记忆列表（具体结构由tools模块定义）
    current_input: str                  # 当前用户输入
```

## 3. 工作流接口 (core/workflow.py)

### 3.1 极简工作流创建
```python
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from typing import List, Callable

def create_react_workflow(agent_function: Callable, 
                         tools: List,
                         should_continue: Callable) -> Any:
    """创建ReAct工作流 - 极简版本"""
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("agent", agent_function)
    workflow.add_node("tools", ToolNode(tools))
    
    # 设置边
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges(
        "agent", 
        should_continue,
        {"tools": "tools", "__end__": "__end__"}
    )
    workflow.add_edge("tools", "agent")
    
    return workflow.compile()
```

---

## 4. 设计特点

**Core模块极简设计原则**：

### 4.1 职责单一
1. **基础数据结构**：只定义TripleOutput和ToolResult等基础输出模型
2. **状态管理**：极简的AgentState，memory类型为Any，由具体工具模块定义
3. **工作流支持**：提供基础的ReAct工作流创建函数

### 4.2 模块解耦
1. **避免依赖**：Core不依赖Tools模块的复杂数据结构
2. **接口稳定**：Core接口变化很少，保证整体架构稳定性
3. **职责明确**：记忆管理交给Tools，Core专注状态和工作流

### 4.3 扩展性好
1. **类型灵活**：AgentState.memory为Any类型，支持各种记忆结构
2. **工作流简洁**：create_react_workflow函数足够通用，支持各种工具组合
3. **向后兼容**：保留TripleOutput等基础类型，确保向后兼容性