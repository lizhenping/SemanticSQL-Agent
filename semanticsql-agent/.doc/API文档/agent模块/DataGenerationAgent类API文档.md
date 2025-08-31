# DataGenerationAgent 类 API 文档

## 概述
`DataGenerationAgent` 是用于生成 SQL 训练数据的智能代理，继承自 `BaseAgent`。它通过自动化的方式生成自然语言查询和对应的 SQL 语句对，用于训练或评估 NL2SQL 模型。

## 类定义
```python
class DataGenerationAgent(BaseAgent):
    """用于生成 SQL 训练数据的智能代理"""
```

## 构造函数

### `__init__(self, settings: Settings, db_config: DatabaseConfig)`
初始化数据生成代理。

**参数：**
- `settings` (Settings): 系统配置对象
- `db_config` (DatabaseConfig): 数据库配置对象

**初始化内容：**
- 数据库管理器
- 生成参数配置
- 已生成的查询集合（用于去重）
- 生成统计信息

## 重写方法

### `_initialize_tools(self) -> None`
初始化工具集。

**注册的工具：**
1. **analyze_er** - ER 分析工具
   - 用途：分析数据库实体关系
   
2. **analyze_domain** - 领域分析工具
   - 用途：分析数据库业务领域
   
3. **classify_fields** - 字段分类工具
   - 用途：对数据库字段进行分类
   
4. **generate_scenario** - 场景生成工具
   - 用途：生成查询场景和操作类型
   
5. **select_operation** - 操作选择工具
   - 用途：选择合适的 SQL 操作类型
   
6. **generate_question** - 问题生成工具
   - 用途：生成自然语言查询问题
   
7. **generate_sql** - SQL 生成工具
   - 用途：生成对应的 SQL 查询
   
8. **validate_sql** - SQL 验证工具
   - 用途：验证生成的 SQL 正确性
   
9. **reflect_sql** - SQL 反思工具（如果启用）
   - 用途：对生成的 SQL 进行反思和优化

### `get_system_prompt(self) -> str`
获取系统提示词。

**返回：**
系统提示包含：
- 角色定义（SQL 训练数据生成专家）
- 可用工具详细说明
- 数据生成工作流程
- 质量要求和多样性要求

### `_execute_action(self, action: str, action_input: Optional[Dict]) -> Any`
执行特定动作（重写以支持批量生成）。

**特殊处理：**
- **Finish** 动作：保存当前生成的数据对
- **Cancel** 动作：跳过当前生成
- 其他动作：调用父类方法

## 公共方法

### `generate_training_data(self, count: int, output_file: str) -> Dict[str, Any]`
生成指定数量的训练数据。

**参数：**
- `count` (int): 要生成的数据对数量
- `output_file` (str): 输出文件路径

**返回：**
- `Dict[str, Any]`: 生成结果统计，包含：
  - `total_requested`: 请求生成数量
  - `total_generated`: 实际生成数量
  - `success_rate`: 成功率
  - `unique_queries`: 唯一查询数量
  - `output_file`: 输出文件路径
  - `error`: 错误信息（如果有）

**执行流程：**
1. 初始化生成统计
2. 循环生成指定数量的数据对
3. 执行生成任务
4. 提取有效数据
5. 保存到文件

### `close(self) -> None`
关闭数据库连接。

## 内部方法

### `_extract_training_data_from_execution(self, execution) -> List[Dict[str, Any]]`
从执行记录中提取训练数据。

**参数：**
- `execution`: 执行记录对象

**返回：**
- `List[Dict[str, Any]]`: 提取的训练数据列表

**提取逻辑：**
1. 查找问题生成和 SQL 生成步骤
2. 验证数据完整性
3. 检查查询唯一性
4. 格式化输出数据

### `_save_training_data(self, data: List[Dict[str, Any]], output_file: str) -> None`
保存训练数据到文件。

**参数：**
- `data` (List[Dict[str, Any]]): 训练数据列表
- `output_file` (str): 输出文件路径

**文件格式：**
- JSON Lines 格式（每行一个 JSON 对象）
- UTF-8 编码

## 生成的数据格式

每个训练数据对包含：
```json
{
    "natural_language": "查询2023年第一季度销售额超过10万的产品",
    "sql": "SELECT product_name, SUM(amount) as total_sales FROM sales WHERE date >= '2023-01-01' AND date <= '2023-03-31' GROUP BY product_id, product_name HAVING SUM(amount) > 100000",
    "metadata": {
        "scenario": "销售分析",
        "operation": "聚合查询",
        "tables": ["sales"],
        "difficulty": "medium"
    }
}
```

## 使用示例

```python
from config.settings import Settings
from config.database import DatabaseConfig

# 配置
settings = Settings()
settings.enable_reflection = True  # 启用反思以提高质量

db_config = DatabaseConfig(
    host="localhost",
    port=3306,
    user="root",
    password="password",
    database="business_db"
)

# 创建代理
agent = DataGenerationAgent(settings, db_config)

try:
    # 生成 100 条训练数据
    result = agent.generate_training_data(
        count=100,
        output_file="training_data.jsonl"
    )
    
    print(f"生成成功: {result['total_generated']} 条")
    print(f"成功率: {result['success_rate']}%")
    print(f"唯一查询: {result['unique_queries']} 条")
    
finally:
    agent.close()
```

## 生成策略

1. **多样性保证**
   - 自动去重，避免生成相同的查询
   - 覆盖不同的操作类型（查询、聚合、连接等）
   - 涵盖不同的业务场景

2. **质量控制**
   - SQL 语法验证
   - 可选的反思优化
   - 自然语言与 SQL 的对应性检查

3. **效率优化**
   - 批量生成
   - 失败重试机制
   - 进度跟踪

## 配置选项

通过 `Settings` 对象可配置：
- `enable_reflection`: 启用 SQL 反思优化
- `max_retries`: 单个数据对的最大重试次数
- `batch_size`: 批量处理大小

## 错误处理

- 生成失败：记录错误并继续下一个
- 数据库错误：返回错误信息
- 文件写入错误：抛出异常
- 超时：通过最大步骤数限制

## 注意事项

1. 生成过程可能耗时较长，建议分批生成
2. 输出文件会追加写入，不会覆盖
3. 确保有足够的磁盘空间
4. 生成质量依赖于数据库结构的复杂度
5. 建议定期检查生成数据的质量