# SQLReflectionTool API 文档

## 概述
`SQLReflectionTool` 是用于分析 SQL 执行结果并提供质量评估和优化建议的工具。通过对查询的多维度分析，帮助改进 SQL 质量。

## 类定义
```python
class SQLReflectionTool(BaseTool):
    """SQL执行反思与优化工具"""
```

## 工具属性

- **名称**: `sql_reflection`
- **类别**: `reflection`
- **描述**: 分析SQL执行结果并提供质量评估和优化建议

## 参数定义

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|-------|------|------|--------|------|
| question | string | 是 | - | 自然语言问题 |
| sql | string | 是 | - | 生成的SQL查询 |
| validation_result | object | 否 | {} | SQL验证结果 |
| execution_result | object | 否 | {} | SQL执行结果 |
| use_llm | boolean | 否 | False | 是否使用LLM进行深度分析 |

## 质量评估维度

### 质量权重配置
```python
{
    "syntax_correctness": 0.3,    # 语法正确性
    "semantic_match": 0.3,         # 语义匹配度
    "execution_success": 0.25,     # 执行成功率
    "result_relevance": 0.15       # 结果相关性
}
```

## 执行方法

### `_execute(...) -> Dict[str, Any]`

**返回数据结构：**
```python
{
    "overall_quality": float,           # 总体质量分数 (0-1)
    "quality_breakdown": {              # 质量分解
        "syntax_correctness": float,
        "semantic_match": float,
        "execution_success": float,
        "result_relevance": float
    },
    "improvements": List[str],          # 改进建议
    "optimized_sql": Optional[str],     # 优化后的SQL
    "confidence": float,                # 反思置信度
    "analysis": str                     # 详细分析
}
```

## 内部分析方法

### `_calculate_quality_score(...) -> Tuple[float, Dict[str, float]]`
计算综合质量分数。

**评估维度：**
1. **语法正确性**
   - 基于验证结果
   - 无错误得满分
   - 有警告适当扣分

2. **语义匹配度**
   - 问题与SQL的对应关系
   - 操作类型匹配
   - 条件完整性

3. **执行成功率**
   - 是否成功执行
   - 执行时间
   - 结果集大小

4. **结果相关性**
   - 返回数据的相关度
   - 列选择的合理性

### `_analyze_and_improve(question: str, sql: str, ...) -> Tuple[List[str], Optional[str]]`
分析并提供改进建议。

**分析内容：**
- 性能优化机会
- 语义准确性
- 安全性改进
- 可读性提升

### `_use_llm_reflection(question: str, sql: str, context: Dict) -> Dict[str, Any]`
使用 LLM 进行深度反思分析。

## 使用示例

### 基础反思分析
```python
# 创建工具实例
tool = SQLReflectionTool(settings)

# 准备输入数据
question = "查询上个月销售额最高的10个产品"
sql = """
SELECT product_id, SUM(amount) as total_sales
FROM orders
WHERE order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH)
GROUP BY product_id
ORDER BY total_sales DESC
LIMIT 10
"""

validation_result = {
    "valid": True,
    "errors": [],
    "warnings": ["未连接产品表获取产品名称"]
}

execution_result = {
    "success": True,
    "row_count": 10,
    "execution_time_ms": 150
}

# 执行反思
result = tool.run(
    question=question,
    sql=sql,
    validation_result=validation_result,
    execution_result=execution_result
)

if result["success"]:
    reflection = result["data"]
    print(f"质量分数: {reflection['overall_quality']:.2f}")
    print(f"置信度: {reflection['confidence']:.2f}")
    
    print("\n质量分解:")
    for dimension, score in reflection['quality_breakdown'].items():
        print(f"- {dimension}: {score:.2f}")
    
    print("\n改进建议:")
    for improvement in reflection['improvements']:
        print(f"- {improvement}")
    
    if reflection['optimized_sql']:
        print(f"\n优化后的SQL:\n{reflection['optimized_sql']}")
```

### 使用 LLM 深度分析
```python
# 启用 LLM 深度分析
result = tool.run(
    question=question,
    sql=sql,
    validation_result=validation_result,
    execution_result=execution_result,
    use_llm=True
)

if result["success"]:
    reflection = result["data"]
    print(f"深度分析:\n{reflection['analysis']}")
```

## 改进建议类型

### 1. 性能优化
- 添加适当的索引
- 优化 JOIN 顺序
- 使用更高效的查询模式
- 避免全表扫描

### 2. 语义准确性
- 补充缺失的条件
- 修正错误的聚合逻辑
- 添加必要的数据过滤

### 3. 结果完整性
- 添加缺失的列
- 包含相关的关联数据
- 提供更好的结果格式

### 4. 安全性改进
- 参数化查询建议
- 权限控制提醒
- 数据脱敏建议

## 优化示例

### 原始 SQL
```sql
SELECT user_id, COUNT(*)
FROM orders
WHERE status = 'completed'
GROUP BY user_id
```

### 优化建议
1. "建议连接用户表获取用户名"
2. "添加时间范围限制提高查询效率"
3. "考虑添加 HAVING 子句过滤小额用户"

### 优化后的 SQL
```sql
SELECT 
    u.user_id,
    u.user_name,
    COUNT(o.order_id) as order_count,
    SUM(o.amount) as total_amount
FROM orders o
INNER JOIN users u ON o.user_id = u.user_id
WHERE o.status = 'completed'
    AND o.order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 MONTH)
GROUP BY u.user_id, u.user_name
HAVING COUNT(o.order_id) >= 5
ORDER BY total_amount DESC
```

## 质量评分标准

### 高质量 SQL (0.8-1.0)
- 语法完全正确
- 完美匹配用户意图
- 执行效率高
- 结果准确相关

### 中等质量 SQL (0.6-0.8)
- 基本正确但有小问题
- 大致匹配用户意图
- 执行效率可接受
- 结果基本相关

### 低质量 SQL (< 0.6)
- 存在明显错误
- 偏离用户意图
- 执行效率低
- 结果不够相关

## 最佳实践

1. **提供完整的上下文**
   - 包含验证和执行结果
   - 提供原始问题

2. **定期使用反思**
   - 每次生成 SQL 后反思
   - 积累优化经验

3. **结合 LLM 分析**
   - 复杂查询使用 LLM
   - 获取更深入的见解

4. **跟踪质量趋势**
   - 记录质量分数
   - 识别常见问题

## 注意事项

1. 反思建议仅供参考
2. LLM 分析可能增加延迟
3. 质量分数是相对指标
4. 需要结合实际业务判断