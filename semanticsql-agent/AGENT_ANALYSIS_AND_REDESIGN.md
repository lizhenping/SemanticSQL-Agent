# SemanticSQL Agent 分析与重新设计

## 1. TRAEAgent 设计分析

### 1.1 核心设计特点

#### 状态管理 (agent_basics.py)
```python
# TRAEAgent 的状态定义
class AgentStepState(Enum):
    THINKING = "thinking"
    CALLING_TOOL = "calling_tool"    # 不是 ACTING
    REFLECTING = "reflecting"         # 独立的反思状态
    COMPLETED = "completed"
    ERROR = "error"

# 步骤定义
@dataclass
class AgentStep:
    step_number: int
    state: AgentStepState
    thought: str | None = None
    tool_calls: list[ToolCall] | None = None    # 支持多个工具调用
    tool_results: list[ToolResult] | None = None # 支持多个结果
    llm_response: LLMResponse | None = None      # 保存完整的 LLM 响应
    reflection: str | None = None                # 反思内容
    error: str | None = None
    extra: dict[str, object] | None = None       # 额外信息
    llm_usage: LLMUsage | None = None           # Token 使用情况
```

#### 工具系统 (tools/base.py)
```python
# 工具调用和结果
@dataclass
class ToolCall:
    name: str
    call_id: str
    arguments: ToolCallArguments
    id: str | None = None

@dataclass
class ToolResult:
    call_id: str
    name: str
    success: bool
    result: str | None = None
    error: str | None = None
    id: str | None = None

# 工具基类
class Tool(ABC):
    def __init__(self, model_provider: str | None = None):
        self._model_provider = model_provider
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolExecResult:
        pass
```

#### 轨迹记录器 (trajectory_recorder.py)
```python
class TrajectoryRecorder:
    def __init__(self, trajectory_path: str | None = None):
        # 默认生成带时间戳的路径
        # 记录详细的 LLM 交互和 Agent 步骤
        
    def record_llm_interaction(self, messages, response, provider, model, tools):
        # 记录每次 LLM 交互的详细信息
        
    def record_agent_step(self, step_number, state, ...):
        # 记录 Agent 执行步骤
```

### 1.2 关键差异

1. **状态命名**：`CALLING_TOOL` 而不是 `ACTING`
2. **批量工具调用**：支持一次调用多个工具
3. **LLM 响应保存**：保存完整的 LLM 响应对象
4. **反思状态**：`REFLECTING` 是独立的状态
5. **轨迹记录粒度**：分别记录 LLM 交互和 Agent 步骤

## 2. 当前实现的问题

### 2.1 trajectory.py 的问题
- 缺少 LLM 交互的详细记录
- 没有记录 token 使用情况
- 文件命名方式不够灵活
- 缺少 provider/model 信息记录

### 2.2 agent_state.py 的问题
- 状态定义不完全符合 TRAEAgent
- 缺少 LLM 响应的保存
- 不支持批量工具调用
- 缺少 token 使用统计

### 2.3 base_agent.py 的问题
- 执行流程与 TRAEAgent 有差异
- 反思机制集成方式不同
- 工具调用处理过于简化

## 3. 重新设计方案

### 3.1 新的目录结构
```
semanticsql-agent/agent/
├── __init__.py
├── agent_basics.py        # 基础类型定义（参考 TRAEAgent）
├── base_agent.py          # 基础智能体类
├── sql_agent.py           # SQL 智能体实现
├── agent_executor.py      # 执行器
├── trajectory_recorder.py # 轨迹记录器
└── llm_client.py         # LLM 客户端封装
```

### 3.2 状态管理重新设计

