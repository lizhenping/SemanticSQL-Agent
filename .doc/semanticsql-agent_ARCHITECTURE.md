# SemanticSQL Agent 架构文档

## 1. 系统架构概览

### 1.1 架构原则
- **分层架构**: 清晰的层次划分，每层只依赖下层
- **模块化设计**: 高内聚低耦合的模块组织
- **依赖注入**: 通过配置和接口实现组件解耦
- **单一职责**: 每个组件只负责一个明确的功能

### 1.2 技术栈
- **编程语言**: Python 3.8+
- **核心框架**: 
  - Click (CLI框架)
  - SQLAlchemy (ORM和数据库访问)
  - OpenAI SDK (LLM接口)
  - Pydantic/Dataclasses (数据验证)
- **异步支持**: asyncio, aiomysql, asyncpg, aiosqlite
- **配置管理**: YAML, 环境变量

## 2. 分层架构详解

### 2.1 表示层 (Presentation Layer)

#### CLI模块 (`cli/`)
```
cli/
├── __init__.py
├── cli.py          # 主CLI入口，命令注册
└── commands/       # 具体命令实现
    ├── init.py     # 初始化配置命令
    ├── run.py      # 执行查询命令
    ├── test.py     # 测试连接命令
    └── schema.py   # 查看数据库结构命令
```

**核心组件**:
- `cli.py`: 使用Click框架实现的命令行接口
- 命令路由和参数解析
- 输出格式化（支持JSON、表格等格式）

### 2.2 业务逻辑层 (Business Logic Layer)

#### Agent模块 (`agent/`)
```
agent/
├── __init__.py
├── base_agent.py      # ReAct模式基础实现
├── sql_agent.py       # SQL专用Agent（已废弃）
└── smart_sql_agent.py # 智能SQL Agent实现
```

**BaseAgent架构**:
```python
class BaseAgent(ABC):
    """ReAct模式实现"""
    - 执行循环: Observe → Think → Act → Reflect
    - 工具管理: 注册、调用、结果处理
    - 状态跟踪: AgentStep, AgentExecution
    - LLM交互: 提示词构建、响应解析
```

**SmartSQLAgent特性**:
- 继承BaseAgent的ReAct能力
- 集成SQL工具链
- 多步推理和错误恢复
- 返回结构化的SQLQueryResult

### 2.3 工具层 (Tools Layer)

#### 工具体系结构
```
tools/
├── __init__.py
├── trae_base_tool.py   # 工具基类定义
├── sql_tools.py        # SQL相关工具
├── analysis_tools.py   # 分析类工具
└── agent_tools.py      # Agent辅助工具
```

**工具分类**:

1. **SQL工具** (`sql_tools.py`)
   - `SyncSchemaExtractionTool`: 提取数据库模式
   - `SyncSQLGenerationTool`: 生成SQL语句
   - `SyncSQLValidationTool`: 验证SQL正确性
   - `SyncSQLExecutionTool`: 执行SQL查询

2. **分析工具** (`analysis_tools.py`)
   - `SyncDomainAnalysisTool`: 领域知识分析
   - `SyncFieldClassificationTool`: 字段分类
   - `SyncERAnalysisTool`: 实体关系分析
   - `SyncSequentialThinkingTool`: 序列化思考

3. **Agent工具** (`agent_tools.py`)
   - `HumanFeedbackTool`: 人机交互
   - `FinishTool`: 任务完成标记

**工具接口设计**:
```python
class TraeBaseTool(ABC):
    name: str                    # 工具名称
    description: str             # 工具描述
    parameters: List[ToolParameter]  # 参数定义
    
    @abstractmethod
    def run(self, **kwargs) -> Any:
        """执行工具逻辑"""
        pass
```

### 2.4 数据访问层 (Data Access Layer)

#### 数据库模块 (`database/`)
```
database/
├── __init__.py
├── connection_manager.py  # 连接管理
├── pool_manager.py        # 连接池管理
└── schema_cache.py        # 模式缓存
```

**连接管理架构**:
- 支持多数据库类型（MySQL、PostgreSQL、SQLite）
- 连接池管理（异步/同步）
- 自动重连和错误恢复
- 连接生命周期管理

### 2.5 基础设施层 (Infrastructure Layer)

#### 配置模块 (`config/`)
```
config/
├── __init__.py
├── trae_config.py     # 统一配置类
├── defaults.py        # 默认配置值
└── validators.py      # 配置验证器
```

**配置架构**:
```python
@dataclass
class TraeConfig:
    app: AppConfig           # 应用配置
    database: DatabaseConfig # 数据库配置
    llm: LLMConfig          # LLM配置
    agent: AgentConfig      # Agent配置
    
    # 配置加载优先级:
    # 1. 命令行参数
    # 2. 环境变量
    # 3. 配置文件
    # 4. 默认值
```

