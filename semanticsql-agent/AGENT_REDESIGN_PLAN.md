# SemanticSQL Agent 重新设计方案

基于 TRAEAgent 的架构设计，结合 SemanticSQL 的具体需求。

## 1. 核心架构设计

### 1.1 目录结构
```
semanticsql-agent/agent/
├── __init__.py
├── base_agent.py          # 基础智能体类（参考 TRAEAgent）
├── sql_agent.py           # SQL 智能体实现
├── agent_state.py         # 智能体状态管理
├── agent_executor.py      # 执行器（ReAct 循环）
└── trajectory.py          # 轨迹记录
```

### 1.2 核心类设计

#### BaseAgent（基础智能体）
```python
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from langchain_core.language_models import BaseChatModel
from tools.base import BaseSemanticSQLTool
from models import QueryResult

class BaseAgent(ABC):
    """基础智能体类，参考 TRAEAgent 的设计"""
    
    def __init__(self, config: AgentConfig):
        self.llm = self._init_llm(config.model)
        self.max_steps = config.max_steps
        self.tools: List[BaseSemanticSQLTool] = []
        self.trajectory_recorder = TrajectoryRecorder()
        
    @abstractmethod
    def create_task(self, query: str, context: Optional[Dict[str, Any]] = None):
        """创建新任务"""
        pass
        
    async def execute_task(self) -> AgentExecution:
        """执行任务 - ReAct 循环"""
        # 实现 Thought-Action-Observation 循环
        pass
```

#### SQLAgent（SQL 智能体）
```python
class SQLAgent(BaseAgent):
    """SQL 查询智能体"""
    
    def __init__(self, config: SQLAgentConfig):
        super().__init__(config)
        # 初始化数据库连接
        self.db = SQLDatabase.from_uri(config.database.connection_string)
        # 初始化工具
        self.tools = self._create_tools()
        # 初始化提示管理器
        self.prompt_manager = PromptManager()
        
    def _create_tools(self) -> List[BaseSemanticSQLTool]:
        """创建工具集"""
        return [
            # 分析工具
            SchemaExtractionTool(db=self.db),
            DomainAnalysisTool(db=self.db, llm=self.llm),
            FieldClassificationTool(db=self.db, llm=self.llm),
            ERAnalysisTool(db=self.db, llm=self.llm),
            # 生成工具
            SQLGenerationTool(db=self.db, llm=self.llm),
            # 验证工具
            SQLValidationTool(db=self.db),
            SQLExecutionTool(db=self.db),
            # 思考工具
            SequentialThinkingTool(llm=self.llm)
        ]
```

## 2. 状态管理设计

### 2.1 AgentState（智能体状态）
```python
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

class AgentState(Enum):
    """智能体状态"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"

class StepState(Enum):
    """步骤状态"""
    THINKING = "thinking"
    ACTING = "acting"
    OBSERVING = "observing"
    COMPLETED = "completed"
    ERROR = "error"

@dataclass
class AgentStep:
    """智能体执行步骤"""
    step_number: int
    state: StepState
    thought: Optional[str] = None
    action: Optional[ToolCall] = None
    observation: Optional[ToolResult] = None
    error: Optional[str] = None

@dataclass
class AgentExecution:
    """智能体执行记录"""
    task: str
    steps: List[AgentStep]
    state: AgentState = AgentState.IDLE
    final_result: Optional[Any] = None
    execution_time: float = 0.0
```

## 3. 执行器设计

### 3.1 使用 LangChain 的 create_react_agent
```python
from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate

class SQLAgentExecutor:
    """SQL 智能体执行器"""
    
    def __init__(self, agent: SQLAgent):
        self.agent = agent
        self.react_agent = self._create_react_agent()
        
    def _create_react_agent(self):
        """创建 ReAct 智能体"""
        # 系统提示词
        system_prompt = self.agent.prompt_manager.get_system_prompt()
        
        # 创建 ReAct 智能体
        return create_react_agent(
            model=self.agent.llm,
            tools=self.agent.tools,
            state_modifier=system_prompt
        )
```

## 4. 工具集成策略

### 4.1 工具执行流程
1. **分析阶段**（可选，基于查询复杂度）
   - extract_database_schema
   - analyze_business_domain
   - classify_table_fields
   - analyze_entity_relationships

2. **生成阶段**
   - deep_thinking（对于复杂查询）
   - generate_sql

3. **验证执行阶段**
   - validate_sql
   - execute_sql

### 4.2 工具调用示例
```python
async def _run_step(self, step: AgentStep, messages: List[Message]):
    """执行单个步骤"""
    # 1. Thought - LLM 思考
    thought_response = await self.llm.ainvoke(messages)
    step.thought = thought_response.content
    
    # 2. Action - 解析并执行工具调用
    if tool_calls := self._parse_tool_calls(thought_response):
        step.action = tool_calls[0]
        tool_result = await self._execute_tool(step.action)
        step.observation = tool_result
        
    # 3. Observation - 处理结果
    if step.observation and step.observation.success:
        # 更新消息历史
        messages.append(...)
```

## 5. 实现步骤

### Phase 1: 基础架构（参考 TRAEAgent）
1. 实现 `base_agent.py` - 基础智能体类
2. 实现 `agent_state.py` - 状态管理
3. 实现 `trajectory.py` - 轨迹记录

### Phase 2: SQL 智能体
1. 实现 `sql_agent.py` - SQL 智能体
2. 实现 `agent_executor.py` - 执行器
3. 集成 LangChain 的 create_react_agent

### Phase 3: 工具集成
1. 确保所有工具符合 LangChain Tool 接口
2. 实现工具的自动发现和注册
3. 优化工具调用策略

## 6. 主要改进点

1. **清晰的架构**：参考 TRAEAgent 的分层设计
2. **状态管理**：明确的状态转换和步骤记录
3. **标准化接口**：所有工具使用统一的接口
4. **异步支持**：支持异步执行提高性能
5. **轨迹记录**：详细记录执行过程便于调试

## 7. 使用示例

```python
# 创建配置
config = SQLAgentConfig(
    model=ModelConfig(provider="openai", model="gpt-4"),
    database=DatabaseConfig(connection_string="mysql://..."),
    max_steps=10
)

# 创建智能体
agent = SQLAgent(config)

# 创建执行器
executor = SQLAgentExecutor(agent)

# 执行查询
result = await executor.execute(
    "查询去年销售额最高的10个产品及其销售趋势"
)

print(result.final_result)
print(f"执行步骤: {len(result.steps)}")
```