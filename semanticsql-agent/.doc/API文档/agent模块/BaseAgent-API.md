# BaseAgent API 文档

基于 LangChain 的智能体基类，提供 ReAct 模式的执行框架。

## 类定义

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from langchain.agents import AgentExecutor
from langchain.memory import BaseMemory
from langchain.callbacks import BaseCallbackHandler

class BaseAgent(ABC):
    """
    智能体基类，封装 LangChain AgentExecutor
    
    Attributes:
        llm: LangChain LLM 实例
        tools: 工具列表
        memory: 记忆管理器
        agent_executor: LangChain AgentExecutor
        callbacks: 回调处理器列表
    """
```

## 构造函数

```python
def __init__(
    self,
    config: Settings,
    db_config: DatabaseConfig,
    callbacks: Optional[List[BaseCallbackHandler]] = None
):
    """
    初始化智能体
    
    Args:
        config: 系统配置对象
        db_config: 数据库配置对象
        callbacks: LangChain 回调处理器列表
    
    Example:
        ```python
        agent = MyAgent(
            config=Settings(),
            db_config=DatabaseConfig(host="localhost", database="mydb"),
            callbacks=[StdOutCallbackHandler()]
        )
        ```
    """
```

## 抽象方法

### get_system_prompt

```python
@abstractmethod
def get_system_prompt(self) -> str:
    """
    获取系统提示词
    
    子类必须实现此方法，返回引导 Agent 行为的系统提示词。
    
    Returns:
        str: 系统提示词内容
    
    Example:
        ```python
        def get_system_prompt(self) -> str:
            return '''
            You are a SQL expert. Your task is to:
            1. Analyze the database structure
            2. Generate high-quality SQL queries
            3. Validate and optimize the results
            '''
        ```
    """
```

### _create_tools

```python
@abstractmethod
def _create_tools(self) -> List[BaseTool]:
    """
    创建工具列表
    
    子类必须实现此方法，返回 Agent 可用的工具列表。
    
    Returns:
        List[BaseTool]: LangChain 工具列表
    
    Example:
        ```python
        def _create_tools(self) -> List[BaseTool]:
            return [
                SchemaExtractionTool(db_config=self.db_config),
                SQLGenerationTool(llm=self.llm),
                SQLValidationTool(db_config=self.db_config)
            ]
        ```
    """
```

## 核心方法

### run

```python
def run(self, task: str, **kwargs) -> Dict[str, Any]:
    """
    执行任务
    
    使用 AgentExecutor 执行给定的任务。
    
    Args:
        task: 任务描述
        **kwargs: 传递给 AgentExecutor 的额外参数
    
    Returns:
        Dict[str, Any]: 执行结果
    
    Raises:
        AgentExecutionError: Agent 执行失败
        ToolExecutionError: 工具执行失败
    
    Example:
        ```python
        # 内部调用 LangChain AgentExecutor
        result = agent.run(
            "分析数据库并生成10条训练数据",
            verbose=True
        )
        
        # 等同于
        result = self.agent_executor.invoke({
            "input": task,
            **kwargs
        })
        ```
    """
```

### _initialize_agent

```python
def _initialize_agent(self) -> None:
    """
    初始化 LangChain Agent
    
    内部方法，创建和配置 AgentExecutor。
    
    使用 LangChain 组件：
    - langchain.agents.create_react_agent
    - langchain.agents.AgentExecutor
    - langchain.memory.ConversationSummaryBufferMemory
    
    配置包括：
    - 创建 ReAct agent
    - 设置工具列表
    - 配置记忆系统
    - 添加回调处理器
    """
```

### get_memory_state

```python
def get_memory_state(self) -> Dict[str, Any]:
    """
    获取当前记忆状态
    
    Returns:
        Dict[str, Any]: 记忆中存储的所有内容
    
    Example:
        ```python
        memory = agent.get_memory_state()
        print(f"Schema info: {memory.get('schema_info')}")
        ```
    """
```

### clear_memory

```python
def clear_memory(self) -> None:
    """
    清空记忆
    
    清除所有存储在记忆中的分析结果。
    
    Example:
        ```python
        # 处理新数据库前清空旧的分析结果
        agent.clear_memory()
        ```
    """
