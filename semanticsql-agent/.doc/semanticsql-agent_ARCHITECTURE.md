# SemanticSQL Agent 架构文档

## 1. 系统概述

### 1.1 架构理念
SemanticSQL Agent 采用基于智能体（Agent）的架构设计，通过 ReAct（Reasoning + Acting）模式实现自主的 NL2SQL 数据生成。系统的核心是一个能够理解任务、规划执行步骤、调用工具并根据结果调整策略的智能体。

### 1.2 架构特点
- **智能体驱动**：中央智能体负责任务编排和决策
- **工具生态**：模块化的工具系统，每个工具完成特定功能
- **执行追踪**：完整记录执行过程，支持调试和优化
- **灵活扩展**：易于添加新工具和功能

### 1.3 技术栈
- **编程语言**：Python 3.8+
- **LLM 框架**：OpenAI API（支持 Qwen）
- **数据库**：SQLAlchemy（支持 MySQL、PostgreSQL、SQLite）
- **CLI 框架**：Click
- **数据验证**：Pydantic
- **配置管理**：YAML + 环境变量

## 2. 系统架构

### 2.1 架构分层

```
┌─────────────────────────────────────────────────────────┐
│                    用户接口层 (CLI)                      │
│              命令行界面，用户交互入口                     │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────┐
│                    智能体层 (Agent)                      │
│  ┌─────────────────────────────────────────────────┐   │
│  │                SmartSQLAgent                     │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────┐ │   │
│  │  │  ReAct   │  │Execution │  │    Tools     │ │   │
│  │  │  Engine  │  │ Tracker  │  │  Registry    │ │   │
│  │  └──────────┘  └──────────┘  └──────────────┘ │   │
│  └─────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────┐
│                     工具层 (Tools)                       │
│  ┌──────────┐  ┌──────────┐  ┌────────┐  ┌──────────┐ │
│  │ Analysis │  │Generation│  │  SQL   │  │Reflection│ │
│  │  Tools   │  │  Tools   │  │ Tools  │  │  Tool    │ │
│  └──────────┘  └──────────┘  └────────┘  └──────────┘ │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────┐
│                   基础设施层 (Infrastructure)            │
│  ┌──────────┐  ┌──────────┐  ┌────────┐  ┌──────────┐ │
│  │  Config  │  │   LLM    │  │Database│  │  Logger  │ │
│  │  Manager │  │  Client  │  │ Client │  │  System  │ │
│  └──────────┘  └──────────┘  └────────┘  └──────────┘ │
└─────────────────────────────────────────────────────────┘
```

### 2.2 组件职责

#### 2.2.1 用户接口层
- 提供命令行接口
- 解析用户输入
- 展示执行结果
- 处理配置加载

#### 2.2.2 智能体层
- **ReAct Engine**：实现思考-行动-观察循环
- **Execution Tracker**：记录执行轨迹
- **Tools Registry**：管理和调度工具

#### 2.2.3 工具层
- **分析工具**：数据库结构分析、领域识别等
- **生成工具**：场景、问题、SQL 生成
- **SQL 工具**：验证和执行
- **反思工具**：质量评估和优化

#### 2.2.4 基础设施层
- **配置管理**：统一的配置加载和管理
- **LLM 客户端**：与大语言模型交互
- **数据库客户端**：数据库连接和操作
- **日志系统**：统一的日志记录

## 3. 核心流程

### 3.1 数据生成主流程

```
开始
  │
  ├─→ 1. 初始化阶段
  │     ├─→ 加载配置
  │     ├─→ 建立数据库连接
  │     └─→ 初始化 LLM 客户端
  │
  ├─→ 2. 分析阶段
  │     ├─→ 提取数据库结构 (SchemaExtractionTool)
  │     ├─→ 分析业务领域 (DomainAnalysisTool)
  │     ├─→ 分类字段类型 (FieldClassificationTool)
  │     └─→ 分析表间关系 (ERAnalysisTool)
  │
  ├─→ 3. 生成阶段
  │     ├─→ 生成业务场景 (ScenarioTool)
  │     ├─→ 选择 SQL 操作 (OperationSelectionTool)
  │     ├─→ 生成自然语言问题 (QuestionGenerationTool)
  │     └─→ 生成 SQL 查询 (SQLGenerationTool)
  │
  ├─→ 4. 验证阶段
  │     ├─→ 验证 SQL 语法 (SQLValidationTool)
  │     └─→ 执行 SQL 测试 (SQLExecutionTool)
  │
  ├─→ 5. 反思阶段
  │     └─→ 分析并优化 (SQLReflectionTool)
  │
  └─→ 6. 输出结果
        └─→ 格式化并保存数据集
```

### 3.2 ReAct 执行循环

```python
while not task_complete and steps < max_steps:
    # 1. Think: 分析当前状态，决定下一步
    thought = agent.think(current_context)
    tracker.record_step("thought", thought)
    
    # 2. Act: 选择并执行工具
    action = agent.decide_action(thought)
    tracker.record_step("action", action)
    
    # 3. Observe: 观察执行结果
    result = tool.execute(action)
    tracker.record_step("observation", result)
    
    # 4. Update: 更新上下文
    current_context.update(result)
```

