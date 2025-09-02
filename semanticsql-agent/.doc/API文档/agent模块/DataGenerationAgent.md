# DataGenerationAgent API 文档

## 概述

`DataGenerationAgent` 是 SemanticSQL Agent 的核心组件，负责生成高质量的 NL2SQL 训练数据。基于 LangChain 的 ReAct 模式实现，支持自主决策和智能优化。

## 类定义

```python
class DataGenerationAgent(BaseAgent):
    """NL2SQL 训练数据生成智能体
    
    基于 LangChain 的 ReAct 模式，实现自主决策的训练数据生成流程。
    核心特性：
    - 使用 LangChain AgentExecutor 管理执行流程
    - 自定义 DatabaseAnalysisMemory 存储分析结果
    - 所有工具继承自 langchain.tools.BaseTool
    - 反思-修正循环确保数据质量
    """
```

## 构造函数

```python
def __init__(self, settings: Settings, db_config: DatabaseConfig)
```

### 参数

- `settings` (Settings): 系统配置对象
  - `llm_model`: LLM 模型名称
  - `llm_base_url`: LLM API 地址
  - `llm_temperature`: 生成温度
  - `agent_max_iterations`: 最大迭代次数
  - 其他配置参见 Settings 类

- `db_config` (DatabaseConfig): 数据库配置对象
  - `host`: 数据库主机
  - `port`: 数据库端口
  - `database`: 数据库名称
  - `username`: 用户名
  - `password`: 密码

### 初始化过程

1. 创建 LLM 客户端（ChatOpenAI）
2. 初始化数据库管理器
3. 注册所有分析、生成、验证和反思工具
4. 创建 DatabaseAnalysisMemory 实例
5. 构建 LangChain AgentExecutor

## 主要方法

### analyze_database

执行数据库全面分析，结果保存到记忆中供后续使用。

```python
def analyze_database(self, database_name: str) -> Dict[str, Any]
```

#### 参数

- `database_name` (str): 要分析的数据库名称

#### 返回值

```python
{
    "success": bool,        # 是否成功
    "error": Optional[str], # 错误信息（如果失败）
    "analysis": {           # 分析结果（如果成功）
        "schema_info": {...},
        "domain_info": {...},
        "field_classification": {...},
        "column_meanings": {...},
        "table_meanings": {...},
        "er_relations": {...}
    }
}
```

#### 执行流程

1. schema_extraction - 提取数据库结构
2. domain_analysis - 分析业务领域  
3. field_classification - 字段语义分类
4. column_meaning_analysis - 分析列含义
5. table_meaning_analysis - 分析表含义
6. er_analysis - 分析实体关系

#### 示例

```python
result = agent.analyze_database("shop_db")
if result["success"]:
    print(f"分析成功，识别到 {len(result['analysis']['schema_info']['tables'])} 个表")
else:
    print(f"分析失败: {result['error']}")
```

### generate_training_data

批量生成 NL2SQL 训练数据。

```python
def generate_training_data(
    self, 
    count: int, 
    output_file: str,
    database_name: Optional[str] = None
) -> TrainingDataResult:
```

#### 参数

- `count` (int): 要生成的训练数据条数
- `output_file` (str): 输出文件路径（支持 .json 和 .jsonl 格式）
- `database_name` (Optional[str]): 可选，指定数据库名称。如果未提供，使用配置的默认数据库

#### 返回值

```python
TrainingDataResult:
    total: int              # 总生成数
    successful: int         # 成功数
    failed: int            # 失败数
    output_file: str       # 输出文件路径
    examples: List[Dict[str, Any]]  # 生成的示例列表（字典格式）
```

#### 执行流程

对每个训练样本：
1. scenario_tool - 选择业务场景
2. operation_selection - 选择SQL操作
3. question_generation - 生成自然语言问题
4. sql_generation - 生成SQL查询
5. sql_validation - 验证SQL语法
6. sql_execution - 执行SQL测试
7. sql_reflection - 评估质量
8. 如需修正，使用 sequential_thinking 分析并重新执行相应步骤

