# SemanticSQL Agent API 总览

## 系统架构

SemanticSQL Agent 是一个基于 LangChain 框架的智能 SQL 生成系统，专注于生成高质量的 NL2SQL 训练数据。

### 核心设计原则

**Agent 自主决策**：
- ✅ **正确**：流程由提示词引导，Agent 自主决定执行策略
- ❌ **错误**：流程硬编码在代码中，固定执行顺序

**ReAct 模式**：
- Agent 通过 思考(Thought) → 行动(Action) → 观察(Observation) 循环
- 根据工具执行结果自主决定下一步
- 使用 sequential_thinking 工具进行深度分析

### 核心特性

1. **基于 LangChain**：利用成熟的 Agent 框架和 ReAct 模式
2. **智能分析**：深度理解数据库结构和业务语义
3. **自主生成**：Agent 自主决定生成流程和修正策略
4. **质量保证**：执行验证和反思优化
5. **MySQL 专注**：专门优化 MySQL 数据库

## 快速开始

### 安装

```bash
pip install -r requirements.txt
```

### 基础使用

```python
from semanticsql_agent.agent.data_generation_agent import DataGenerationAgent
from semanticsql_agent.config import Settings, DatabaseConfig

# 配置
settings = Settings()
db_config = DatabaseConfig(
    host="localhost",
    port=3306,
    database="mydb",
    username="root",
    password="password"
)

# 创建 Agent
agent = DataGenerationAgent(settings, db_config)

# 批量生成训练数据
result = agent.generate_training_data(
    count=100,
    output_file="nl2sql_training.json"
)
```

## API 结构

### 1. Agent API

#### DataGenerationAgent

主要的数据生成智能体类：

```python
class DataGenerationAgent(BaseAgent):
    """NL2SQL 训练数据生成智能体
    
    基于 LangChain 的 ReAct 模式，实现自主决策的训练数据生成流程。
    """
    
    def __init__(
        self,
        settings: Settings,
        db_config: DatabaseConfig
    ):
        """
        初始化数据生成 Agent
        
        Args:
            settings: 系统配置
            db_config: 数据库配置
        """
    
    def analyze_database(
        self,
        database_name: str
    ) -> Dict[str, Any]:
        """
        执行数据库分析阶段
        
        Args:
            database_name: 数据库名称
            
        Returns:
            Dict: 包含 success 状态和分析结果
        """
    
    def generate_training_data(
        self,
        count: int,
        output_file: str,
        database_name: Optional[str] = None
    ) -> TrainingDataResult:
        """
        批量生成训练数据
        
        Args:
            count: 生成数据条数
            output_file: 输出文件路径
            database_name: 可选，指定数据库名称
            
        Returns:
            TrainingDataResult: 生成结果统计
        """
```

### 2. 工具 API

所有工具都继承自 `langchain.tools.BaseTool`：

#### 分析工具

```python
# 数据库结构提取
class SchemaExtractionTool(BaseTool):
    name = "schema_extraction"
    description = "提取数据库的完整结构信息，包括表、列、索引、外键等"
    
    def _run(self, database_name: str) -> Dict[str, Any]:
        """返回数据库结构信息"""

# 领域分析
class DomainAnalysisTool(BaseAnalysisTool):
    name = "domain_analysis"
    description = "分析数据库的业务领域，识别主要业务场景和数据特征"
    
    def _run(self, memory: Dict[str, Any]) -> Dict[str, Any]:
        """返回领域分析结果"""

# 字段分类
class FieldClassificationTool(BaseAnalysisTool):
    name = "field_classification"
    description = "对数据库字段进行语义分类，识别字段的业务含义和用途"
    
    def _run(self, memory: Dict[str, Any]) -> Dict[str, Any]:
        """返回字段分类结果"""

# 列含义分析
class ColumnMeaningTool(BaseAnalysisTool):
    name = "column_meaning_analysis"
    description = "分析数据库列的业务含义，识别列的业务用途、数据模式和常见值"
    
    def _run(self, memory: Dict[str, Any]) -> Dict[str, Any]:
        """返回列含义分析结果"""

# 表含义分析
class TableMeaningTool(BaseAnalysisTool):
    name = "table_meaning_analysis"
    description = "分析数据库表的业务含义，识别表的业务用途、实体类型和表间关系"
    
    def _run(self, memory: Dict[str, Any]) -> Dict[str, Any]:
        """返回表含义分析结果"""

# 实体关系分析
class ERAnalysisTool(BaseAnalysisTool):
    name = "er_analysis"
    description = "分析数据库表之间的实体关系，识别外键关系和隐式关联"
    
    def _run(self, memory: Dict[str, Any], analyze_implicit: bool = True, depth: int = 2) -> Dict[str, Any]:
        """返回实体关系分析结果"""
```

#### 生成工具

