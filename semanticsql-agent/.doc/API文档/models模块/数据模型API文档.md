# 数据模型 API 文档

## 概述
`models` 模块定义了 SemanticSQL Agent 系统中使用的所有数据模型。这些模型基于 Pydantic，提供了数据验证、序列化和类型提示功能。

## 枚举类型

### AgentStepType
智能体执行步骤类型。

```python
class AgentStepType(Enum):
    THOUGHT = "thought"          # 思考步骤
    ACTION = "action"            # 行动步骤
    OBSERVATION = "observation"  # 观察步骤
    REFLECTION = "reflection"    # 反思步骤
```

### DifficultyLevel
查询难度级别。

```python
class DifficultyLevel(Enum):
    EASY = "easy"      # 简单查询
    MEDIUM = "medium"  # 中等难度
    HARD = "hard"      # 困难查询
    EXPERT = "expert"  # 专家级查询
```

### SQLOperation
SQL 操作类型。

```python
class SQLOperation(Enum):
    SELECT = "SELECT"    # 基本查询
    JOIN = "JOIN"        # 连接操作
    GROUP = "GROUP"      # 分组聚合
    SUBQUERY = "SUBQUERY"  # 子查询
    WINDOW = "WINDOW"    # 窗口函数
    CTE = "CTE"          # 公共表表达式
    UNION = "UNION"      # 联合查询
```

## 智能体执行模型

### AgentStep
单个执行步骤。

```python
class AgentStep(BaseModel):
    step_type: AgentStepType           # 步骤类型
    content: str                       # 步骤内容
    timestamp: datetime                # 时间戳
    tool_name: Optional[str]           # 工具名称
    tool_input: Optional[Dict[str, Any]]  # 工具输入
    tool_output: Optional[Any]         # 工具输出
    error: Optional[str]               # 错误信息
    duration_ms: Optional[int]         # 执行时长（毫秒）
```

### AgentExecution
完整的执行记录。

```python
class AgentExecution(BaseModel):
    task_id: str                      # 任务ID
    task: str                         # 任务描述
    started_at: datetime              # 开始时间
    completed_at: Optional[datetime]  # 完成时间
    steps: List[AgentStep]            # 执行步骤列表
    final_result: Optional[Any]       # 最终结果
    status: str                       # 状态: running/completed/failed
    error: Optional[str]              # 错误信息
    metadata: Dict[str, Any]          # 元数据
```

**主要方法：**
- `add_step(step: AgentStep)`: 添加执行步骤
- `complete(result: Any = None, error: str = None)`: 标记执行完成
- `get_duration() -> Optional[float]`: 获取执行时长（秒）
- `get_summary() -> Dict[str, Any]`: 获取执行摘要

## 数据库模式模型

### ColumnInfo
列信息。

```python
class ColumnInfo(BaseModel):
    name: str                    # 列名
    data_type: str              # 数据类型
    nullable: bool = True       # 是否可空
    default: Optional[str]      # 默认值
    is_primary: bool = False    # 是否主键
    is_foreign: bool = False    # 是否外键
```

### ForeignKey
外键信息。

```python
class ForeignKey(BaseModel):
    column: str              # 本表列名
    referenced_table: str    # 引用表名
    referenced_column: str   # 引用列名
```

### TableInfo
表结构信息。

```python
class TableInfo(BaseModel):
    name: str                        # 表名
    columns: List[ColumnInfo]        # 列信息列表
    primary_key: Optional[str]       # 主键
    foreign_keys: List[ForeignKey]   # 外键列表
    indexes: List[str]               # 索引列表
    row_count: Optional[int]         # 行数
```

### TableRelationship
表关系。

```python
class TableRelationship(BaseModel):
    from_table: str         # 源表
    to_table: str           # 目标表
    relationship_type: str  # 关系类型: one-to-one, one-to-many, many-to-many
    join_condition: str     # 连接条件
```

### DatabaseSchema
数据库结构信息。

```python
class DatabaseSchema(BaseModel):
    database_name: str                      # 数据库名称
    tables: Dict[str, TableInfo]            # 表信息字典
    relationships: List[TableRelationship]  # 表关系列表
    extracted_at: datetime                  # 提取时间
```

**方法：**
- `get_table_names() -> List[str]`: 获取所有表名

## 领域分析模型

### DomainAnalysis
领域分析结果。

```python
class DomainAnalysis(BaseModel):
    domain: str                      # 领域名称
    confidence: float                # 置信度
    key_entities: List[str]          # 关键实体
    business_features: List[str]     # 业务特征
```

### FieldClassification
字段分类结果。

```python
class FieldClassification(BaseModel):
    field_name: str              # 字段名
    classification: str          # 分类: id, timestamp, amount, status等
    confidence: float            # 置信度
    reasoning: Optional[str]     # 推理说明
```

## 查询生成模型

### QueryScenario
查询场景。

```python
class QueryScenario(BaseModel):
    id: str                                    # 场景ID
    category: str                              # 类别：销售分析、库存管理等
    business_purpose: str                      # 业务目的
    complexity: DifficultyLevel                # 复杂度
    applicable_tables: List[str]               # 适用表
    required_operations: List[SQLOperation]    # 所需操作
    description: str                           # 描述
```

### GeneratedQuestion
生成的自然语言问题。

```python
class GeneratedQuestion(BaseModel):
    scenario_id: str      # 场景ID
    question: str         # 问题文本
    question_type: str    # 问题类型
    complexity: str       # 复杂度
```