#### agent_basics.py
```python
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Any

class AgentStepState(Enum):
    """智能体步骤状态"""
    THINKING = "thinking"
    CALLING_TOOL = "calling_tool"
    REFLECTING = "reflecting"
    COMPLETED = "completed"
    ERROR = "error"

class AgentState(Enum):
    """智能体状态"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"

@dataclass
class LLMUsage:
    """LLM Token 使用情况"""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cache_read_tokens: Optional[int] = None
    cache_creation_tokens: Optional[int] = None

@dataclass
class LLMResponse:
    """LLM 响应"""
    content: str
    model: str
    finish_reason: str
    usage: Optional[LLMUsage] = None
    tool_calls: Optional[List['ToolCall']] = None

@dataclass
class ToolCall:
    """工具调用"""
    name: str
    call_id: str
    arguments: Dict[str, Any]
    id: Optional[str] = None

@dataclass
class ToolResult:
    """工具执行结果"""
    call_id: str
    name: str
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None

@dataclass
class AgentStep:
    """智能体执行步骤"""
    step_number: int
    state: AgentStepState
    thought: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_results: Optional[List[ToolResult]] = None
    llm_response: Optional[LLMResponse] = None
    reflection: Optional[str] = None
    error: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None
    llm_usage: Optional[LLMUsage] = None

@dataclass
class AgentExecution:
    """智能体执行记录"""
    task: str
    steps: List[AgentStep]
    final_result: Optional[str] = None
    success: bool = False
    total_tokens: Optional[LLMUsage] = None
    execution_time: float = 0.0
    agent_state: AgentState = AgentState.IDLE
```

### 3.3 轨迹记录器重新设计

#### trajectory_recorder.py
```python
class TrajectoryRecorder:
    """轨迹记录器 - 参考 TRAEAgent 设计"""
    
    def __init__(self, trajectory_path: Optional[str] = None):
        if trajectory_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            trajectory_path = f"trajectories/trajectory_{timestamp}.json"
        
        self.trajectory_path = Path(trajectory_path)
        self.trajectory_data = {
            "task": "",
            "start_time": "",
            "end_time": "",
            "provider": "",
            "model": "",
            "max_steps": 0,
            "llm_interactions": [],
            "agent_steps": [],
            "success": False,
            "final_result": None,
            "execution_time": 0.0,
        }
    
    def record_llm_interaction(
        self,
        messages: List[Message],
        response: LLMResponse,
        provider: str,
        model: str,
        tools: Optional[List[Tool]] = None
    ):
        """记录 LLM 交互"""
        # 详细记录每次 LLM 调用
        
    def record_agent_step(
        self,
        step_number: int,
        state: str,
        llm_response: Optional[LLMResponse] = None,
        tool_calls: Optional[List[ToolCall]] = None,
        tool_results: Optional[List[ToolResult]] = None,
        reflection: Optional[str] = None,
        error: Optional[str] = None
    ):
        """记录智能体步骤"""
        # 记录执行步骤的详细信息
```

### 3.4 执行流程调整

1. **支持批量工具调用**
   - 一次 LLM 响应可能包含多个工具调用
   - 并行执行多个工具

2. **独立的反思阶段**
   - REFLECTING 作为独立状态
   - 可选的反思步骤

3. **更好的错误处理**
   - 工具级别的错误不立即终止
   - 支持重试机制

## 4. 实施计划

### Phase 1: 基础重构
1. 创建 `agent_basics.py` - 统一的类型定义
2. 重写 `trajectory_recorder.py` - 参考 TRAEAgent
3. 调整 `base_agent.py` - 支持新的执行流程

### Phase 2: 功能增强
1. 支持批量工具调用
2. 实现独立的反思机制
3. 添加 token 使用统计

### Phase 3: 优化
1. 并行工具执行
2. 更好的错误恢复
3. 轨迹分析工具

## 5. 保留的设计优点

1. **模块化的工具系统** - 继续使用基于 Pydantic 的工具定义
2. **LangChain 集成** - 保留 create_react_agent 的使用
3. **配置管理** - 保持灵活的配置系统

## 6. 主要改进

1. **更准确的状态管理** - 完全符合 TRAEAgent 的设计
2. **详细的轨迹记录** - 分别记录 LLM 交互和执行步骤
3. **批量操作支持** - 提高执行效率
4. **Token 统计** - 成本监控和优化