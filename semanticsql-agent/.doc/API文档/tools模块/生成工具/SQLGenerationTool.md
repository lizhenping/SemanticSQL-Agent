# SQLGenerationTool API 文档

根据自然语言问题生成 SQL 查询的核心工具。

## 类定义

```python
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

class SQLGenerationTool(BaseTool):
    """
    SQL 生成工具
    
    基于自然语言问题和数据库结构信息生成 SQL 查询。
    使用 LLM 理解问题语义并生成符合语法的 SQL。
    
    Attributes:
        name: 工具名称，固定为 "sql_generation"
        description: 工具描述
        llm: LangChain LLM 实例
        dialect: SQL 方言，默认 "mysql"
    """
    
    name = "sql_generation"
    description = "Generate SQL query from natural language question based on database schema"
```

## 输入定义

```python
class InputSchema(BaseModel):
    """工具输入参数"""
    question: str = Field(
        description="Natural language question to convert to SQL"
    )
    schema_info: Dict[str, Any] = Field(
        description="Database schema information from memory"
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional context like domain info, examples"
    )
    sql_type: Optional[str] = Field(
        default=None,
        description="Expected SQL type: SELECT, INSERT, UPDATE, DELETE"
    )

args_schema = InputSchema
```

## 核心方法

### _run

```python
def _run(
    self,
    question: str,
    memory: Dict[str, Any]
) -> Dict[str, Any]:
    """
    生成 SQL 查询
    
    Args:
        question: 自然语言问题
        memory: 完整的数据库分析记忆（包含schema_info, er_analysis, domain_analysis等）
    
    Returns:
        Dict[str, Any]: 生成结果
    
    Raises:
        SQLGenerationError: SQL 生成失败
        InvalidSchemaError: Schema 信息无效
    
    Return Format:
        ```python
        {
            "sql": "SELECT COUNT(*) FROM orders WHERE status = 'completed'",
            "dialect": "mysql",
            "tables_used": ["orders"],
            "operations_used": ["SELECT", "WHERE", "COUNT"],
            "has_aggregation": true,
            "has_join": false,
            "complexity": "simple"
        }
        ```
    """
```

## 生成流程

### _build_prompt

```python
def _build_prompt(
    self,
    question: str,
    schema_info: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None
) -> str:
    """
    构建 LLM 提示词
    
    包含：
    1. 数据库结构描述
    2. 问题文本
    3. 生成要求
    4. 示例（如果有）
    """
```

### _extract_tables_info

```python
def _extract_tables_info(
    self,
    schema_info: Dict[str, Any],
    question: str
) -> Dict[str, Any]:
    """
    提取相关表信息
    
    根据问题内容，智能筛选相关的表和列信息，
    避免提示词过长。
    """
```

### _validate_sql

```python
def _validate_sql(
    self,
    sql: str,
    schema_info: Dict[str, Any]
) -> List[str]:
    """
    基础 SQL 验证
    
    检查：
    - 表名是否存在
    - 列名是否正确
    - 基本语法结构
    
    Returns:
        List[str]: 发现的问题列表
    """
```

## 高级功能

### 复杂查询生成

```python
# 生成包含 JOIN 的查询
result = tool.run(
    question="查询每个用户的订单总金额和订单数量",
    schema_info=schema,
    context={
        "expected_operations": ["JOIN", "GROUP BY", "AGGREGATE"],
        "performance_hint": "optimize_for_large_dataset"
    }
)

# 生成的 SQL 示例：
# SELECT 
#     u.id, 
#     u.name,
#     COUNT(o.id) as order_count,
#     SUM(o.total_amount) as total_amount
# FROM users u
# LEFT JOIN orders o ON u.id = o.user_id
# GROUP BY u.id, u.name
```

### 时间相关查询

```python
# 处理相对时间
result = tool.run(
    question="查询最近7天的销售趋势",
    schema_info=schema,
    context={
        "current_date": "2024-12-20",
        "timezone": "Asia/Shanghai"
    }
)

# 生成的 SQL：
# SELECT 
#     DATE(created_at) as date,
#     COUNT(*) as order_count,
#     SUM(amount) as total_sales
# FROM orders
# WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
# GROUP BY DATE(created_at)
# ORDER BY date
```

### 子查询和 CTE

```python
# 生成复杂查询
result = tool.run(
    question="查询销售额超过平均值的产品",
    schema_info=schema,
    sql_type="SELECT",
    context={"prefer_cte": True}
)

# 生成的 SQL（使用 CTE）：
# WITH avg_sales AS (
#     SELECT AVG(total_sales) as avg_amount
#     FROM product_sales
# )
# SELECT p.*, ps.total_sales
# FROM products p
# JOIN product_sales ps ON p.id = ps.product_id
# CROSS JOIN avg_sales
# WHERE ps.total_sales > avg_sales.avg_amount
```

## 使用示例

### 基础使用

