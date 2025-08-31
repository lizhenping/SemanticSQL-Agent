# SmartSQLAgent 类 API 文档

## 概述
`SmartSQLAgent` 是一个智能 SQL 生成代理，继承自 `BaseAgent`。它使用 ReAct 模式来理解自然语言查询并生成相应的 SQL 查询语句，专注于数据库分析和查询生成。

## 类定义
```python
class SmartSQLAgent(BaseAgent):
    """使用 ReAct 模式进行数据库分析的智能 SQL 代理"""
```

## 构造函数

### `__init__(self, settings: Settings, db_config: DatabaseConfig)`
初始化 SmartSQL 代理。

**参数：**
- `settings` (Settings): 系统配置对象
- `db_config` (DatabaseConfig): 数据库配置对象

**初始化内容：**
- 数据库管理器（DatabaseManager）
- 当前数据库信息
- 当前模式信息
- 分析结果存储

**异常：**
- 如果数据库连接初始化失败，抛出异常

## 重写方法

### `_initialize_tools(self) -> None`
初始化智能体工具集。

**注册的工具：**
1. **extract_schema** - 模式提取工具
   - 用途：提取数据库表结构和模式信息
   
2. **generate_sql** - SQL 生成工具
   - 用途：基于自然语言生成 SQL 查询
   
3. **validate_sql** - SQL 验证工具
   - 用途：验证生成的 SQL 语法正确性
   
4. **execute_sql** - SQL 执行工具
   - 用途：执行 SQL 查询并返回结果
   
5. **sequential_thinking** - 顺序思考工具（如果启用）
   - 用途：进行分步推理和思考

### `get_system_prompt(self) -> str`
获取系统提示词。

**返回：**
- 包含以下内容的系统提示：
  - 角色定义（数据库分析专家）
  - 可用工具列表及其用途
  - 工作流程指导
  - 输出格式要求
  - 数据库连接信息

### `_generate_final_result(self) -> Any`
生成最终执行结果。

**返回：**
- 如果有 SQL 查询结果和执行结果，返回 `SQLQueryResult` 对象
- 否则返回最后一步的输出或错误信息

## 公共方法

### `query(self, natural_language_query: str) -> SQLQueryResult`
执行自然语言查询。

**参数：**
- `natural_language_query` (str): 自然语言查询语句

**返回：**
- `SQLQueryResult`: 查询结果对象，包含：
  - `success`: 执行是否成功
  - `question`: 原始自然语言查询
  - `sql`: 生成的 SQL 语句（可选）
  - `answer`: 自然语言答案（可选）
  - `data`: 查询结果数据列表
  - `row_count`: 返回的行数
  - `execution_time`: 执行时间（秒）
  - `error`: 错误信息（可选）
  - `steps`: 执行步骤数

**执行流程：**
1. 使用 `new_task()` 开始新任务
2. 通过 ReAct 循环生成并执行 SQL
3. 格式化返回结果

### `close(self) -> None`
关闭数据库连接。

## 内部方法

### `_generate_answer(self, sql_result: Dict, execution_result: Dict) -> str`
生成自然语言答案。

**参数：**
- `sql_result` (Dict): SQL 生成结果
- `execution_result` (Dict): SQL 执行结果

**返回：**
- `str`: 格式化的自然语言答案

## 使用示例

```python
from config.settings import Settings
from config.database import DatabaseConfig

# 配置数据库连接
db_config = DatabaseConfig(
    host="localhost",
    port=3306,
    user="root",
    password="password",
    database="sales_db"
)

# 创建设置
settings = Settings()

# 创建智能 SQL 代理
agent = SmartSQLAgent(settings, db_config)

try:
    # 执行自然语言查询
    result = agent.query("查询上个月销售额最高的前10个产品")

if result.success:
    print(f"生成的SQL: {result.sql}")
    print(f"查询结果: {result.data}")
    print(f"答案: {result.answer}")
    print(f"返回行数: {result.row_count}")
    print(f"执行时间: {result.execution_time}秒")
    else:
        print(f"错误: {result.error}")
        
finally:
    # 关闭连接
    agent.close()
```

## 工具调用流程

典型的查询执行流程：

1. **模式提取**
   ```
   Tool: extract_schema
   Action: 获取数据库表结构信息
   ```

2. **SQL 生成**
   ```
   Tool: generate_sql
   Input: 自然语言查询 + 模式信息
   Output: SQL 查询语句
   ```

3. **SQL 验证**
   ```
   Tool: validate_sql
   Input: 生成的 SQL
   Output: 语法验证结果
   ```

4. **SQL 执行**
   ```
   Tool: execute_sql
   Input: 验证通过的 SQL
   Output: 查询结果
   ```

## 配置选项

通过 `Settings` 对象可以配置：
- `enable_thinking`: 是否启用思考工具
- `max_steps`: 最大执行步骤数
- `llm_model`: 使用的语言模型
- `llm_temperature`: 生成温度

## 错误处理

- 数据库连接错误：在初始化时抛出异常
- SQL 语法错误：通过验证工具捕获
- 执行错误：返回包含错误信息的结果对象
- 超时错误：通过最大步骤数限制

## 注意事项

1. 必须确保数据库连接配置正确
2. 代理会自动管理数据库连接
3. 使用完毕后应调用 `close()` 方法
4. 支持复杂的多表查询和聚合操作
5. 生成的 SQL 会经过验证确保安全性