## 4. 工具系统设计

### 4.1 工具分类

#### 4.1.1 分析工具 (Analysis Tools)
```
tools/analysis/
├── schema_extraction_tool.py    # 提取数据库结构
├── domain_analysis_tool.py      # 识别业务领域
├── field_classification_tool.py # 字段分类
└── er_analysis_tool.py         # 关系分析
```

**功能职责**：
- 理解数据库结构和业务含义
- 为后续生成提供基础信息
- 识别数据特征和模式

#### 4.1.2 生成工具 (Generation Tools)
```
tools/generation/
├── scenario_tool.py             # 场景生成
├── operation_selection_tool.py  # 操作选择
├── question_generation_tool.py  # 问题生成
└── sql_generation_tool.py      # SQL生成
```

**生成流程**：
1. **场景生成**：创建业务场景（如"销售分析"、"库存查询"）
2. **操作选择**：选择 SQL 操作类型（SELECT、JOIN、GROUP BY 等）
3. **问题生成**：生成自然语言问题
4. **SQL 生成**：生成对应的 SQL 查询

#### 4.1.3 验证工具 (Validation Tools)
```
tools/validation/
├── sql_validation_tool.py       # SQL语法验证
└── sql_execution_tool.py       # SQL执行测试
```

**验证策略**：
- 静态验证：检查 SQL 语法
- 动态验证：实际执行并检查结果

#### 4.1.4 反思工具 (Reflection Tool)
```
tools/reflection/
└── sql_reflection_tool.py      # 执行分析与优化
```

**反思机制**：
- 分析执行结果
- 评估查询质量
- 提供优化建议
- 生成改进版本

### 4.2 工具接口设计

```python
class BaseTool(ABC):
    """工具基类"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = get_logger(self.__class__.__name__)
    
    @property
    @abstractmethod
    def name(self) -> str:
        """工具唯一标识"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """工具功能描述"""
        pass
    
    @abstractmethod
    def run(self, **kwargs) -> Dict[str, Any]:
        """执行工具，返回标准格式结果"""
        pass
    
    def get_schema(self) -> Dict[str, Any]:
        """获取 Function Calling Schema"""
        pass
```

## 5. 执行追踪机制

### 5.1 追踪器设计

```python
class ExecutionTracker:
    """执行轨迹记录器"""
    
    def __init__(self):
        self.execution_id = str(uuid.uuid4())
        self.steps = []
        self.start_time = None
        self.end_time = None
        self.metadata = {}
    
    def record_step(self, step_type: AgentStepType, 
                   content: str, **kwargs):
        """记录单个执行步骤"""
        step = AgentStep(
            step_type=step_type,
            content=content,
            timestamp=datetime.now(),
            **kwargs
        )
        self.steps.append(step)
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """获取执行摘要"""
        return {
            "execution_id": self.execution_id,
            "total_steps": len(self.steps),
            "duration": (self.end_time - self.start_time).seconds,
            "tools_used": self._get_tools_used(),
            "success_rate": self._calculate_success_rate()
        }
```

### 5.2 轨迹数据结构

```python
@dataclass
class AgentStep:
    """单个执行步骤"""
    step_type: AgentStepType  # thought/action/observation
    content: str              # 步骤内容
    timestamp: datetime       # 时间戳
    tool_name: Optional[str]  # 使用的工具
    tool_output: Optional[Any] # 工具输出
    error: Optional[str]      # 错误信息

@dataclass
class AgentExecution:
    """完整执行记录"""
    task_id: str
    task: str
    started_at: datetime
    completed_at: Optional[datetime]
    steps: List[AgentStep]
    final_result: Optional[Any]
    status: str  # running/completed/failed
```

## 6. 数据流设计

### 6.1 数据流向图

```
输入参数
    ↓
配置加载 ──→ Config 对象
    ↓
数据库连接 ──→ 数据库结构
    ↓
分析工具 ──→ 分析结果
    ↓         ├─ 表结构
              ├─ 领域信息
              ├─ 字段分类
              └─ 关系图谱
生成工具 ←────┘
    ↓
    ├─→ 场景列表
    ├─→ 操作类型
    ├─→ 问题集合
    └─→ SQL 查询
         ↓
验证工具 ←────┘
    ↓
    ├─→ 验证结果
    └─→ 执行结果
         ↓
反思工具 ←────┘
    ↓
    └─→ 优化建议
         ↓
输出处理 ←────┘
    ↓
最终数据集
```

### 6.2 数据模型转换

```python
# 原始数据 → 分析模型
DatabaseSchema → SchemaAnalysis → DomainInfo

# 分析模型 → 生成模型  
DomainInfo → QueryScenario → SQLOperation → Question → SQL

# 生成模型 → 验证模型
SQL → ValidationResult → ExecutionResult

# 验证模型 → 输出模型
ExecutionResult → ReflectionResult → TrainingExample
```