### GeneratedSQL
生成的 SQL 查询。

```python
class GeneratedSQL(BaseModel):
    question_id: str           # 问题ID
    sql: str                   # SQL语句
    operations: List[str]      # 使用的操作
    tables: List[str]          # 涉及的表
    complexity_score: float    # 复杂度分数
```

### GeneratedExample
生成的示例（问题-SQL对）。

```python
class GeneratedExample(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scenario: QueryScenario           # 查询场景
    question: GeneratedQuestion       # 自然语言问题
    sql: GeneratedSQL                 # SQL查询
    validation_result: Optional[ValidationResult]  # 验证结果
    execution_result: Optional[ExecutionResult]    # 执行结果
    quality_score: Optional[float]    # 质量分数
    created_at: datetime              # 创建时间
```

## 训练数据模型

### TrainingExample
训练示例。

```python
class TrainingExample(BaseModel):
    id: str                          # 示例ID
    natural_language: str            # 自然语言查询
    sql: str                         # SQL语句
    database_schema: Dict[str, Any]  # 数据库模式
    metadata: Dict[str, Any]         # 元数据（场景、难度等）
    quality_metrics: Dict[str, float]  # 质量指标
    created_at: datetime             # 创建时间
    source: str = "generated"        # 来源
```

## 验证和执行模型

### ValidationResult
验证结果。

```python
class ValidationResult(BaseModel):
    is_valid: bool              # 是否有效
    syntax_errors: List[str]    # 语法错误
    semantic_warnings: List[str]  # 语义警告
    confidence_score: float     # 置信度分数
```

### ExecutionResult
执行结果。

```python
class ExecutionResult(BaseModel):
    success: bool               # 是否成功
    rows_affected: Optional[int]  # 影响行数
    result_data: Optional[List[Dict[str, Any]]]  # 结果数据
    execution_time_ms: Optional[int]  # 执行时间（毫秒）
    error_message: Optional[str]  # 错误信息
```

### ReflectionResult
反思结果。

```python
class ReflectionResult(BaseModel):
    original_sql: str          # 原始SQL
    improved_sql: Optional[str]  # 改进的SQL
    improvements: List[str]    # 改进点
    confidence: float          # 置信度
```

## 查询结果模型

### SQLQueryResult
SQL 查询结果。

```python
class SQLQueryResult(BaseModel):
    success: bool                           # 是否成功
    question: str                           # 自然语言查询
    sql: Optional[str] = None               # 生成的SQL（可选）
    answer: Optional[str] = None            # 自然语言答案（可选）
    data: List[Dict[str, Any]] = []         # 查询结果数据
    row_count: int = 0                      # 返回行数
    execution_time: float = 0.0             # 执行时间（秒）
    error: Optional[str] = None             # 错误信息（可选）
    steps: int = 0                          # 执行步骤数
```

## 工具输入输出模型

### ToolInput
工具输入基类。

```python
class ToolInput(BaseModel):
    """工具输入的基类"""
    pass
```

### ToolOutput
工具输出基类。

```python
class ToolOutput(BaseModel):
    success: bool                   # 是否成功
    error: Optional[str] = None     # 错误信息
    data: Optional[Dict[str, Any]] = None  # 输出数据
```

## 使用示例

### 创建执行记录
```python
from models.schemas import AgentExecution, AgentStep, AgentStepType

# 创建执行记录
execution = AgentExecution(task="查询销售数据")

# 添加步骤
step = AgentStep(
    step_type=AgentStepType.THOUGHT,
    content="需要查询上个月的销售总额"
)
execution.add_step(step)

# 完成执行
execution.complete(result={"total_sales": 1000000})
```

### 构建数据库模式
```python
from models.schemas import DatabaseSchema, TableInfo, ColumnInfo

# 创建表信息
sales_table = TableInfo(
    name="sales",
    columns=[
        ColumnInfo(name="id", data_type="int", is_primary=True),
        ColumnInfo(name="product_id", data_type="int"),
        ColumnInfo(name="amount", data_type="decimal"),
        ColumnInfo(name="sale_date", data_type="date")
    ],
    primary_key="id"
)

# 创建数据库模式
schema = DatabaseSchema(
    database_name="sales_db",
    tables={"sales": sales_table}
)
```

### 创建训练示例
```python
from models.schemas import TrainingExample

example = TrainingExample(
    id="example_001",
    natural_language="查询上个月销售额最高的产品",
    sql="SELECT product_id, SUM(amount) as total FROM sales WHERE sale_date >= '2024-01-01' GROUP BY product_id ORDER BY total DESC LIMIT 1",
    database_schema=schema.dict(),
    metadata={
        "difficulty": "medium",
        "operations": ["SELECT", "GROUP", "ORDER"]
    },
    quality_metrics={
        "syntax_score": 1.0,
        "semantic_score": 0.95
    }
)
```

## 序列化支持

所有模型都支持：
- JSON 序列化：`model.json()`
- 字典转换：`model.dict()`
- 从字典创建：`Model.parse_obj(dict_data)`
- 从 JSON 创建：`Model.parse_raw(json_string)`

## 注意事项

1. 所有时间字段都使用 ISO 格式序列化
2. ID 字段默认使用 UUID 生成
3. 所有模型都进行严格的类型验证
4. 可选字段使用 `Optional` 类型标注
5. 列表字段默认为空列表，字典字段默认为空字典