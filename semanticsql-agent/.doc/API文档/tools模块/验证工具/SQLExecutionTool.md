# SQLExecutionTool API 文档

SQL 执行测试工具，执行 SQL 并返回结果。

## 类定义

```python
from langchain.tools import BaseTool
from typing import Dict, Any, List
from semanticsql_agent.tools.validation_tools import SQLExecutionTool

class SQLExecutionTool(BaseTool):
    """
    SQL 执行工具
    
    在数据库中执行 SQL 查询并返回结果。
    
    Attributes:
        name: "sql_execution"
        description: "执行 SQL 查询并返回结果"
    """
```

## 构造函数

```python
def __init__(self, db_config: DatabaseConfig):
    """
    初始化 SQL 执行工具
    
    Args:
        db_config: 数据库配置
    """
```

## 核心方法

### _run

```python
def _run(
    self,
    sql: str,
    limit: int = 10,
    timeout: int = 30
) -> Dict[str, Any]:
    """
    执行 SQL 查询
    
    Args:
        sql: 要执行的 SQL 语句
        limit: 返回结果行数限制
        timeout: 执行超时时间（秒）
    
    Returns:
        Dict[str, Any]: 执行结果
    
    Return Format:
        ```python
        {
            "success": true,
            "data": [
                {"order_id": 1, "total": 99.99, "status": "completed"},
                {"order_id": 2, "total": 149.99, "status": "pending"}
            ],
            "row_count": 2,
            "column_names": ["order_id", "total", "status"],
            "execution_time": 0.123,
            "affected_rows": 0,  # for INSERT/UPDATE/DELETE
            "error": null
        }
        ```
    """
```

## 执行特性

### 1. 安全执行
- 自动添加 LIMIT 防止大结果集
- 超时保护
- 只读查询（默认）

### 2. 结果处理
- 自动转换数据类型
- 处理 NULL 值
- 格式化日期时间

### 3. 性能监控
- 记录执行时间
- 返回影响行数
- 查询计划信息（可选）

## 使用示例

### 基本查询
```python
# 创建工具
tool = SQLExecutionTool(db_config=db_config)

# 执行查询
result = tool.run({
    "sql": "SELECT COUNT(*) as total FROM orders WHERE status = 'completed'",
    "limit": 1
})

if result["success"]:
    total = result["data"][0]["total"]
    print(f"Total completed orders: {total}")
    print(f"Execution time: {result['execution_time']}s")
```

### 复杂查询
```python
# 执行聚合查询
sql = """
SELECT 
    DATE(created_at) as order_date,
    COUNT(*) as order_count,
    SUM(total_amount) as daily_total
FROM orders
WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
GROUP BY DATE(created_at)
ORDER BY order_date DESC
"""

result = tool.run({
    "sql": sql,
    "limit": 7,
    "timeout": 10
})

# 处理结果
for row in result["data"]:
    print(f"{row['order_date']}: {row['order_count']} orders, ${row['daily_total']}")
```

## 错误处理

```python
# 处理执行错误
result = tool.run({
    "sql": "SELECT * FROM invalid_table"
})

if not result["success"]:
    print(f"Execution failed: {result['error']}")
    # 错误类型可能包括：
    # - Table doesn't exist
    # - Column not found
    # - Syntax error
    # - Permission denied
```

## 高级功能

### 查询解释
```python
def explain_query(self, sql: str) -> Dict[str, Any]:
    """
    获取查询执行计划
    
    Returns:
        Dict containing query plan information
    """
```

### 事务支持
```python
# 注意：默认只支持只读查询
# 如需写操作，需要特殊配置
```

## 安全考虑

1. **SQL 注入防护**：参数化查询
2. **权限控制**：只读账户
3. **资源限制**：超时和结果集大小限制
4. **审计日志**：记录所有执行的查询

## 注意事项

1. 默认限制返回行数
2. 长时间查询会被超时中断
3. 大数据集需要分页处理
4. 建议使用只读数据库账户

---

相关文档：
- [SQLValidationTool](./SQLValidationTool.md)
- [DatabaseManager](../../utils模块/DatabaseManager-API.md)