```python
# 场景选择
class ScenarioTool(BaseTool):
    name = "scenario_tool"
    description = "从预定义的场景模板中选择一个适合当前数据库的业务场景"
    
    def _run(self, iteration: int = 0, memory: Dict[str, Any] = None) -> Dict[str, Any]:
        """从预定义模板选择一个场景"""

# 操作选择
class OperationSelectionTool(BaseTool):
    name = "operation_selection"
    description = "根据场景复杂度和业务需求选择合适的SQL操作组合"
    
    def _run(self, scenario: Dict[str, Any], memory: Dict[str, Any]) -> Dict[str, Any]:
        """选择SQL操作"""

# 问题生成
class QuestionGenerationTool(BaseTool):
    name = "question_generation"
    description = "根据场景和数据库结构生成自然语言问题"
    
    def _run(self, scenario: Dict[str, Any], operations: List[str], memory: Dict[str, Any]) -> Dict[str, Any]:
        """生成自然语言问题"""

# SQL生成
class SQLGenerationTool(BaseTool):
    name = "sql_generation"
    description = "根据自然语言问题和数据库结构生成对应的SQL查询"
    
    def _run(self, question: str, memory: Dict[str, Any], operations: List[str] = None, dialect: str = "mysql") -> Dict[str, Any]:
        """生成SQL查询"""
```

#### 验证和反思工具

```python
# SQL验证
class SQLValidationTool(BaseTool):
    name = "sql_validation"
    description = "验证SQL语句的语法正确性"
    
    def _run(self, sql: str, memory: Dict[str, Any]) -> Dict[str, Any]:
        """验证SQL语法"""

# SQL执行
class SQLExecutionTool(BaseTool):
    name = "sql_execution"
    description = "执行SQL查询并返回结果"
    
    def _run(self, sql: str, limit: int = 100) -> Dict[str, Any]:
        """执行SQL并返回结果"""

# SQL反思
class SQLReflectionTool(BaseTool):
    name = "sql_reflection"
    description = "分析SQL执行结果，识别问题来源并建议下一步行动"
    
    def _run(self, question: str, sql: str, execution_result: Dict[str, Any], memory: Dict[str, Any]) -> Dict[str, Any]:
        """评估生成质量并给出改进建议"""

# 深度思考
class SequentialThinkingTool(BaseTool):
    name = "sequential_thinking"
    description = "进行深度分析，制定问题解决策略"
    
    def _run(self, problem_description: str, context: Dict[str, Any], memory: Dict[str, Any]) -> Dict[str, Any]:
        """深度分析问题并制定解决策略"""
```

### 3. 数据模型

```python
# Agent执行步骤
@dataclass
class AgentStep:
    step_type: AgentStepType  # thought/action/observation
    content: str
    timestamp: datetime
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None

# 完整执行记录
@dataclass
class AgentExecution:
    task_id: str
    task: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    steps: List[AgentStep] = field(default_factory=list)
    final_result: Optional[Any] = None
    status: str = "running"  # running/completed/failed
    error: Optional[str] = None

# 查询场景
@dataclass
class QueryScenario:
    id: str
    category: str               # 场景类别
    business_purpose: str       # 业务目的
    complexity: DifficultyLevel # easy/medium/hard/expert
    applicable_tables: List[str]
    suggested_operations: List[SQLOperation]
    description: str

# 生成的示例
@dataclass
class GeneratedExample:
    id: str
    scenario_id: str
    question: str
    sql: str
    difficulty: DifficultyLevel
    validation_result: ValidationResult
    execution_result: Optional[SQLQueryResult] = None
    quality_score: float = 0.0
    reflection_notes: Optional[str] = None

# 训练数据结果
@dataclass
class TrainingDataResult:
    total_generated: int
    successful: int
    failed: int
    examples: List[GeneratedExample]
    generation_time: float
    statistics: Dict[str, Any]
```

### 4. 记忆管理

```python
class DatabaseAnalysisMemory(BaseMemory):
    """
    管理数据库分析结果的记忆
    基于 LangChain BaseMemory 实现
    """
    
    def update_analysis(self, analysis_type: str, result: Dict[str, Any]):
        """更新特定类型的分析结果"""
    
    def get_analysis(self, analysis_type: str) -> Dict[str, Any]:
        """获取特定类型的分析结果"""
    
    def has_complete_analysis(self) -> bool:
        """检查是否有完整的数据库分析"""
    
    def load_memory_variables(self, inputs: Dict) -> Dict:
        """加载相关的分析结果供Agent使用"""
    
    def save_context(self, inputs: Dict, outputs: Dict) -> None:
        """保存工具执行结果"""
```

### 5. 配置管理