```

## 属性

### tools

```python
@property
def tools(self) -> List[BaseTool]:
    """获取工具列表"""
```

### memory

```python
@property
def memory(self) -> BaseMemory:
    """获取记忆管理器"""
```

### is_running

```python
@property
def is_running(self) -> bool:
    """检查 Agent 是否正在执行"""
```

## 使用示例

### 基本使用

```python
from semanticsql_agent.agent import BaseAgent
from semanticsql_agent.config import Settings, DatabaseConfig

# 实现自定义 Agent
class MyCustomAgent(BaseAgent):
    def get_system_prompt(self) -> str:
        return "You are a helpful SQL assistant..."
    
    def _create_tools(self) -> List[BaseTool]:
        return [
            MyCustomTool(),
            AnotherTool()
        ]

# 创建实例
agent = MyCustomAgent(
    config=Settings(),
    db_config=DatabaseConfig(
        host="localhost",
        database="mydb",
        username="root",
        password="password"
    )
)

# 执行任务
result = agent.run("Analyze the database and generate a report")
```

### 使用回调

```python
from langchain.callbacks import StdOutCallbackHandler

class ProgressCallback(BaseCallbackHandler):
    def on_tool_start(self, serialized, input_str, **kwargs):
        print(f"🔧 Starting tool: {serialized.get('name')}")
    
    def on_tool_end(self, output, **kwargs):
        print(f"✅ Tool completed")

# 创建带回调的 Agent
agent = MyCustomAgent(
    config=config,
    db_config=db_config,
    callbacks=[
        StdOutCallbackHandler(),  # 标准输出
        ProgressCallback()        # 进度提示
    ]
)
```

### 访问执行历史

```python
# 执行任务
result = agent.run("Generate SQL for user queries")

# 获取执行轨迹
trajectory = agent.agent_executor.memory.chat_memory.messages

# 分析工具调用
for message in trajectory:
    if hasattr(message, 'tool_calls'):
        print(f"Tool called: {message.tool_calls}")
```

## 配置选项

### AgentExecutor 配置

```python
# 在子类中配置 AgentExecutor
self.agent_executor = AgentExecutor(
    agent=agent,
    tools=self.tools,
    memory=self.memory,
    verbose=True,                    # 详细输出
    max_iterations=20,               # 最大迭代次数
    max_execution_time=300,          # 最大执行时间（秒）
    early_stopping_method="force",   # 停止策略
    handle_parsing_errors=True,      # 处理解析错误
    return_intermediate_steps=True   # 返回中间步骤
)
```

### 提示词配置

```python
from langchain.prompts import ChatPromptTemplate

# 创建结构化提示词
self.prompt = ChatPromptTemplate.from_messages([
    ("system", self.get_system_prompt()),
    ("human", "{input}"),
    ("assistant", "{agent_scratchpad}")
])
```

## 错误处理

```python
try:
    result = agent.run("Complex task")
except AgentExecutionError as e:
    print(f"Agent error: {e.message}")
    print(f"Last action: {e.last_action}")
except ToolExecutionError as e:
    print(f"Tool {e.tool_name} failed: {e.message}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## 最佳实践

1. **工具选择**：精心设计工具集，避免功能重叠
2. **提示词优化**：清晰描述工具使用顺序和条件
3. **记忆管理**：定期清理不需要的记忆内容
4. **错误恢复**：实现工具级别的错误处理
5. **轨迹记录**：使用回调记录执行过程

## 注意事项

1. BaseAgent 是抽象类，不能直接实例化
2. 所有工具必须继承自 `langchain.tools.BaseTool`
3. 记忆系统基于 `DatabaseAnalysisMemory`
4. 默认使用 ReAct 模式，可通过配置改变
5. 支持同步执行，异步支持需要额外实现

---

相关文档：
- [SQLAgent API](./SQLAgent-API.md)
- [记忆管理 API](./记忆管理-API.md)
- [LangChain 集成指南](../LangChain集成指南.md)