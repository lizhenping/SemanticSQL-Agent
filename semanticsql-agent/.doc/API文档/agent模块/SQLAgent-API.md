# SQLAgent API 文档

继承自 BaseAgent 的 SQL 生成智能体，支持单次查询和批量训练数据生成。

## 类定义

```python
from typing import List, Dict, Any, Optional
from semanticsql_agent.agent.base_agent import BaseAgent
from semanticsql_agent.models import SQLQueryResult, TrainingDataResult

class SQLAgent(BaseAgent):
    """
    SQL 生成智能体
    
    支持两种模式：
    1. 查询模式：生成单个 SQL 查询
    2. 批量生成模式：生成大量训练数据
    
    Attributes:
        mode: 当前运行模式 ('query' 或 'batch')
        analysis_completed: 数据库分析是否完成
        current_scenario: 当前处理的场景
    """
```

## 构造函数

```python
def __init__(
    self,
    config: Settings,
    db_config: DatabaseConfig,
    callbacks: Optional[List[BaseCallbackHandler]] = None,
    mode: str = "query"
):
    """
    初始化 SQL Agent
    
    Args:
        config: 系统配置
        db_config: 数据库配置
        callbacks: 回调处理器列表
        mode: 运行模式，'query' 或 'batch'
    
    Example:
        ```python
        # 查询模式
        agent = SQLAgent(config, db_config, mode="query")
        
        # 批量生成模式
        agent = SQLAgent(
            config, 
            db_config, 
            mode="batch",
            callbacks=[ProgressCallback()]
        )
        ```
    """
```

## 核心方法

### query

```python
def query(self, question: str) -> SQLQueryResult:
    """
    单次 SQL 查询生成
    
    根据自然语言问题生成并执行 SQL 查询。
    
    Args:
        question: 自然语言问题
    
    Returns:
        SQLQueryResult: 包含问题、SQL、执行结果等信息
    
    Raises:
        DatabaseNotAnalyzedError: 数据库未分析
        SQLGenerationError: SQL 生成失败
        SQLExecutionError: SQL 执行失败
    
    Example:
        ```python
        result = agent.query("查询所有订单的总金额")
        print(f"SQL: {result.sql}")
        print(f"Result: {result.result}")
        print(f"Execution time: {result.execution_time}s")
        ```
    """
```

### generate_training_data

```python
def generate_training_data(
    self,
    count: int,
    output_file: str,
    scenarios_per_batch: int = 10,
    include_failed: bool = False
) -> TrainingDataResult:
    """
    批量生成训练数据
    
    生成指定数量的 NL2SQL 训练样本。
    
    Args:
        count: 生成数据条数
        output_file: 输出文件路径（支持 .json, .jsonl）
        scenarios_per_batch: 每批生成的场景数量
        include_failed: 是否包含验证失败的样本
    
    Returns:
        TrainingDataResult: 生成结果统计
    
    Raises:
        InvalidConfigError: 配置无效
        GenerationError: 生成过程失败
    
    Example:
        ```python
        result = agent.generate_training_data(
            count=1000,
            output_file="training_data.jsonl",
            scenarios_per_batch=20
        )
        
        print(f"Generated: {result.success_count}")
        print(f"Failed: {result.failed_count}")
        print(f"Total time: {result.total_time}s")
        ```
    """
```

### _analyze_database

```python
def _analyze_database(self) -> None:
    """
    内部方法：分析数据库
    
    执行完整的数据库分析流程，结果保存在记忆中。
    该方法在第一次 query 或 generate_training_data 时自动调用。


    """
```

## 模式特定方法

### 查询模式方法

```python
def explain_sql(self, sql: str) -> str:
    """
    解释 SQL 查询
    
    生成 SQL 查询的自然语言解释。
    
    Args:
        sql: SQL 查询语句
    
    Returns:
        str: 自然语言解释
    """

def optimize_sql(self, sql: str) -> str:
    """
    优化 SQL 查询
    
    分析并优化给定的 SQL 查询。
    
    Args:
        sql: 原始 SQL 查询
    
    Returns:
        str: 优化后的 SQL
    """
```

### 批量生成模式方法

```python
def set_scenario_filter(self, filter_func: Callable[[QueryScenario], bool]) -> None:
    """
    设置场景过滤器
    
    只生成满足条件的场景数据。
    
    Args:
        filter_func: 场景过滤函数
    
    Example:
        ```python
        # 只生成中等难度以上的场景
        agent.set_scenario_filter(
            lambda s: s.difficulty in ['medium', 'hard']
        )
        ```
    """

def get_generation_stats(self) -> Dict[str, Any]:
    """
    获取生成统计信息
    
    Returns:
        Dict[str, Any]: 包含各类统计数据
    """
```

## 实现的抽象方法

### get_system_prompt

```python
def get_system_prompt(self) -> str:
    """
    返回 SQL Agent 的系统提示词
    
    根据运行模式返回不同的提示词：
    - query 模式：专注于单个查询的准确性
    - batch 模式：强调批量生成的多样性和质量
    """
```

