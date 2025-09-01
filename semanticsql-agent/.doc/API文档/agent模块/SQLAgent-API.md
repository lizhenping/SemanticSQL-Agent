# SQLAgent API 文档

继承自 BaseAgent 的 SQL 查询智能体，根据自然语言问题生成 SQL。

## 类定义

```python
from typing import List, Dict, Any, Optional
from semanticsql_agent.agent.base_agent import BaseAgent
from semanticsql_agent.models import SQLQueryResult, TrainingDataResult

class SQLAgent(BaseAgent):
    """
    SQL 查询智能体
    
    根据自然语言问题生成对应的 SQL 查询。
    
    Attributes:
        analysis_completed: 数据库分析是否完成
        memory: LangChain 记忆组件
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
    初始化 SQL Agent
    
    Args:
        config: 系统配置
        db_config: 数据库配置
        callbacks: 回调处理器列表
    
    Example:
        ```python
        from semanticsql_agent.agent import SQLAgent
        from semanticsql_agent.config import Settings, DatabaseConfig
        
        config = Settings()
        db_config = DatabaseConfig(
            host="localhost",
            database="test_db",
            username="root",
            password="password"
        )
        
        agent = SQLAgent(config, db_config)
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



### _analyze_database

```python
def _analyze_database(self) -> None:
    """
    内部方法：分析数据库
    
    执行完整的数据库分析流程，结果保存在记忆中。
    该方法在第一次 query 或 generate_training_data 时自动调用。


    """
```

### generate_questions

```python
def generate_questions(self, count: int, output_file: str) -> Dict[str, Any]:
    """
    生成指定数量的问题-SQL对
    
    基于预定义场景模板，循环生成自然语言问题和对应的SQL。
    
    Args:
        count: 要生成的问题数量
        output_file: 输出文件路径（JSON/JSONL格式）
    
    Returns:
        Dict[str, Any]: 生成结果统计
        
    Return Format:
        ```python
        {
            "total_generated": 100,
            "successful": 95,
            "failed": 5,
            "scenarios_used": ["销售分析", "库存查询", "客户统计"],
            "time_elapsed": 120.5
        }
        ```
    
    Example:
        ```python
        result = agent.generate_questions(
            count=100,
            output_file="training_data.jsonl"
        )
        print(f"Generated: {result['successful']} questions")
        ```
    """
```

## 辅助方法

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

def validate_sql(self, sql: str) -> Dict[str, Any]:
    """
    验证 SQL 查询
    
    检查 SQL 语法和可执行性。
    
    Args:
        sql: SQL 查询语句
    
    Returns:
        Dict[str, Any]: 验证结果
    """
```

## 实现的抽象方法

### get_system_prompt

```python
def get_system_prompt(self) -> str:
    """
    返回 SQL Agent 的系统提示词
    
    提示词引导 Agent 自主执行任务，包括：
    - 使用 sequential_thinking 制定执行策略
    - 自主调用数据库分析工具
    - 根据任务类型决定执行流程
    - 使用 sql_reflection 评估生成质量
    - 必要时调用 sequential_thinking 分析问题并修正
    
    提示词专注于准确理解用户意图并生成正确的 SQL 查询。
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



### 高级用法

```python
# 1. 使用不同的 LLM 参数
agent.llm.temperature = 0.5  # 更确定的输出

# 2. 访问记忆内容
memory = agent.get_memory_state()
schema = memory.get('schema_info')
domain = memory.get('domain_analysis')

# 3. 导出执行轨迹
trajectory = agent.agent_executor.memory.chat_memory.messages
with open("execution_trace.json", "w") as f:
    json.dump([msg.dict() for msg in trajectory], f)
```

## 配置优化

### 查询优化

```python
# 优化查询性能
agent = SQLAgent(
    config=Settings(
        llm_temperature=0.3,  # 低温度，更确定
        max_iterations=10,    # 减少迭代
        enable_reflection=False  # 关闭反思（提高速度）
    ),
    db_config=db_config
)

# 或者启用反思以提高准确性
agent = SQLAgent(
    config=Settings(
        llm_temperature=0.5,
        max_iterations=15,
        enable_reflection=True,  # 启用反思
        enable_thinking_tool=True  # 启用深度思考
    ),
    db_config=db_config
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
2. **错误处理**：合理处理各种异常情况
3. **执行效率**：可通过关闭反思机制提高执行速度

## 注意事项

1. 首次查询会自动触发数据库分析
2. 数据库分析结果会缓存在记忆中
3. 生成的 SQL 都会经过验证
4. 支持通过轨迹文件追踪执行过程

---

相关文档：
- [BaseAgent API](./BaseAgent-API.md)
- [工具系统 API](../tools模块/)
- [数据模型](../models模块/数据模型.md)