## 7. 配置架构

### 7.1 配置层次

```
环境变量
    ↓ (最高优先级)
命令行参数
    ↓
配置文件
    ↓
默认值
    (最低优先级)
```

### 7.2 配置结构

```python
@dataclass
class Config:
    """统一配置"""
    database: DatabaseConfig
    llm: LLMConfig
    agent: AgentConfig
    generation: GenerationConfig
    output: OutputConfig
    
    @classmethod
    def load(cls) -> "Config":
        """加载配置，合并多个来源"""
        # 1. 加载默认配置
        config = cls.default()
        
        # 2. 加载配置文件
        if config_file := os.getenv("SEMANTICSQL_CONFIG"):
            config.merge_from_file(config_file)
        
        # 3. 加载环境变量
        config.merge_from_env()
        
        # 4. 验证配置
        config.validate()
        
        return config
```

## 8. 错误处理架构

### 8.1 错误传播链

```
工具层错误
    ↓ (捕获并包装)
智能体层处理
    ↓ (记录并决策)
执行策略调整
    ↓ (重试/跳过/终止)
用户层反馈
```

### 8.2 错误恢复策略

```python
class ErrorRecoveryStrategy:
    """错误恢复策略"""
    
    def handle_tool_error(self, error: ToolError) -> RecoveryAction:
        """处理工具错误"""
        if error.is_transient():
            return RecoveryAction.RETRY
        elif error.is_partial():
            return RecoveryAction.CONTINUE_WITH_WARNING
        else:
            return RecoveryAction.ABORT
    
    def handle_validation_error(self, error: ValidationError) -> RecoveryAction:
        """处理验证错误"""
        if error.can_fix():
            return RecoveryAction.FIX_AND_RETRY
        else:
            return RecoveryAction.SKIP
```

## 9. 扩展性设计

### 9.1 添加新工具

```python
# 1. 创建工具类
class MyNewTool(BaseTool):
    name = "my_new_tool"
    description = "我的新工具"
    
    def run(self, **kwargs) -> Dict[str, Any]:
        # 实现工具逻辑
        pass

# 2. 注册到智能体
agent.register_tool(MyNewTool(config))

# 3. 工具自动可用于 ReAct 循环
```

### 9.2 自定义智能体

```python
class CustomAgent(BaseAgent):
    """自定义智能体"""
    
    def get_system_prompt(self) -> str:
        """自定义系统提示词"""
        return "你是一个专门的数据分析智能体..."
    
    def _should_use_reflection(self) -> bool:
        """自定义反思策略"""
        return self.config.custom_reflection_enabled
```

### 9.3 扩展输出格式

```python
# output/formatters/custom_formatter.py
def format_for_custom_platform(dataset: Dict) -> Any:
    """自定义平台格式"""
    return {
        "version": "1.0",
        "examples": [
            transform_example(ex) for ex in dataset["examples"]
        ]
    }
```

## 10. 性能优化架构

### 10.1 缓存层次

```
LLM 响应缓存
    ├─→ 相同输入的响应
    └─→ TTL: 1 小时

数据库结构缓存
    ├─→ 表结构信息
    └─→ TTL: 会话期间

工具结果缓存
    ├─→ 确定性工具的输出
    └─→ TTL: 任务期间
```

### 10.2 并发架构

```python
# 可并行的工具组
PARALLEL_TOOL_GROUPS = [
    ["schema_extraction", "domain_analysis"],  # 分析阶段
    ["sql_validation", "sql_execution"],       # 验证阶段
]

# 并发执行器
async def execute_parallel_tools(tools: List[str], context: Dict):
    """并行执行工具组"""
    tasks = [
        execute_tool_async(tool, context) 
        for tool in tools
    ]
    results = await asyncio.gather(*tasks)
    return dict(zip(tools, results))
```

## 11. 监控和可观测性

### 11.1 指标收集

```python
# 性能指标
- 任务执行时间
- 工具调用次数
- LLM token 使用量
- 数据生成速率

# 质量指标
- SQL 验证通过率
- 执行成功率
- 反思改进率
- 数据多样性得分

# 系统指标
- 内存使用
- CPU 使用率
- 数据库连接数
- API 调用频率
```

### 11.2 日志聚合

```
应用日志 ──→ 日志收集器 ──→ 日志分析
                ↓
            日志存储
                ↓
            告警系统
```

## 12. 安全架构

### 12.1 安全层次

```
API 层安全
    ├─→ API Key 管理
    └─→ 请求限流

数据层安全
    ├─→ SQL 注入防护
    └─→ 敏感数据脱敏

系统层安全
    ├─→ 权限最小化
    └─→ 资源隔离
```

### 12.2 凭据管理

```python
# 凭据加载优先级
1. 环境变量 (推荐生产环境)
2. 密钥管理服务 (KMS)
3. 加密配置文件
4. 本地配置文件 (仅开发环境)
```

这个架构设计提供了清晰的系统结构、组件职责、数据流向和扩展机制，为 SemanticSQL Agent 的实现和维护提供了坚实的基础。