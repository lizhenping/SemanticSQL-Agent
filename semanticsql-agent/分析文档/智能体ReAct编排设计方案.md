# SemanticSQL Agent - 极简 ReAct 设计方案

## 1. 核心理念

**设计目标**：基于 LangGraph 的极简 ReAct 模式，构建简单高效的 SQL 生成智能体

### 1.1 设计原则
- **极简优先**：只保留核心功能，避免过度工程化
- **ReAct 循环**：标准的思考-行动-观察循环
- **三元组记忆**：简单的三元组存储，支持基本查询
- **动态工具调用**：LLM 自主选择和调用十几个工具
- **状态机架构**：基于 LangGraph 的清晰状态流转

## 2. 极简架构设计

### 2.1 现代化状态和存储
```python
from typing import List, Any
from typing_extensions import Annotated, TypedDict
from langchain_core.messages import BaseMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, add_messages
from langgraph.prebuilt import InjectedState, InjectedStore, ToolNode
from langgraph.store.memory import InMemoryStore

class AgentState(TypedDict):
    """极简状态定义 - 只需要消息"""
    messages: Annotated[List[BaseMessage], add_messages]

# 三元组记忆通过 InjectedStore 管理，无需在状态中维护
```

### 2.2 现代化工具定义
```python
@tool
def schema_extraction(
    database_url: str,
    state: Annotated[dict, InjectedState],
    store: Annotated[Any, InjectedStore()]
) -> str:
    """提取数据库结构并存储为三元组"""
    # 执行 schema 提取逻辑
    result = extract_database_schema(database_url)
    
    # 存储三元组到持久化存储
    for table_name, table_info in result.items():
        store.put(("triples",), f"table_{table_name}", 
                 {"subject": "database", "predicate": "has_table", "object": table_name})
        
        for column in table_info.get("columns", []):
            store.put(("triples",), f"column_{table_name}_{column}", 
                     {"subject": table_name, "predicate": "has_column", "object": column})
    
    return f"✅ 提取了 {len(result)} 个表的结构信息"

@tool  
def sql_generation(
    question: str,
    store: Annotated[Any, InjectedStore()]
) -> str:
    """基于三元组记忆生成SQL"""
    # 从存储中获取相关三元组
    schema_triples = list(store.search(("triples",)))
    
    # 生成SQL逻辑
    sql = generate_sql_from_triples(question, schema_triples)
    
    # 存储结果
    store.put(("triples",), f"sql_{hash(question)}", 
             {"subject": question, "predicate": "generates_sql", "object": sql})
    
    return f"✅ 生成SQL: {sql}"

@tool
def sequential_thinking(
    problem: str,
    state: Annotated[dict, InjectedState],
    store: Annotated[Any, InjectedStore()]
) -> str:
    """深度思考工具，可以访问完整状态和记忆"""
    messages = state["messages"]
    memory_context = list(store.search(("triples",)))
    
    # 深度思考逻辑
    analysis = deep_think(problem, messages, memory_context)
    
    # 存储思考结果
    store.put(("triples",), f"thinking_{hash(problem)}", 
             {"subject": problem, "predicate": "analyzed_as", "object": analysis})
    
    return f"🤔 思考完成: {analysis}"

def should_continue(state: AgentState):
    """您的完美决策路由函数"""
    messages = state["messages"]
    last_message = messages[-1]
    
    # 检查是否有工具调用
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tools"
    
    return "__end__"
```

### 2.3 工作流构建
```python
def create_simple_react_agent():
    """创建极简 ReAct 智能体"""
    workflow = StateGraph(AgentState)
    
    # 添加两个核心节点
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", call_tools)
    
    # 设置入口点
    workflow.set_entry_point("agent")
    
    # 使用您的简化决策函数
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", "__end__": "__end__"}
    )
    
    # 工具执行后返回智能体
    workflow.add_edge("tools", "agent")
    
    return workflow.compile()
```

## 3. 工具集成

### 3.1 工具接口
现有的工具可以直接集成，只需要确保：
- 工具继承 LangChain 的 BaseTool
- 执行结果可以转换为简单的三元组
- 支持基本的错误处理

```python
# 工具执行后的结果转换
def convert_to_triples(tool_name: str, result: Any) -> List[Triple]:
    """将工具结果转换为三元组"""
    triples = []
    
    if isinstance(result, dict):
        for key, value in result.items():
            triples.append(Triple(tool_name, key, str(value)))
    else:
        triples.append(Triple(tool_name, "output", str(result)))
    
    return triples
```

## 4. 使用方式

### 4.1 基本使用
```python
# 1. 创建智能体
agent = SimpleReActAgent(llm, tools)

# 2. 执行任务
result = agent.run("分析数据库并生成查询SQL")

# 3. 查看结果
print(f"成功: {result['success']}")
print(f"三元组数量: {result['total_triples']}")
print(f"记忆摘要: {result['memory_summary']}")
```

### 4.2 典型执行流程
```
用户输入: "分析数据库并生成用户查询SQL"
    ↓
LLM 思考: 需要先了解数据库结构
    ↓
选择工具: schema_extraction  
    ↓
执行工具: 提取到表结构，存入三元组记忆
    ↓
LLM 思考: 基于结构信息，需要理解业务域
    ↓  
选择工具: domain_analysis
    ↓
执行工具: 识别业务域，存入三元组记忆
    ↓
LLM 思考: 现在可以生成SQL了
    ↓
选择工具: sql_generation
    ↓
执行工具: 生成SQL，任务完成
```

## 5. 实施计划

### 5.1 极简实施步骤
```
Phase 1: 核心架构 (3天)
├── 实现 SimpleMemory 和 AgentState
├── 实现 call_model 和 call_tools 节点
├── 集成您的 should_continue 函数
└── 创建基本的 LangGraph 工作流

Phase 2: 工具集成 (2天)  
├── 适配现有十几个工具
├── 实现结果到三元组的转换
├── 测试工具调用和记忆存储
└── 验证完整的 ReAct 循环

Phase 3: 测试优化 (1天)
├── 端到端功能测试
├── 修复发现的问题
└── 性能优化
```

### 5.2 核心优势

**简单性**：
- 只有 2 个核心节点 vs 原方案的多个复杂节点
- 基础三元组存储 vs 复杂的记忆管理系统
- 您的简单决策函数 vs 复杂的路由逻辑

**可维护性**：
- 清晰的代码结构，易于理解和修改
- 最小化的抽象，减少维护负担
- 标准的 LangChain 工具接口，便于集成

**扩展性**：
- 新工具只需实现基本接口
- LangGraph 提供灵活的状态机扩展
- 三元组记忆支持简单的知识积累

这个极简设计完全符合您的需求：**简单的 ReAct 循环 + 三元组记忆 + 动态工具调用**，避免了原方案的过度工程化问题。
