# SQLValidationTool API 文档

SQL 验证工具，检查生成的 SQL 语法和可执行性。

## 类定义

```python
from langchain.tools import BaseTool
from typing import Dict, Any
from semanticsql_agent.tools.validation_tools import SQLValidationTool

class SQLValidationTool(BaseTool):
    """
    SQL 验证工具
    
    验证 SQL 语句的语法正确性和在目标数据库中的可执行性。
    
    Attributes:
        name: "sql_validation"
        description: "验证 SQL 查询的语法和可执行性"
    """
```

## 构造函数

```python
def __init__(self, db_config: DatabaseConfig):
    """
    初始化 SQL 验证工具
    
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
    memory: Dict[str, Any]
) -> Dict[str, Any]:
    """
    验证 SQL 查询
    
    Args:
        sql: 要验证的 SQL 语句
        memory: 包含数据库分析结果的记忆（使用其中的schema_info）
    
    Returns:
        Dict[str, Any]: 验证结果
    
    Return Format:
        ```python
        {
            "valid": true,
            "syntax_check": {
                "passed": true,
                "message": "SQL syntax is valid"
            },
            "semantic_check": {
                "passed": true,
                "tables_exist": true,
                "columns_exist": true,
                "invalid_references": []
            },
            "warnings": [
                "Column 'orders.created_date' might need index for better performance"
            ],
            "optimizations": [
                "Consider adding LIMIT clause for large result sets"
            ]
        }
        ```
    """
```

## 验证类型

### 1. 语法验证
- SQL 语法正确性
- 关键字使用
- 引号匹配

### 2. 语义验证
- 表存在性
- 列存在性
- 数据类型匹配
- 函数可用性

### 3. 性能检查
- 索引使用
- 查询复杂度
- 潜在性能问题

## 使用示例

```python
# 创建工具
tool = SQLValidationTool(db_config=db_config)

# 验证 SQL
result = tool.run({
    "sql": "SELECT * FROM orders WHERE created_at > '2024-01-01'",
    "schema_info": schema_info
})

if result["valid"]:
    print("SQL is valid and ready to execute")
else:
    print(f"SQL validation failed: {result['syntax_check']['message']}")

# 检查警告
for warning in result.get("warnings", []):
    print(f"Warning: {warning}")
```

## 错误处理

```python
# 无效 SQL 示例
result = tool.run({
    "sql": "SELECT * FROM non_existent_table",
    "schema_info": schema_info
})

# 结果
{
    "valid": false,
    "syntax_check": {
        "passed": true,
        "message": "SQL syntax is valid"
    },
    "semantic_check": {
        "passed": false,
        "tables_exist": false,
        "invalid_references": ["non_existent_table"]
    }
}
```

## 注意事项

1. 只验证不执行
2. 依赖准确的 schema 信息
3. MySQL 特定语法支持
4. 性能建议仅供参考

---

相关文档：
- [SQLExecutionTool](./SQLExecutionTool.md)
- [SQLGenerationTool](../生成工具/SQLGenerationTool.md)