#### 示例

```python
# 基础使用
result = agent.generate_training_data(
    count=100,
    output_file="training_data.json"
)

print(f"生成完成: {result.successful}/{result.total} 成功")
print(f"输出文件: {result.output_file}")

# 指定数据库
result = agent.generate_training_data(
    count=50,
    output_file="shop_data.jsonl",
    database_name="shop_db"
)
```

## 工具集成

DataGenerationAgent 集成了以下工具：

### 分析工具
- `schema_extraction`: 数据库结构提取
- `domain_analysis`: 业务领域分析
- `field_classification`: 字段语义分类
- `column_meaning_analysis`: 列业务含义分析
- `table_meaning_analysis`: 表业务含义分析
- `er_analysis`: 实体关系分析

### 生成工具
- `scenario_tool`: 场景选择
- `operation_selection`: SQL操作选择
- `question_generation`: 问题生成
- `sql_generation`: SQL生成

### 验证工具
- `sql_validation`: SQL语法验证
- `sql_execution`: SQL执行测试

### 反思工具
- `sql_reflection`: 质量评估和问题诊断
- `sequential_thinking`: 深度分析和策略制定

## 记忆管理

Agent 使用 `DatabaseAnalysisMemory` 管理分析结果：

```python
# 自动保存分析结果
memory.update_analysis("schema_info", schema_result)

# Agent可以访问所有历史分析
schema = memory.get_analysis("schema_info")
domain = memory.get_analysis("domain_info")
```

## 错误处理

```python
from models.exceptions import (
    AgentExecutionError,
    DatabaseConnectionError,
    ToolExecutionError
)

try:
    result = agent.generate_training_data(100, "data.json")
except AgentExecutionError as e:
    print(f"Agent执行错误: {e.step} - {e.reason}")
except DatabaseConnectionError as e:
    print(f"数据库连接失败: {e.message}")
except ToolExecutionError as e:
    print(f"工具执行错误: {e.tool_name} - {e.message}")
```

## 配置选项

通过 Settings 类配置 Agent 行为：

```python
settings = Settings(
    # LLM 配置
    llm_temperature=0.7,      # 控制生成的创造性
    llm_max_tokens=20000,     # 最大token数
    
    # Agent 配置
    max_iterations=20,        # 最大迭代次数
    enable_reflection=True,   # 启用反思机制
    verbose=True,            # 详细输出
    
    # 批处理配置
    batch_size=10,           # 批次大小
    concurrent_workers=5      # 并发工作线程
)
```

## 最佳实践

1. **数据库分析**：在生成数据前先执行 `analyze_database`
2. **批量大小**：合理设置生成数量，建议每批不超过 100 条
3. **输出格式**：使用 .jsonl 格式便于流式处理大量数据
4. **错误处理**：实现完善的错误处理和重试机制
5. **监控进度**：使用回调监控生成进度

## 扩展和自定义

### 添加自定义工具

```python
class CustomTool(BaseTool):
    name = "custom_tool"
    description = "自定义工具"
    
    def _run(self, **kwargs):
        # 实现自定义逻辑
        return {"result": "success"}

# 在初始化时添加
agent = DataGenerationAgent(settings, db_config)
agent.tools.append(CustomTool())
```

### 自定义回调

```python
from langchain.callbacks import BaseCallbackHandler

class ProgressCallback(BaseCallbackHandler):
    def on_tool_start(self, serialized, input_str, **kwargs):
        print(f"执行工具: {serialized['name']}")

agent.agent_executor.callbacks.append(ProgressCallback())
```

## 性能考虑

1. **内存使用**：大量生成时注意内存占用
2. **数据库连接**：使用连接池管理连接
3. **LLM 调用**：合理设置温度和 token 限制
4. **并行处理**：可以并行处理独立的场景

## 版本历史

- v1.0.0: 初始版本，基于 LangChain 0.3.0
- v1.1.0: 添加 column_meaning 和 table_meaning 分析工具
- v1.2.0: 优化反思-修正机制，提高生成质量