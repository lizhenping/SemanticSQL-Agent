# SemanticSQL Agent 架构重构方案

## 一、架构差距分析

### 1.1 当前代码与架构规范的主要差距

#### 1. **ReAct 执行引擎缺失**
- **架构要求**：独立的 ReAct Engine 模块，实现思考-行动-观察循环
- **当前状态**：ReAct 逻辑分散在 `BaseAgent` 和 `SmartSQLAgent` 中，未独立成模块
- **影响**：执行流程不清晰，难以调试和扩展

#### 2. **工具系统不规范**
- **架构要求**：统一的 `BaseTool` 接口，标准的工具注册机制
- **当前状态**：
  - 存在多个基类：`BaseTool`、`TraeBaseTool`、`agent_tools` 混用
  - 工具分散在 `tools/` 的多个子目录，缺乏统一管理
  - 部分工具缺少 Function Calling Schema
- **影响**：工具管理混乱，难以统一调度

#### 3. **执行追踪机制不完整**
- **架构要求**：完整的 `ExecutionTracker`，记录每个步骤的详细信息
- **当前状态**：
  - `execution_tracker.py` 存在但功能简单
  - 缺少步骤类型定义（thought/action/observation）
  - 没有执行摘要和分析功能
- **影响**：无法有效调试和优化执行过程

#### 4. **数据生成流程缺失**
- **架构要求**：完整的 6 阶段流程（初始化→分析→生成→验证→反思→输出）
- **当前状态**：
  - 缺少场景生成工具（`ScenarioTool`）
  - 缺少操作选择工具（`OperationSelectionTool`）
  - 缺少问题生成工具（`QuestionGenerationTool`）
  - 反思工具存在但未集成到主流程
- **影响**：无法生成高质量的 NL2SQL 数据集

#### 5. **配置管理不一致**
- **架构要求**：统一的配置加载机制，支持环境变量覆盖
- **当前状态**：
  - 配置系统基本完整但缺少 `GenerationConfig` 和 `OutputConfig`
  - 环境变量支持不完整
  - 配置验证机制缺失
- **影响**：配置管理复杂，容易出错

#### 6. **错误处理架构缺失**
- **架构要求**：分层的错误处理和恢复策略
- **当前状态**：错误处理分散，没有统一的策略
- **影响**：系统健壮性不足

## 二、代码重构方案

### 2.1 核心架构重构

#### Phase 1: ReAct 引擎实现（优先级：高）

```python
# agent/react_engine.py
class ReactEngine:
    """独立的 ReAct 执行引擎"""
    
    def __init__(self, agent, tracker):
        self.agent = agent
        self.tracker = tracker
        self.max_steps = 10
        
    def execute(self, task: str) -> AgentExecution:
        """执行 ReAct 循环"""
        current_context = {"task": task}
        steps = 0
        
        while not self._is_complete(current_context) and steps < self.max_steps:
            # Think
            thought = self._think(current_context)
            self.tracker.record_step(AgentStepType.THOUGHT, thought)
            
            # Act
            action = self._decide_action(thought)
            self.tracker.record_step(AgentStepType.ACTION, action)
            
            # Observe
            result = self._execute_action(action)
            self.tracker.record_step(AgentStepType.OBSERVATION, result)
            
            # Update context
            current_context.update({"last_result": result})
            steps += 1
            
        return self.tracker.get_execution()
```

#### Phase 2: 工具系统标准化

```python
# tools/base_tool.py
class BaseTool(ABC):
    """统一的工具基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        pass
    
    @abstractmethod
    def run(self, **kwargs) -> ToolResult:
        pass
    
    def get_schema(self) -> Dict[str, Any]:
        """获取 Function Calling Schema"""
        pass
```

```python
# tools/registry.py
class ToolRegistry:
    """工具注册中心"""
    
    def __init__(self):
        self._tools = {}
        
    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool
        
    def get_tool(self, name: str) -> BaseTool:
        return self._tools.get(name)
        
    def list_tools(self) -> List[str]:
        return list(self._tools.keys())
```

