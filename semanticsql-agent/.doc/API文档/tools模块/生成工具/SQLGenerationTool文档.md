# SQLGenerationTool API 文档

## 概述
`SQLGenerationTool` 是用于根据自然语言问题生成 SQL 查询语句的工具。支持多种 SQL 方言和操作类型。

## 类定义
```python
class SQLGenerationTool(BaseTool):
    """生成SQL查询语句"""
```

## 工具属性

- **名称**: `generate_sql`
- **类别**: `generation`
- **描述**: 根据自然语言问题生成对应的SQL查询

## 参数定义

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|-------|------|------|--------|------|
| question | string | 是 | - | 自然语言问题 |
| schema_info | object | 是 | - | 数据库结构信息 |
| operations | array | 否 | [] | 期望的SQL操作类型 |
| dialect | string | 否 | "mysql" | SQL方言 (mysql/postgresql/sqlite) |
| use_llm | boolean | 否 | True | 是否使用LLM生成 |

## 执行方法

### `_execute(...) -> Dict[str, Any]`

**返回数据结构：**
```python
{
    "sql": str,                    # 生成的SQL语句
    "operations": List[str],       # 使用的操作类型
    "tables": List[str],           # 涉及的表
    "complexity": str,             # 复杂度 (simple/medium/complex)
    "explanation": str,            # SQL解释
    "confidence": float            # 生成置信度
}
```

## 内部方法

### `_generate_with_llm(question: str, schema_context: str, dialect: str) -> str`
使用 LLM 生成 SQL。

**提示词模板包含：**
- 角色定义（SQL专家）
- 数据库结构上下文
- SQL方言要求
- 格式化要求

### `_generate_with_rules(question: str, schema_info: Dict, operations: List[str]) -> str`
使用规则引擎生成 SQL（备用方案）。

**支持的模式：**
- 简单查询（SELECT）
- 聚合查询（GROUP BY）
- 连接查询（JOIN）
- 排序和限制（ORDER BY, LIMIT）

### `_extract_sql_from_response(response: str) -> str`
从 LLM 响应中提取 SQL 语句。

### `_analyze_sql(sql: str, schema_info: Dict) -> Dict[str, Any]`
分析生成的 SQL 语句。

**分析内容：**
- 使用的操作类型
- 涉及的表
- 查询复杂度
- 语法正确性

### `_format_schema_context(schema_info: Any, relevant_tables: List[str] = None) -> str`
格式化数据库结构信息为 LLM 上下文。

## 使用示例

```python
# 创建工具实例
tool = SQLGenerationTool(settings)

# 准备数据库结构信息
schema_info = {
    "database_name": "sales_db",
    "tables": {
        "users": {
            "columns": [
                {"name": "id", "type": "int", "is_primary": True},
                {"name": "name", "type": "varchar(100)"},
                {"name": "email", "type": "varchar(255)"},
                {"name": "created_at", "type": "datetime"}
            ]
        },
        "orders": {
            "columns": [
                {"name": "id", "type": "int", "is_primary": True},
                {"name": "user_id", "type": "int"},
                {"name": "total_amount", "type": "decimal(10,2)"},
                {"name": "order_date", "type": "datetime"}
            ]
        }
    }
}

# 生成简单查询
result = tool.run(
    question="查询所有用户的姓名和邮箱",
    schema_info=schema_info,
    dialect="mysql"
)

if result["success"]:
    data = result["data"]
    print(f"生成的SQL: {data['sql']}")
    print(f"复杂度: {data['complexity']}")
    print(f"解释: {data['explanation']}")

# 生成复杂查询
result = tool.run(
    question="查询上个月订单金额超过1000的用户及其总消费",
    schema_info=schema_info,
    operations=["JOIN", "GROUP", "HAVING"],
    dialect="mysql"
)
```

## 支持的 SQL 操作类型

- **SELECT**: 基本查询
- **JOIN**: 表连接（INNER, LEFT, RIGHT）
- **GROUP**: 分组聚合
- **HAVING**: 分组过滤
- **ORDER**: 排序
- **LIMIT**: 限制结果数
- **SUBQUERY**: 子查询
- **CTE**: 公共表表达式
- **WINDOW**: 窗口函数

## SQL 方言特性

### MySQL
- 使用反引号包裹标识符
- LIMIT 语法
- 日期函数：DATE_SUB, DATE_ADD

### PostgreSQL
- 使用双引号包裹标识符
- LIMIT/OFFSET 语法
- 日期函数：interval 语法

### SQLite
- 灵活的标识符引用
- 简化的日期处理

## 生成示例

### 输入
```python
question = "查询每个部门平均工资最高的前3个部门"
```

### 输出
```sql
SELECT 
    d.department_name,
    AVG(e.salary) as avg_salary
FROM employees e
INNER JOIN departments d ON e.department_id = d.id
GROUP BY d.id, d.department_name
ORDER BY avg_salary DESC
LIMIT 3
```

## 错误处理

- `LLMError`: LLM 调用失败
- `GenerationError`: SQL 生成失败
- `ValidationError`: 参数验证失败

## 优化建议

1. **提供完整的数据库结构**
   - 包含所有相关表和列
   - 标注主键和外键关系

2. **明确查询意图**
   - 使用清晰的自然语言
   - 指定期望的操作类型

3. **选择合适的方言**
   - 根据目标数据库选择
   - 注意方言特有语法

## 性能考虑

- LLM 调用可能有延迟（1-3秒）
- 规则引擎作为备用方案更快
- 复杂查询生成时间更长

## 注意事项

1. 生成的 SQL 需要进一步验证
2. LLM 可能产生语法错误
3. 复杂查询建议人工审核
4. 注意 SQL 注入风险（仅用于开发）