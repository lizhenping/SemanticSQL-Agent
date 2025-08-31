# SemanticSQL Agent API 手册

## 目录

1. [系统概述](#系统概述)
2. [快速开始](#快速开始)
3. [核心模块](#核心模块)
   - [Agent 模块](#agent-模块)
   - [Models 模块](#models-模块)
   - [Tools 模块](#tools-模块)
   - [Utils 模块](#utils-模块)
   - [Config 模块](#config-模块)
4. [使用指南](#使用指南)
5. [API 参考](#api-参考)
6. [最佳实践](#最佳实践)

---

## 系统概述

SemanticSQL Agent 是一个基于 ReAct（推理+行动）模式的智能 SQL 生成系统。它能够理解自然语言查询，分析数据库结构，并生成相应的 SQL 语句。

### 主要特性

- **智能 SQL 生成**：将自然语言转换为准确的 SQL 查询
- **数据库分析**：自动分析数据库结构和业务领域
- **质量保证**：SQL 验证、执行测试和反思优化
- **可扩展架构**：模块化设计，易于扩展新功能
- **完整的执行轨迹**：记录每次执行的详细过程

### 系统架构

```
SemanticSQL Agent
├── agent/          # 智能体核心
├── models/         # 数据模型
├── tools/          # 工具集合
├── utils/          # 工具类
└── config/         # 配置管理
```

---

## 快速开始

### 安装

```bash
# 克隆项目
git clone https://github.com/yourusername/semanticsql-agent.git
cd semanticsql-agent

# 安装依赖
pip install -r requirements.txt
```

### 基础使用

```python
from config.settings import Settings
from config.database import DatabaseConfig
from agent.smart_sql_agent import SmartSQLAgent

# 配置
settings = Settings()
db_config = DatabaseConfig(
    host="localhost",
    port=3306,
    database="mydb",
    username="user",
    password="password"
)

# 创建智能体
agent = SmartSQLAgent(settings, db_config)

# 执行查询
result = agent.query("查询上个月销售额最高的10个产品")

if result.success:
    print(f"SQL: {result.generated_sql}")
    print(f"结果: {result.answer}")
```

---

## 核心模块

### Agent 模块

Agent 模块是系统的核心，实现了 ReAct 模式的智能体。

#### 主要类

1. **BaseAgent** - 所有智能体的基类
   - 实现 ReAct 循环
   - 工具管理和调用
   - 执行跟踪

2. **SmartSQLAgent** - SQL 生成智能体
   - 自然语言到 SQL 的转换
   - 集成多种分析和生成工具

3. **DataGenerationAgent** - 训练数据生成
   - 自动生成 NL2SQL 训练数据
   - 多样化的查询场景

#### 关键方法

```python
# BaseAgent
agent.new_task(task: str) -> AgentExecution
agent.register_tool(name: str, tool_instance: Any, description: str)
agent.add_callback(callback: ExecutionCallback)

# SmartSQLAgent
agent.query(natural_language_query: str) -> SQLQueryResult
agent.close()
```

### Models 模块

定义系统中使用的所有数据结构。

#### 核心数据模型

1. **执行相关**
   - `AgentStep`: 单个执行步骤
   - `AgentExecution`: 完整执行记录
   - `AgentStepType`: 步骤类型枚举

2. **数据库相关**
   - `DatabaseSchema`: 数据库结构
   - `TableInfo`: 表信息
   - `ColumnInfo`: 列信息

3. **查询相关**
   - `SQLQueryResult`: 查询结果
   - `GeneratedSQL`: 生成的 SQL
   - `ValidationResult`: 验证结果

#### 异常类

- `SemanticSQLError`: 基础异常类
- `ToolExecutionError`: 工具执行错误
- `DatabaseConnectionError`: 数据库连接错误
- `ValidationError`: 验证错误

### Tools 模块

提供各种专门的工具来完成特定任务。

#### 工具分类

1. **分析工具** (`analysis_tools/`)
   - `SchemaExtractionTool`: 提取数据库结构
   - `DomainAnalysisTool`: 分析业务领域
   - `ERAnalysisTool`: 实体关系分析
   - `FieldClassificationTool`: 字段分类

2. **生成工具** (`generation_tools/`)
   - `SQLGenerationTool`: 生成 SQL 查询
   - `QuestionGenerationTool`: 生成自然语言问题
   - `ScenarioTool`: 生成查询场景
   - `OperationSelectionTool`: 选择 SQL 操作

3. **验证工具** (`validation_tools/`)
   - `SQLValidationTool`: 验证 SQL 语法
   - `SQLExecutionTool`: 执行 SQL 查询

4. **反思工具** (`reflection_tools/`)
   - `SQLReflectionTool`: 分析和优化 SQL

5. **思考工具** (`thinking_tools/`)
   - `SequentialThinkingTool`: 顺序推理

#### 工具基类

```python
class BaseTool(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...
    
    @property
    @abstractmethod
    def description(self) -> str: ...
    
    @abstractmethod
    def _execute(self, **kwargs) -> Any: ...
    
    def run(self, **kwargs) -> Dict[str, Any]: ...
```

### Utils 模块

提供系统级的工具类。

#### 主要组件

1. **DatabaseManager** - 数据库连接管理
   - 统一的数据库接口
   - 连接池管理
   - 查询执行

2. **LLMClient** - 大语言模型客户端
   - OpenAI API 兼容
   - 聊天和补全功能
   - 函数调用支持

3. **TrajectoryRecorder** - 轨迹记录器
   - 保存执行历史
   - 轨迹分析和搜索
   - 性能统计

### Config 模块

管理系统配置。

#### 配置类

1. **Settings** - 全局设置
   - LLM 配置
   - Agent 配置
   - 工具启用控制
   - 日志和轨迹设置

2. **DatabaseConfig** - 数据库配置
   - 连接参数
   - 连接池设置
   - 数据库类型支持

---

## 使用指南

### 场景1：简单查询

```python
# 创建智能体
agent = SmartSQLAgent(settings, db_config)

# 执行简单查询
result = agent.query("显示所有用户")

print(result.generated_sql)  # SELECT * FROM users
```

### 场景2：复杂分析

```python
# 复杂的业务查询
query = """
分析最近三个月每个产品类别的销售趋势，
包括销售额环比增长率和占总销售额的比例
"""

result = agent.query(query)

# 生成的 SQL 可能包含 CTE、窗口函数等高级特性
```

### 场景3：生成训练数据

```python
# 创建数据生成智能体
gen_agent = DataGenerationAgent(settings, db_config)

# 生成训练数据
result = gen_agent.generate_training_data(
    count=100,
    output_file="training_data.jsonl"
)

print(f"生成了 {result['total_generated']} 条训练数据")
```

### 场景4：自定义工具

```python
from tools.base_tool import BaseTool, ToolParameter

class CustomAnalysisTool(BaseTool):
    @property
    def name(self) -> str:
        return "custom_analysis"
    
    @property
    def description(self) -> str:
        return "执行自定义分析"
    
    def _execute(self, data: str) -> Dict[str, Any]:
        # 实现自定义逻辑
        return {"result": "分析完成"}

# 注册到智能体
agent.register_tool(
    "custom_analysis",
    CustomAnalysisTool(),
    "自定义分析工具"
)
```

---

## API 参考

### Agent API

#### SmartSQLAgent

```python
class SmartSQLAgent(BaseAgent):
    def __init__(self, settings: Settings, db_config: DatabaseConfig)
    def query(self, natural_language_query: str) -> SQLQueryResult
    def close(self)
```

#### SQLQueryResult

```python
class SQLQueryResult(BaseModel):
    success: bool                    # 是否成功
    question: str                    # 原始查询
    sql: Optional[str] = None        # 生成的 SQL（可选）
    answer: Optional[str] = None     # 自然语言答案（可选）
    data: List[Dict[str, Any]] = []  # 查询结果数据
    row_count: int = 0               # 返回行数
    execution_time: float = 0.0      # 执行时间（秒）
    error: Optional[str] = None      # 错误信息（可选）
    steps: int = 0                   # 执行步骤数
```

### 工具 API

#### 工具执行格式

```python
result = tool.run(**params)

# 返回格式
{
    "success": bool,
    "data": Any,
    "error": Optional[str],
    "metadata": Optional[Dict]
}
```

### 配置 API

#### Settings

```python
settings = Settings(
    llm_model="gpt-3.5-turbo",
    llm_temperature=0.7,
    max_steps=10,
    enable_reflection=True
)
```

#### DatabaseConfig

```python
config = DatabaseConfig(
    type=DatabaseType.MYSQL,
    host="localhost",
    port=3306,
    database="mydb",
    username="user",
    password="password"
)
```

---

## 最佳实践

### 1. 配置管理

- 使用环境变量管理敏感信息
- 为不同环境创建配置文件
- 定期审查和更新配置

### 2. 性能优化

- 合理设置连接池大小
- 使用查询缓存
- 监控执行时间

### 3. 错误处理

```python
try:
    result = agent.query(user_input)
except ValidationError as e:
    # 处理验证错误
    logger.error(f"查询验证失败: {e}")
except DatabaseConnectionError as e:
    # 处理连接错误
    logger.error(f"数据库连接失败: {e}")
except SemanticSQLError as e:
    # 处理其他错误
    logger.error(f"执行失败: {e}")
```

### 4. 日志和监控

- 启用详细日志用于调试
- 使用轨迹记录分析性能
- 设置告警规则

### 5. 安全考虑

- 验证所有用户输入
- 使用参数化查询
- 限制查询权限
- 定期审计生成的 SQL

### 6. 扩展开发

- 继承 BaseTool 创建新工具
- 实现 ExecutionCallback 添加监控
- 自定义数据模型扩展功能

---

## 附录

### 环境变量列表

| 变量名 | 描述 | 示例值 |
|--------|------|--------|
| LLM__MODEL | 语言模型名称 | gpt-3.5-turbo |
| LLM__API_KEY | API 密钥 | sk-xxxxx |
| DB_HOST | 数据库主机 | localhost |
| DB_PORT | 数据库端口 | 3306 |
| DB_NAME | 数据库名称 | mydb |
| DB_USER | 数据库用户 | root |
| DB_PASSWORD | 数据库密码 | password |

### 常见问题

**Q: 如何提高 SQL 生成的准确性？**
A: 
- 提供完整的数据库结构信息
- 使用更低的 temperature（如 0.1）
- 启用反思功能
- 提供清晰的查询描述

**Q: 系统支持哪些数据库？**
A: 主要支持 MySQL，同时对 PostgreSQL 和 SQLite 提供基础支持。

**Q: 如何处理大型数据库？**
A: 
- 限制模式提取的表数量
- 使用采样数据
- 优化连接池配置
- 考虑分批处理

**Q: 轨迹文件太多怎么办？**
A: 
- 调整 trajectory_max_count 参数
- 使用 cleanup_old_trajectories 方法
- 启用压缩选项
- 定期归档旧文件

### 更新日志

- v2.0.0 - 全新的 ReAct 架构
- v1.0.0 - 初始版本

### 许可证

本项目采用 MIT 许可证。