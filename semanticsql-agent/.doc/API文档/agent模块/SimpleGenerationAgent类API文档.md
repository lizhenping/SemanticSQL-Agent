# SimpleGenerationAgent 类 API 文档

## 概述
`SimpleGenerationAgent` 是简化版的训练数据生成代理，专门用于绕过复杂的 schema 传递问题，直接基于已知的表信息生成 NL2SQL 训练数据。

## 类定义
```python
class SimpleGenerationAgent(BaseAgent):
    """简化的训练数据生成Agent"""
```

## 构造函数

### `__init__(self, settings: Settings, db_config: DatabaseConfig)`
初始化简化的生成代理。

**参数：**
- `settings` (Settings): 系统配置对象
- `db_config` (DatabaseConfig): 数据库配置对象

**初始化内容：**
- 数据库管理器
- 预定义的表结构信息
- 训练数据存储列表

**预定义表信息：**
```python
known_tables = {
    "aid_info": ["id", "date", "amount", "total_amount", "aid_type", "memo", "sum", "sum_tmp"],
    "sjckc_zyccq_htjcxx": ["htbzh", "htmc", "htlb", "htlx", "htzje", "htqdrq"],
    "sjckc_zyccq_htdtxx": ["htbzh", "jgrq", "tqsj", "ljzfjf", "cgsl"],
    "sjckc_zyccq_czdwxx": ["jgbzh", "jgmc", "czdwxz"],
    "sjckc_zyccq_zlwt": ["zlwtbs", "htbzh", "zlwtbh", "wtmc", "fxsj"]
}
```

## 重写方法

### `_initialize_tools(self) -> None`
初始化简化的工具集。

**注册的工具：**
1. **sql_generation** - SQL 生成工具
   - 用途：根据问题生成 SQL 查询
   
2. **sql_execution** - SQL 执行工具
   - 用途：执行 SQL 查询并获取结果

### `get_system_prompt(self) -> str`
获取简化的系统提示词。

**提示词特点：**
- 明确的工具使用格式
- 预定义的表结构信息
- 简化的 schema 传递方式
- 清晰的任务指导

## 公共方法

### `generate_training_pairs(self, count: int = 10) -> List[Dict[str, Any]]`
生成指定数量的训练数据对。

**参数：**
- `count` (int): 要生成的数据对数量

**返回：**
- `List[Dict[str, Any]]`: 生成的训练数据列表

**数据格式：**
```python
{
    "question": "自然语言问题",
    "sql": "对应的SQL查询",
    "schema": "使用的表结构信息"
}
```

**执行流程：**
1. 循环生成指定数量的数据对
2. 每次使用不同的问题类型
3. 提取生成的 SQL
4. 保存到训练数据列表

## 特性与优势

### 1. 简化的架构
- 只使用必要的工具
- 避免复杂的 schema 对象传递
- 减少工具调用的复杂性

### 2. 预定义表信息
- 无需动态提取 schema
- 避免序列化问题
- 提高生成效率

### 3. 明确的格式要求
- 工具输入使用简单字符串
- 避免复杂的 JSON 结构
- 减少格式错误

## 使用示例

### 基本使用
```python
# 创建配置
settings = Settings()
db_config = DatabaseConfig(
    host="localhost",
    port=3306,
    database="testdb",
    username="user",
    password="password"
)

# 创建代理
agent = SimpleGenerationAgent(settings, db_config)

# 生成训练数据
training_data = agent.generate_training_pairs(count=20)

# 查看生成的数据
for item in training_data:
    print(f"问题: {item['question']}")
    print(f"SQL: {item['sql']}")
    print(f"Schema: {item['schema']}")
    print("-" * 50)
```

### 保存训练数据
```python
# 生成数据
training_data = agent.generate_training_pairs(count=50)

# 保存为 JSONL 格式
import json

with open("training_data.jsonl", "w", encoding="utf-8") as f:
    for item in training_data:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")

print(f"已保存 {len(training_data)} 条训练数据")
```

## 生成的问题类型

代理会生成多种类型的问题：

### 1. 统计查询
- "统计aid_info表中的总记录数"
- "计算合同总金额的平均值"
- "查询每种援助类型的数量"

### 2. 条件过滤
- "查找2023年之后的所有合同"
- "查询金额大于10000的援助记录"
- "获取特定机构的所有信息"

### 3. 排序和限制
- "查询金额最高的前10条记录"
- "按日期降序显示最新的合同"
- "获取最近添加的5个质量问题"

### 4. 多表关联
- "查询合同及其对应的质量问题"
- "显示合同和承租单位的关联信息"
- "统计每个合同的问题数量"

## 工具调用格式

代理使用特定的格式调用工具：

```
Thought: 需要生成一个查询aid_info表总记录数的SQL
Action: sql_generation
Action Input: {"question": "统计aid_info表中的总记录数", "schema_info": "aid_info表包含id,date,amount等字段"}
```

## 错误处理

### 常见错误
1. **工具调用格式错误**
   - 确保 JSON 格式正确
   - 检查必需参数

2. **数据库连接失败**
   - 验证连接配置
   - 检查网络和权限

3. **生成失败**
   - 重试机制
   - 跳过错误继续生成

## 最佳实践

1. **批量生成**
   - 分批生成避免长时间运行
   - 定期保存中间结果

2. **质量控制**
   - 人工抽查生成质量
   - 验证 SQL 的正确性
   - 确保问题的多样性

3. **扩展表信息**
   - 可以修改 `known_tables` 添加新表
   - 保持字段信息的准确性

4. **监控生成过程**
   - 使用日志跟踪生成进度
   - 记录失败的生成尝试

## 与标准 DataGenerationAgent 的区别

| 特性 | SimpleGenerationAgent | DataGenerationAgent |
|-----|---------------------|-------------------|
| 架构复杂度 | 简单 | 复杂 |
| 工具数量 | 2个 | 8+个 |
| Schema处理 | 预定义字符串 | 动态对象 |
| 生成流程 | 直接生成 | 多阶段生成 |
| 适用场景 | 已知数据库结构 | 通用场景 |

## 注意事项

1. 仅适用于已知表结构的场景
2. 需要手动更新表信息
3. 生成的多样性可能有限
4. 不支持动态 schema 发现
5. 适合快速原型和测试