### 2.2 工具系统重构

#### 需要创建的新工具

1. **场景生成工具**
```python
# tools/generation/scenario_tool.py
class ScenarioTool(BaseTool):
    """生成业务场景"""
    name = "generate_scenario"
    description = "基于数据库结构生成业务场景"
    
    def run(self, schema_info: Dict) -> ToolResult:
        # 生成销售分析、库存查询等场景
        pass
```

2. **操作选择工具**
```python
# tools/generation/operation_selection_tool.py
class OperationSelectionTool(BaseTool):
    """选择 SQL 操作类型"""
    name = "select_operation"
    description = "选择适合的 SQL 操作类型"
    
    def run(self, scenario: str) -> ToolResult:
        # 返回 SELECT, JOIN, GROUP BY 等操作
        pass
```

3. **问题生成工具**
```python
# tools/generation/question_generation_tool.py
class QuestionGenerationTool(BaseTool):
    """生成自然语言问题"""
    name = "generate_question"
    description = "基于场景生成自然语言问题"
    
    def run(self, scenario: str, operation: str) -> ToolResult:
        # 生成符合场景的问题
        pass
```

### 2.3 执行追踪增强

```python
# agent/execution_tracker.py
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Any, Dict

class AgentStepType(Enum):
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"

@dataclass
class AgentStep:
    step_type: AgentStepType
    content: str
    timestamp: datetime
    tool_name: Optional[str] = None
    tool_output: Optional[Any] = None
    error: Optional[str] = None

@dataclass
class AgentExecution:
    task_id: str
    task: str
    started_at: datetime
    completed_at: Optional[datetime]
    steps: List[AgentStep]
    final_result: Optional[Any]
    status: str  # running/completed/failed
    
class ExecutionTracker:
    def __init__(self):
        self.execution_id = str(uuid.uuid4())
        self.steps = []
        self.start_time = datetime.now()
        self.end_time = None
        
    def record_step(self, step_type: AgentStepType, content: str, **kwargs):
        step = AgentStep(
            step_type=step_type,
            content=content,
            timestamp=datetime.now(),
            **kwargs
        )
        self.steps.append(step)
        
    def get_execution_summary(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "total_steps": len(self.steps),
            "duration": (self.end_time - self.start_time).seconds if self.end_time else None,
            "tools_used": self._get_tools_used(),
            "success_rate": self._calculate_success_rate()
        }
```

## 三、模块划分和接口规范

### 3.1 模块架构

```
semanticsql-agent/
├── agent/                    # 智能体层
│   ├── base_agent.py        # 基础智能体
│   ├── react_engine.py      # ReAct 引擎
│   ├── smart_sql_agent.py   # SQL 智能体
│   └── execution_tracker.py # 执行追踪
│
├── tools/                    # 工具层
│   ├── base_tool.py         # 工具基类
│   ├── registry.py          # 工具注册
│   ├── analysis/            # 分析工具
│   ├── generation/          # 生成工具
│   ├── validation/          # 验证工具
│   └── reflection/          # 反思工具
│
├── config/                   # 配置层
│   ├── config.py            # 统一配置
│   ├── loader.py            # 配置加载
│   └── validator.py         # 配置验证
│
├── core/                     # 核心模块
│   ├── models.py            # 数据模型
│   ├── exceptions.py        # 异常定义
│   └── constants.py         # 常量定义
│
└── infrastructure/          # 基础设施
    ├── database/            # 数据库管理
    ├── llm/                 # LLM 客户端
    └── logger/              # 日志系统
```

### 3.2 接口规范

#### 工具接口
```python
class ToolInterface:
    name: str
    description: str
    parameters: List[ToolParameter]
    
    def run(self, **kwargs) -> ToolResult
    def get_schema(self) -> Dict[str, Any]
    def validate_input(self, **kwargs) -> bool
```

#### 智能体接口
```python
class AgentInterface:
    def initialize(self, config: Config) -> None
    def execute(self, task: str) -> AgentExecution
    def register_tool(self, tool: BaseTool) -> None
    def get_status(self) -> AgentStatus
```