### _create_tools

```python
def _create_tools(self) -> List[BaseTool]:
    """
    创建 SQL Agent 的工具集
    
    包含的工具：
    - 分析工具：6个（含新增的列/表含义分析）
    - 生成工具：4个
    - 验证工具：2个
    - 反思工具：1个
    - 思考工具：1个
    """
```

## 数据模型

### SQLQueryResult

```python
@dataclass
class SQLQueryResult:
    """SQL 查询结果"""
    question: str              # 原始问题
    sql: str                  # 生成的 SQL
    result: Any               # 执行结果
    execution_time: float     # 执行时间（秒）
    row_count: int           # 结果行数
    error: Optional[str]     # 错误信息
    confidence: float        # 置信度 (0-1)
    metadata: Dict[str, Any] # 额外元数据
```

### TrainingDataResult

```python
@dataclass
class TrainingDataResult:
    """训练数据生成结果"""
    total_count: int         # 请求生成数量
    success_count: int       # 成功生成数量
    failed_count: int        # 失败数量
    output_file: str         # 输出文件路径
    total_time: float        # 总耗时（秒）
    scenarios_used: int      # 使用的场景数
    statistics: Dict[str, Any]  # 详细统计
```

## 使用示例

### 基本查询

```python
# 创建 Agent
agent = SQLAgent(config, db_config)

# 分析数据库（首次需要）
agent.analyze_database()

# 生成 SQL
result = agent.query("查询今年销售额最高的10个产品")

# 使用结果
if result.error:
    print(f"Error: {result.error}")
else:
    print(f"SQL: {result.sql}")
    print(f"Results: {result.result}")
```

### 批量生成

```python
# 创建批量生成 Agent
agent = SQLAgent(config, db_config, mode="batch")

# 自定义回调
class GenerationProgress(BaseCallbackHandler):
    def __init__(self):
        self.count = 0
    
    def on_tool_end(self, output, **kwargs):
        if "sql_generation" in str(output):
            self.count += 1
            if self.count % 10 == 0:
                print(f"Generated {self.count} examples...")

# 生成数据
result = agent.generate_training_data(
    count=500,
    output_file="nl2sql_train.jsonl",
    scenarios_per_batch=25
)

# 查看统计
stats = agent.get_generation_stats()
print(f"Difficulty distribution: {stats['difficulty_dist']}")
print(f"Table coverage: {stats['table_coverage']}")
```

### 高级用法

```python
# 1. 自定义场景生成
agent.set_scenario_filter(
    lambda s: s.category in ['sales', 'customer'] and s.difficulty != 'easy'
)

# 2. 使用不同的 LLM 参数
agent.llm.temperature = 0.5  # 更确定的输出

# 3. 访问记忆内容
memory = agent.get_memory_state()
schema = memory.get('schema_info')
domain = memory.get('domain_analysis')

# 4. 导出执行轨迹
trajectory = agent.agent_executor.memory.chat_memory.messages
with open("execution_trace.json", "w") as f:
    json.dump([msg.dict() for msg in trajectory], f)
```

## 配置优化

### 查询模式优化

```python
# 优化单次查询
agent = SQLAgent(
    config=Settings(
        llm_temperature=0.3,  # 低温度，更确定
        max_iterations=10,    # 减少迭代
        enable_reflection=False  # 关闭反思（提高速度）
    ),
    db_config=db_config,
    mode="query"
)
```

### 批量生成优化

```python
# 优化批量生成
agent = SQLAgent(
    config=Settings(
        llm_temperature=0.7,  # 较高温度，增加多样性
        max_iterations=20,    # 允许更多迭代
        enable_reflection=True,  # 启用反思
        enable_thinking_tool=True  # 启用深度思考
    ),
    db_config=db_config,
    mode="batch"
)
```

## 错误处理

```python
try:
    result = agent.query("复杂查询")
except DatabaseNotAnalyzedError:
    # 数据库未分析
    agent.analyze_database()
    result = agent.query("复杂查询")
except SQLGenerationError as e:
    print(f"生成失败: {e.message}")
    print(f"尝试的工具: {e.tool_trace}")
except SQLExecutionError as e:
    print(f"执行失败: {e.sql}")
    print(f"数据库错误: {e.db_error}")
```

## 性能考虑

1. **记忆管理**：数据库分析结果自动保存在记忆中
2. **批次大小**：合理设置 `scenarios_per_batch` 避免内存溢出
3. **错误处理**：合理处理各种异常情况

## 注意事项

1. 首次使用必须先调用 `analyze_database()`
2. 批量生成模式下会自动管理记忆防止溢出
3. 输出文件支持 `.json` 和 `.jsonl` 格式
4. 生成的 SQL 都会经过验证和执行测试
5. 支持中途恢复（通过轨迹文件）

---

相关文档：
- [BaseAgent API](./BaseAgent-API.md)
- [工具系统 API](../tools模块/)
- [数据模型](../models模块/数据模型.md)