```python
from semanticsql_agent.tools.generation import SQLGenerationTool

# 创建工具
tool = SQLGenerationTool(llm=llm)

# 准备 schema 信息（通常从记忆中获取）
schema_info = {
    "tables": [
        {"name": "users", "columns": [...]},
        {"name": "orders", "columns": [...]}
    ],
    "foreign_keys": [...]
}

# 生成 SQL
result = tool.run(
    question="查询今天的订单数量",
    schema_info=schema_info
)

print(f"SQL: {result['sql']}")
print(f"Confidence: {result['confidence']}")
```

### 在 Agent 中使用

```python
# Agent 自动从记忆中获取 schema
# Thought: I need to generate SQL for this question
# Action: sql_generation
# Action Input: {
#     "question": "查询VIP用户的平均消费",
#     "schema_info": {from memory}
# }
```

### 批量生成

```python
questions = [
    "查询所有用户",
    "统计每月订单数",
    "找出最畅销的产品"
]

results = []
for question in questions:
    try:
        result = tool.run(
            question=question,
            schema_info=schema_info
        )
        results.append({
            "question": question,
            "sql": result["sql"],
            "confidence": result["confidence"]
        })
    except Exception as e:
        print(f"Failed for '{question}': {e}")
```

## 优化技巧

### 提供上下文

```python
# 提供领域上下文
result = tool.run(
    question="查询活跃用户",
    schema_info=schema,
    context={
        "domain": "e-commerce",
        "business_rules": {
            "active_user": "用户在最近30天内有订单"
        }
    }
)
```

### 使用示例引导

```python
# Few-shot learning
context = {
    "examples": [
        {
            "question": "查询总销售额",
            "sql": "SELECT SUM(amount) FROM orders"
        },
        {
            "question": "查询用户数量",
            "sql": "SELECT COUNT(DISTINCT user_id) FROM users"
        }
    ]
}

result = tool.run(
    question="查询订单总数",
    schema_info=schema,
    context=context
)
```

### 性能优化提示

```python
# 指导生成高效 SQL
result = tool.run(
    question="查询大表中的数据",
    schema_info=schema,
    context={
        "performance_hints": [
            "use_index",
            "limit_results",
            "avoid_full_scan"
        ],
        "estimated_data_size": "1M+ rows"
    }
)
```

## 错误处理

```python
try:
    result = tool.run(question=question, schema_info=schema)
except SQLGenerationError as e:
    # SQL 生成失败
    print(f"Generation failed: {e.message}")
    print(f"Problematic input: {e.input_data}")
    
    # 尝试简化问题
    simplified = simplify_question(question)
    result = tool.run(question=simplified, schema_info=schema)
    
except InvalidSchemaError as e:
    # Schema 信息有问题
    print(f"Invalid schema: {e.message}")
    # 重新获取 schema
```

## 配置选项

```python
class SQLGenerationConfig:
    # 生成参数
    temperature: float = 0.3  # 低温度for更确定的输出
    max_tokens: int = 500
    
    # SQL 风格
    use_backticks: bool = True  # MySQL 风格
    uppercase_keywords: bool = True
    
    # 复杂度控制
    max_joins: int = 3
    max_subqueries: int = 2
    
    # 安全选项
    read_only: bool = True  # 只生成 SELECT
    
# 使用配置
tool = SQLGenerationTool(
    llm=llm,
    config=SQLGenerationConfig(
        temperature=0.2,
        read_only=True
    )
)
```

## 质量保证

### 置信度评估

```python
def assess_confidence(result):
    """评估生成 SQL 的置信度"""
    confidence = result['confidence']
    
    if confidence < 0.7:
        print("Low confidence, consider:")
        print("- Simplifying the question")
        print("- Providing more context")
        print("- Checking schema completeness")
    
    return confidence >= 0.8
```

### 后处理

```python
def post_process_sql(sql: str) -> str:
    """SQL 后处理"""
    # 格式化
    sql = sqlparse.format(
        sql,
        reindent=True,
        keyword_case='upper'
    )
    
    # 添加注释
    sql = f"-- Generated from: {question}\n{sql}"
    
    # 安全检查
    if "DROP" in sql or "DELETE" in sql:
        raise ValueError("Unsafe SQL detected")
    
    return sql
```

## 注意事项

1. **LLM 依赖**：质量高度依赖 LLM 能力
2. **Schema 完整性**：确保 schema 信息准确完整
3. **安全性**：生产环境中仅生成只读查询
4. **性能考虑**：生成的 SQL 可能需要优化
5. **方言差异**：目前优化for MySQL，其他数据库需调整

## 相关工具

- [SQLValidationTool](../验证工具/SQLValidationTool.md) - 验证生成的 SQL
- [SQLExecutionTool](../验证工具/SQLExecutionTool.md) - 执行 SQL 查询
- [SQLReflectionTool](../反思工具/SQLReflectionTool.md) - 评估 SQL 质量

---

更多信息请参考 [LangChain LLM 文档](https://docs.langchain.com/docs/modules/llms/)