#### 数据流接口
```python
class DataFlowInterface:
    def transform(self, input_data: Any) -> Any
    def validate(self, data: Any) -> bool
    def get_schema(self) -> Dict[str, Any]
```

## 四、配置管理一致性方案

### 4.1 完整配置结构

```python
# config/config.py
@dataclass
class GenerationConfig:
    """数据生成配置"""
    scenarios_per_domain: int = 5
    questions_per_scenario: int = 10
    sql_complexity_levels: List[str] = field(default_factory=lambda: ["simple", "medium", "complex"])
    enable_reflection: bool = True
    
@dataclass
class OutputConfig:
    """输出配置"""
    format: str = "json"  # json/csv/parquet
    output_dir: str = "./output"
    batch_size: int = 100
    include_metadata: bool = True

@dataclass
class Config:
    """统一配置"""
    app: AppConfig
    database: DatabaseConfig
    llm: LLMConfig
    agent: AgentConfig
    generation: GenerationConfig
    output: OutputConfig
    
    @classmethod
    def load(cls) -> "Config":
        """统一加载机制"""
        # 1. 默认配置
        config = cls.default()
        
        # 2. 配置文件
        if config_file := os.getenv("SEMANTICSQL_CONFIG"):
            config.merge_from_file(config_file)
            
        # 3. 环境变量
        config.merge_from_env()
        
        # 4. 验证
        config.validate()
        
        return config
```

### 4.2 环境变量映射

```python
ENV_MAPPING = {
    # 数据库配置
    "DB_TYPE": "database.type",
    "DB_HOST": "database.host",
    "DB_PORT": "database.port",
    "DB_NAME": "database.database",
    "DB_USER": "database.username",
    "DB_PASSWORD": "database.password",
    
    # LLM 配置
    "LLM_MODEL": "llm.model",
    "LLM_BASE_URL": "llm.base_url",
    "LLM_API_KEY": "llm.api_key",
    
    # 生成配置
    "GEN_SCENARIOS": "generation.scenarios_per_domain",
    "GEN_QUESTIONS": "generation.questions_per_scenario",
    
    # 输出配置
    "OUTPUT_FORMAT": "output.format",
    "OUTPUT_DIR": "output.output_dir"
}
```

## 五、代码迁移实施计划

### Phase 1: 基础架构（第1-2周）
- [ ] 实现 ReAct 引擎
- [ ] 标准化工具基类
- [ ] 增强执行追踪器
- [ ] 实现工具注册中心

### Phase 2: 工具系统（第3-4周）
- [ ] 迁移现有工具到新基类
- [ ] 创建缺失的生成工具
- [ ] 实现工具验证机制
- [ ] 添加 Function Calling Schema

### Phase 3: 数据生成流程（第5-6周）
- [ ] 实现 6 阶段流程
- [ ] 集成所有工具
- [ ] 添加流程控制逻辑
- [ ] 实现质量控制机制

### Phase 4: 配置和错误处理（第7周）
- [ ] 完善配置系统
- [ ] 实现错误恢复策略
- [ ] 添加配置验证
- [ ] 环境变量支持

### Phase 5: 测试和优化（第8周）
- [ ] 单元测试覆盖
- [ ] 集成测试
- [ ] 性能优化
- [ ] 文档更新

## 六、迁移脚本示例

### 6.1 工具迁移脚本

```python
# scripts/migrate_tools.py
import os
import re
from pathlib import Path

def migrate_tool(tool_path: Path):
    """迁移单个工具到新架构"""
    with open(tool_path, 'r') as f:
        content = f.read()
    
    # 替换基类
    content = re.sub(
        r'from tools\.base_tool import BaseTool',
        'from tools.base_tool import BaseTool',
        content
    )
    
    # 添加必需方法
    if 'def get_schema' not in content:
        schema_method = '''
    def get_schema(self) -> Dict[str, Any]:
        """获取 Function Calling Schema"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self._get_parameters()
            }
        }
'''
        content += schema_method
    
    # 保存迁移后的文件
    backup_path = tool_path.with_suffix('.bak')
    tool_path.rename(backup_path)
    
    with open(tool_path, 'w') as f:
        f.write(content)
    
    print(f"迁移完成: {tool_path}")

# 执行迁移
tools_dir = Path("tools")
for tool_file in tools_dir.rglob("*.py"):
    if tool_file.name != "__init__.py" and tool_file.name != "base_tool.py":
        migrate_tool(tool_file)
```