```python
class Settings(BaseSettings):
    """全局配置（使用Pydantic BaseSettings）"""
    # LLM 配置
    llm_model: str = "Qwen3-14B"
    llm_base_url: str = "http://192.168.200.216:9991/v1"
    llm_api_key: str = "sk-dummy"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 4096
    
    # Agent 配置
    agent_max_iterations: int = 20
    agent_enable_reflection: bool = True
    agent_verbose: bool = True
    
    # 生成配置
    generation_batch_size: int = 10
    generation_timeout: int = 300
    
    class Config:
        env_file = ".env"
        env_prefix = "SEMANTICSQL_"

class DatabaseConfig(BaseModel):
    """数据库配置"""
    type: DatabaseType = DatabaseType.MYSQL
    host: str
    port: int = 3306
    database: str
    username: str
    password: str
    charset: str = "utf8mb4"
    
    def get_connection_string(self) -> str:
        """获取数据库连接字符串"""
```

## 执行流程

### 1. 数据库分析阶段（一次性执行）

```python
# Agent 自主执行以下分析
1. schema_extraction    → 提取数据库结构
2. domain_analysis     → 识别业务领域
3. field_classification → 字段语义分类
4. column_meaning_analysis → 列业务含义分析
5. table_meaning_analysis → 表业务含义分析
6. er_analysis         → 实体关系分析

# 结果自动保存到 memory 中
```

### 2. 数据生成循环

```python
for i in range(count):
    # 1. 选择场景
    scenario = scenario_tool(iteration=i)
    
    # 2. 选择操作
    operations = operation_selection(scenario)
    
    # 3. 生成问题
    question = question_generation(scenario, operations)
    
    # 4. 生成SQL
    sql = sql_generation(question)
    
    # 5. 验证执行
    validation = sql_validation(sql)
    execution = sql_execution(sql)
    
    # 6. 反思优化
    reflection = sql_reflection(question, sql, execution)
    
    # 7. 如需修正
    if reflection.needs_revision:
        # 使用 sequential_thinking 深度分析
        # 根据分析结果修正相应步骤
```

## 错误处理

所有 API 都使用统一的异常体系（定义在 `models/exceptions.py`）：

```python
try:
    result = agent.generate_training_data(count=100, output_file="data.json")
except ToolExecutionError as e:
    print(f"工具执行错误: {e.tool_name} - {e.message}")
except AgentExecutionError as e:
    print(f"Agent 执行错误: {e.step} - {e.reason}")
except DatabaseConnectionError as e:
    print(f"数据库连接错误: {e.host}:{e.port} - {e.message}")
except ConfigurationError as e:
    print(f"配置错误: {e.message}")
```

## 命令行接口

```bash
# 生成训练数据
python -m semanticsql_agent.cli generate \
    --count 100 \
    --output data.json \
    --database mydb

# 分析数据库
python -m semanticsql_agent.cli analyze \
    --database mydb

# 查看执行轨迹
python -m semanticsql_agent.cli trajectory \
    --latest

# 测试连接
python -m semanticsql_agent.cli test-connection
```

## 扩展开发

### 自定义工具

```python
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from models.exceptions import ToolExecutionError

class MyCustomToolInput(BaseModel):
    param1: str = Field(description="参数1")
    param2: int = Field(description="参数2")

class MyCustomTool(BaseTool):
    name = "my_custom_tool"
    description = "自定义工具描述"
    args_schema = MyCustomToolInput
    
    def _run(self, param1: str, param2: int) -> Dict[str, Any]:
        try:
            # 实现工具逻辑
            return {"success": True, "result": "data"}
        except Exception as e:
            raise ToolExecutionError(
                tool_name=self.name,
                reason=str(e)
            )
```

### 自定义回调

```python
from utils.callbacks import TrajectoryCallback

class MyCallback(TrajectoryCallback):
    def on_tool_start(self, serialized, input_str, **kwargs):
        super().on_tool_start(serialized, input_str, **kwargs)
        print(f"工具开始: {serialized['name']}")
    
    def on_tool_end(self, output, **kwargs):
        super().on_tool_end(output, **kwargs)
        print(f"工具结束: {output}")

# 使用自定义回调
agent = DataGenerationAgent(settings, db_config)
agent.extra_callbacks = [MyCallback()]
```

## 最佳实践

1. **数据库分析优先**：确保在生成数据前完成全面的数据库分析
2. **合理设置批次大小**：避免一次生成过多数据导致内存问题
3. **使用反思机制**：充分利用 sql_reflection 确保生成质量
4. **适度使用深度思考**：sequential_thinking 强大但耗时，适度使用
5. **监控执行过程**：使用回调和轨迹记录监控执行情况

## 性能优化

1. **连接池管理**：DatabaseManager 自动管理连接池
2. **批量处理**：合理设置 generation_batch_size
3. **内存管理**：定期清理大型分析结果
4. **并行执行**：独立的场景可以并行处理

## 版本兼容性

- Python: 3.8+
- LangChain: 0.3.0+
- SQLAlchemy: 1.4.0+
- Pydantic: 2.0.0+

---

更多详细信息请参考各模块的 API 文档。