#### 工具模块 (`utils/`)
```
utils/
├── __init__.py
├── llm_clients/       # LLM客户端实现
│   ├── llm_client.py  # 统一的LLM接口
│   └── openai_client.py
├── logger.py          # 日志配置
├── exceptions.py      # 异常定义
└── helpers.py         # 辅助函数
```

## 3. 核心流程架构

### 3.1 请求处理流程
```
用户输入
    ↓
CLI解析 → 配置加载 → Agent初始化
    ↓
工具注册 → 数据库连接 → 模式缓存
    ↓
ReAct循环执行:
    ├─ Observe: 获取当前状态
    ├─ Think: LLM推理下一步
    ├─ Act: 调用相应工具
    └─ Reflect: 评估执行结果
    ↓
结果格式化 → 输出返回
```

### 3.2 工具调用流程
```
Agent决策调用工具
    ↓
参数验证 → 工具执行准备
    ↓
执行工具逻辑:
    ├─ 数据库操作（如需要）
    ├─ LLM调用（如需要）
    └─ 业务逻辑处理
    ↓
结果封装 → 返回Agent
```

## 4. 数据模型架构

### 4.1 核心数据结构

#### Agent执行状态
```python
@dataclass
class AgentStep:
    step_type: AgentStepType  # 步骤类型
    content: str              # 步骤内容
    timestamp: datetime       # 时间戳
    tool_name: Optional[str]  # 使用的工具
    tool_input: Optional[Dict]  # 工具输入
    tool_output: Optional[Any]  # 工具输出
    error: Optional[str]      # 错误信息

@dataclass
class AgentExecution:
    task: str                 # 任务描述
    steps: List[AgentStep]    # 执行步骤
    final_result: Optional[Any]  # 最终结果
    success: bool             # 是否成功
    total_steps: int          # 总步骤数
    execution_time: float     # 执行时间
```

#### SQL查询结果
```python
@dataclass
class SQLQueryResult:
    success: bool             # 是否成功
    sql: Optional[str]        # 生成的SQL
    result: Optional[Any]     # 查询结果
    error: Optional[str]      # 错误信息
    execution_time: float     # 执行时间
    row_count: Optional[int]  # 结果行数
    metadata: Dict[str, Any]  # 元数据
```

### 4.2 配置数据模型
```python
@dataclass
class DatabaseConfig:
    type: str                 # 数据库类型
    host: str                 # 主机地址
    port: int                 # 端口
    database: str             # 数据库名
    username: str             # 用户名
    password: str             # 密码
    # 连接池配置
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30

@dataclass
class LLMConfig:
    model: str                # 模型名称
    base_url: str             # API地址
    api_key: str              # API密钥
    temperature: float = 0.1  # 温度参数
    max_tokens: int = 20000   # 最大token数
    timeout: int = 30         # 超时时间
```

## 5. 扩展点架构

### 5.1 工具扩展
- 实现TraeBaseTool接口
- 在tools/__init__.py注册
- Agent自动发现和加载

### 5.2 数据库扩展
- 实现DatabaseDialect接口
- 添加对应的异步驱动
- 更新连接字符串构建逻辑

### 5.3 LLM扩展
- 实现LLMClient接口
- 添加模型特定的参数处理
- 更新配置验证逻辑

## 6. 部署架构

### 6.1 单机部署
```
SemanticSQL Agent
    ├─ 配置文件 (trae_config.yaml)
    ├─ 环境变量 (.env)
    └─ 数据库连接
        ├─ 本地数据库
        └─ 远程数据库
```

### 6.2 容器化部署
```dockerfile
FROM python:3.8-slim
# 安装依赖
# 复制代码
# 设置入口点
ENTRYPOINT ["python", "main.py"]
```

### 6.3 服务化部署（未来）
- RESTful API接口
- gRPC服务
- 消息队列集成

## 7. 性能架构

### 7.1 缓存架构
- **模式缓存**: 数据库结构信息缓存
- **查询缓存**: 相似查询结果缓存（可选）
- **LLM缓存**: 模型响应缓存（可选）

### 7.2 并发架构
- **连接池**: 数据库连接复用
- **异步执行**: 支持异步工具调用
- **批处理**: 批量查询优化

### 7.3 监控架构
- **日志系统**: 结构化日志记录
- **性能指标**: 执行时间、成功率统计
- **错误追踪**: 详细的错误上下文

## 8. 安全架构

### 8.1 输入验证
- SQL注入防护
- 参数类型验证
- 长度和范围检查

### 8.2 权限控制
- 数据库权限最小化
- 只读查询限制
- 敏感操作审计

### 8.3 数据保护
- 连接加密
- 配置加密存储
- 查询结果脱敏