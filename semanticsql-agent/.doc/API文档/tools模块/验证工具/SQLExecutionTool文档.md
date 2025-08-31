# SQLExecutionTool API 文档

## 概述
`SQLExecutionTool` 是用于执行 SQL 查询并返回结果的工具。支持查询执行、结果验证、执行计划分析等功能。

## 类定义
```python
class SQLExecutionTool(BaseTool):
    """SQL执行测试工具"""
```

## 构造函数
```python
def __init__(self, db_manager: DatabaseManager)
```

**参数：**
- `db_manager` (DatabaseManager): 数据库管理器实例

**默认配置：**
- `sql_execution_timeout`: 30秒
- `max_result_rows`: 1000行

## 工具属性

- **名称**: `execute_sql`
- **类别**: `validation`
- **描述**: 执行SQL查询并返回结果

## 参数定义

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|-------|------|------|--------|------|
| sql | string | 是 | - | 要执行的SQL查询 |
| timeout | integer | 否 | 30 | 执行超时时间（秒） |
| max_rows | integer | 否 | 1000 | 最大返回行数 |
| dry_run | boolean | 否 | False | 是否只进行模拟执行 |
| explain | boolean | 否 | False | 是否返回执行计划 |

## 执行方法

### `_execute(...) -> Dict[str, Any]`

**返回数据结构：**
```python
{
    "success": bool,              # 执行是否成功
    "rows_affected": int,         # 影响的行数
    "column_names": List[str],    # 列名列表
    "rows": List[List[Any]],     # 结果数据
    "row_count": int,            # 返回的行数
    "execution_time_ms": int,    # 执行时间（毫秒）
    "truncated": bool,           # 结果是否被截断
    "explain_plan": str,         # 执行计划（如果请求）
    "warnings": List[str]        # 执行警告
}
```

## 内部方法

### `_prepare_sql(sql: str, max_rows: int) -> str`
准备 SQL 语句，添加必要的限制。

**功能：**
- 去除危险操作
- 添加行数限制
- 格式化查询

### `_execute_query(sql: str, timeout: int) -> Tuple[List[Dict], float]`
执行查询并返回结果。

**返回：**
- 结果列表
- 执行时间

### `_get_explain_plan(sql: str) -> str`
获取查询执行计划。

**支持的数据库：**
- MySQL: `EXPLAIN`
- PostgreSQL: `EXPLAIN ANALYZE`
- SQLite: `EXPLAIN QUERY PLAN`

### `_format_results(results: List[Dict], max_rows: int) -> Dict[str, Any]`
格式化查询结果。

## 使用示例

### 基本查询执行
```python
# 创建工具实例
tool = SQLExecutionTool(db_manager)

# 执行简单查询
result = tool.run(
    sql="SELECT id, name, email FROM users LIMIT 10"
)

if result["success"]:
    data = result["data"]
    print(f"返回 {data['row_count']} 行")
    print(f"列: {data['column_names']}")
    
    # 打印结果
    for row in data["rows"]:
        print(row)
    
    print(f"执行时间: {data['execution_time_ms']}ms")
```

### 带执行计划的查询
```python
# 执行复杂查询并获取执行计划
result = tool.run(
    sql="""
    SELECT u.name, COUNT(o.id) as order_count
    FROM users u
    LEFT JOIN orders o ON u.id = o.user_id
    GROUP BY u.id, u.name
    ORDER BY order_count DESC
    """,
    explain=True,
    max_rows=50
)

if result["success"]:
    data = result["data"]
    
    # 查看执行计划
    print("执行计划:")
    print(data["explain_plan"])
    
    # 查看性能警告
    if data["warnings"]:
        print("性能警告:")
        for warning in data["warnings"]:
            print(f"- {warning}")
```

### 模拟执行（Dry Run）
```python
# 验证 SQL 但不实际执行
result = tool.run(
    sql="DELETE FROM users WHERE created_at < '2020-01-01'",
    dry_run=True
)

if result["success"]:
    print("SQL 语法正确，可以安全执行")
else:
    print(f"SQL 存在问题: {result['error']}")
```

### 超时控制
```python
# 设置较短的超时时间
result = tool.run(
    sql="SELECT * FROM large_table WHERE complex_condition",
    timeout=5,  # 5秒超时
    max_rows=100
)

if not result["success"] and "timeout" in result.get("error", ""):
    print("查询执行超时，请优化查询")
```

## 安全特性

### 1. 查询限制
- 自动添加 LIMIT 子句
- 防止返回过多数据
- 保护数据库性能

### 2. 危险操作检测
- 禁止 DROP、TRUNCATE 等操作
- 限制 UPDATE、DELETE 范围
- 警告无 WHERE 条件的操作

### 3. 超时保护
- 防止长时间运行的查询
- 可配置超时时间
- 自动终止超时查询

## 性能监控

### 执行时间统计
```python
{
    "execution_time_ms": 125,     # 总执行时间
    "query_time_ms": 120,         # 查询时间
    "fetch_time_ms": 5            # 结果获取时间
}
```

### 性能警告示例
- "查询未使用索引"
- "全表扫描检测"
- "结果集过大"
- "复杂度过高"

## 结果格式化

### 列名和数据分离
```python
{
    "column_names": ["id", "name", "email"],
    "rows": [
        [1, "张三", "zhang@example.com"],
        [2, "李四", "li@example.com"]
    ]
}
```

### 数据类型处理
- 日期时间：转换为 ISO 格式字符串
- 二进制数据：转换为 Base64
- NULL 值：保持为 None
- 大数值：保持精度

## 错误处理

### 常见错误类型
1. **语法错误**
   - 返回详细的错误信息
   - 包含错误位置

2. **权限错误**
   - 提示缺少的权限
   - 建议解决方案

3. **连接错误**
   - 数据库连接失败
   - 网络超时

4. **资源限制**
   - 内存不足
   - 结果集过大

## 最佳实践

1. **使用参数化查询**
   - 避免 SQL 注入
   - 提高查询缓存命中率

2. **合理设置限制**
   - 根据需求设置 max_rows
   - 避免返回不必要的数据

3. **监控执行时间**
   - 识别慢查询
   - 优化性能瓶颈

4. **使用执行计划**
   - 理解查询执行过程
   - 发现优化机会

## 注意事项

1. 生产环境慎用 DELETE/UPDATE
2. 大表查询注意添加条件
3. 避免笛卡尔积
4. 定期检查慢查询日志
5. 注意数据库连接池限制