### 6.2 配置迁移脚本

```python
# scripts/migrate_config.py
import yaml
from pathlib import Path

def migrate_config(old_config_path: str, new_config_path: str):
    """迁移旧配置到新格式"""
    with open(old_config_path, 'r') as f:
        old_config = yaml.safe_load(f)
    
    # 构建新配置结构
    new_config = {
        "app": {
            "name": "SemanticSQL Agent",
            "version": "2.0.0",
            "environment": "development"
        },
        "database": old_config.get("database", {}),
        "llm": old_config.get("llm", {}),
        "agent": {
            "max_steps": 10,
            "enable_reflection": True,
            "verbose": True
        },
        "generation": {
            "scenarios_per_domain": 5,
            "questions_per_scenario": 10,
            "sql_complexity_levels": ["simple", "medium", "complex"],
            "enable_reflection": True
        },
        "output": {
            "format": "json",
            "output_dir": "./output",
            "batch_size": 100,
            "include_metadata": True
        }
    }
    
    # 保存新配置
    with open(new_config_path, 'w') as f:
        yaml.dump(new_config, f, default_flow_style=False, sort_keys=False)
    
    print(f"配置迁移完成: {new_config_path}")

# 执行迁移
migrate_config("configs/config.yaml", "configs/config_v2.yaml")
```

## 七、验证标准

### 7.1 架构合规性检查清单

- [ ] ReAct 引擎独立实现
- [ ] 所有工具继承自统一基类
- [ ] 执行追踪记录完整
- [ ] 6 阶段流程完整实现
- [ ] 配置管理统一
- [ ] 错误处理机制完善
- [ ] Function Calling Schema 完整
- [ ] 数据流转换正确
- [ ] 模块职责清晰
- [ ] 接口规范统一

### 7.2 功能验证

```python
# tests/test_architecture.py
def test_react_engine():
    """测试 ReAct 引擎"""
    engine = ReactEngine(agent, tracker)
    execution = engine.execute("分析数据库")
    assert execution.status == "completed"
    assert len(execution.steps) > 0

def test_tool_registry():
    """测试工具注册"""
    registry = ToolRegistry()
    tool = SchemaExtractionTool()
    registry.register(tool)
    assert registry.get_tool("schema_extraction") == tool

def test_data_generation_flow():
    """测试数据生成流程"""
    agent = SmartSQLAgent(config)
    result = agent.generate_dataset(count=10)
    assert len(result["examples"]) == 10
    assert all(ex["sql"] for ex in result["examples"])
```

## 八、风险和缓解措施

### 8.1 主要风险

1. **代码破坏性变更**
   - 风险：重构可能破坏现有功能
   - 缓解：分阶段实施，保留旧代码备份

2. **性能退化**
   - 风险：新架构可能影响性能
   - 缓解：添加性能测试，优化关键路径

3. **集成复杂性**
   - 风险：新旧代码集成困难
   - 缓解：使用适配器模式，渐进式迁移

### 8.2 回滚策略

```bash
# 创建重构分支
git checkout -b refactoring-v2

# 定期创建检查点
git tag checkpoint-phase1
git tag checkpoint-phase2

# 如需回滚
git checkout main
git reset --hard checkpoint-phase1
```

## 九、总结

本重构方案基于架构文档要求，通过分阶段实施，将当前代码库逐步迁移到符合规范的架构。重点解决了 ReAct 引擎缺失、工具系统混乱、执行追踪不完整等核心问题，确保系统具有良好的扩展性和维护性。