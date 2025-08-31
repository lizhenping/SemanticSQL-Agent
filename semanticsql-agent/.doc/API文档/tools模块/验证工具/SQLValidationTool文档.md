# SQLValidationTool API 文档

## 概述
`SQLValidationTool` 是用于验证 SQL 查询语法和结构正确性的工具。支持多种 SQL 方言的语法检查、安全性验证和性能建议。

## 类定义
```python
class SQLValidationTool(BaseTool):
    """SQL语法验证工具"""
```

## 工具属性

- **名称**: `sql_validation`
- **类别**: `validation`
- **描述**: 验证SQL查询的语法和结构正确性

## 参数定义

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|-------|------|------|--------|------|
| sql | string | 是 | - | 要验证的SQL查询 |
| schema_info | object | 否 | {} | 数据库结构信息 |
| dialect | string | 否 | "mysql" | SQL方言 (mysql/postgresql/sqlite) |
| strict | boolean | 否 | True | 是否严格验证 |

## 执行方法

### `_execute(...) -> Dict[str, Any]`

**返回数据结构：**
```python
{
    "valid": bool,               # 是否有效
    "errors": List[str],         # 错误列表
    "warnings": List[str],       # 警告列表
    "suggestions": List[str],    # 改进建议
    "formatted_sql": str,        # 格式化后的SQL
    "metadata": Dict[str, Any]   # SQL元数据信息
}
```

## 验证功能

### 1. 语法验证 (`_validate_syntax`)
- 基本 SQL 语法检查
- 关键字使用验证
- 语句结构完整性

### 2. 结构验证 (`_validate_structure`)
- 表名和列名验证
- 连接条件检查
- 聚合函数使用验证

### 3. 安全性验证 (`_validate_security`)
- SQL 注入风险检测
- 危险操作警告
- 权限相关检查

### 4. 性能验证 (`_validate_performance`)
- 索引使用建议
- 查询优化提示
- 潜在性能问题警告

### 5. 方言特定验证 (`_validate_dialect_specific`)
- MySQL 特定语法
- PostgreSQL 特定语法
- SQLite 特定语法

## 使用示例

### 基本验证
```python
# 创建工具实例
tool = SQLValidationTool(settings)

# 验证简单查询
result = tool.run(
    sql="SELECT * FROM users WHERE id = 1",
    dialect="mysql"
)

if result["success"]:
    validation = result["data"]
    if validation["valid"]:
        print("SQL 语法正确")
    else:
        print("SQL 存在错误:")
        for error in validation["errors"]:
            print(f"- {error}")
```

### 带数据库结构的验证
```python
# 提供数据库结构信息
schema_info = {
    "tables": {
        "users": {
            "columns": ["id", "name", "email", "created_at"]
        },
        "orders": {
            "columns": ["id", "user_id", "amount", "status"]
        }
    }
}

# 验证包含表和列的查询
result = tool.run(
    sql="""
    SELECT u.name, SUM(o.amount) as total
    FROM users u
    JOIN orders o ON u.id = o.user_id
    WHERE o.status = 'completed'
    GROUP BY u.id, u.name
    HAVING total > 1000
    """,
    schema_info=schema_info,
    dialect="mysql",
    strict=True
)

# 查看验证结果
if result["success"]:
    validation = result["data"]
    
    if validation["warnings"]:
        print("警告:")
        for warning in validation["warnings"]:
            print(f"- {warning}")
    
    if validation["suggestions"]:
        print("优化建议:")
        for suggestion in validation["suggestions"]:
            print(f"- {suggestion}")
```

## 验证规则详解

### 错误类型
1. **语法错误**
   - 缺少必需的子句
   - 关键字拼写错误
   - 括号不匹配

2. **结构错误**
   - 引用不存在的表或列
   - 连接条件缺失
   - 聚合函数使用错误

3. **逻辑错误**
   - GROUP BY 缺少非聚合列
   - HAVING 使用了未分组的列
   - 子查询返回多行用于单值比较

### 警告类型
1. **性能警告**
   - SELECT * 的使用
   - 缺少 WHERE 条件
   - 可能的笛卡尔积

2. **安全警告**
   - 动态 SQL 风险
   - 过于宽泛的权限
   - 敏感数据暴露

### 建议类型
1. **索引建议**
   - 建议创建的索引
   - 覆盖索引机会
   
2. **查询优化**
   - 使用 EXISTS 替代 IN
   - 避免在 WHERE 中使用函数
   - 合理使用 LIMIT

## 方言特定功能

### MySQL
- 反引号标识符检查
- LIMIT 语法验证
- 特定函数支持

### PostgreSQL
- 双引号标识符检查
- LIMIT/OFFSET 语法
- 数组和 JSON 操作

### SQLite
- 灵活的类型系统
- 简化的语法规则

## 错误示例

### 输入
```sql
SELECT user_name, COUNT(*)
FROM users
WHERE created_at > '2024-01-01'
```

### 输出
```json
{
    "valid": false,
    "errors": [
        "GROUP BY 子句缺失：使用聚合函数 COUNT(*) 时需要 GROUP BY"
    ],
    "warnings": [],
    "suggestions": [
        "添加 GROUP BY user_name 子句"
    ]
}
```

## 性能考虑

- 基本语法验证：< 10ms
- 完整验证（含结构）：10-50ms
- 大型 SQL（>1000行）：可能需要更长时间

## 最佳实践

1. **提供完整的数据库结构**
   - 可以进行更准确的验证
   - 检测表和列名错误

2. **使用严格模式**
   - 生产环境建议开启
   - 捕获更多潜在问题

3. **关注警告和建议**
   - 即使语法正确也要检查
   - 有助于优化查询性能

## 注意事项

1. 不执行实际的 SQL 查询
2. 某些运行时错误无法检测
3. 性能建议基于通用规则
4. 复杂查询可能需要人工审核