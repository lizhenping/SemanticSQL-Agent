# OperationSelectionTool API 文档

## 概述
`OperationSelectionTool` 是为查询场景选择合适 SQL 操作的工具。它根据场景的复杂度、涉及的表数量和业务需求，智能选择最合适的 SQL 操作组合。

## 类定义
```python
class OperationSelectionTool(BaseTool):
    """为查询场景选择SQL操作类型"""
```

## 工具属性

- **名称**: `select_operations`
- **类别**: `generation`
- **描述**: 根据场景和难度选择合适的SQL操作组合

## 参数定义

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|-------|------|------|--------|------|
| scenario | object | 是 | - | 查询场景 |
| schema_info | object | 是 | - | 数据库结构信息 |
| force_operations | array | 否 | [] | 强制包含的操作类型 |

## 执行方法

### `_execute(...) -> Dict[str, Any]`

**返回数据结构：**
```python
{
    "operations": List[str],              # 选择的操作列表
    "operation_details": {                # 操作详情
        "operation_name": {
            "purpose": str,               # 操作目的
            "example": str,               # 使用示例
            "complexity_impact": str      # 对复杂度的影响
        },
        ...
    },
    "reasoning": str,                     # 选择理由
    "estimated_complexity": float         # 预估复杂度分数
}
```

## 内部方法

### `_select_operations_by_difficulty(difficulty: DifficultyLevel, table_count: int, ...) -> List[SQLOperation]`
根据难度选择操作。

**难度映射规则：**

#### 简单 (EASY)
- 基础操作：SELECT, WHERE
- 最多 1 个聚合函数
- 不包含 JOIN
- 适合单表查询

#### 中等 (MEDIUM)
- 增加：JOIN, GROUP BY, ORDER BY
- 支持多个聚合函数
- 简单的 HAVING 条件
- 2-3 个表的连接

#### 困难 (HARD)
- 增加：SUBQUERY, UNION
- 复杂的聚合和分组
- 多层嵌套查询
- 3-4 个表的复杂连接

#### 专家 (EXPERT)
- 增加：WINDOW, CTE
- 递归查询
- 复杂的分析函数
- 5+ 个表的连接

### `_generate_operation_details(operations: List[SQLOperation], scenario: Dict, schema_info: Dict) -> Dict`
生成操作详细说明。

**详情内容：**
- 每个操作的具体用途
- 在当前场景中的应用
- 预期的性能影响
- 使用建议

### `_estimate_complexity(operations: List[SQLOperation], table_count: int) -> float`
估算查询复杂度。

**复杂度计算：**
```python
基础分数 = len(operations) * 0.1
表复杂度 = table_count * 0.15
操作复杂度 = sum(operation_weights)
总分 = min(基础分数 + 表复杂度 + 操作复杂度, 1.0)
```

## 操作权重配置

```python
OPERATION_WEIGHTS = {
    SQLOperation.SELECT: 0.1,
    SQLOperation.JOIN: 0.2,
    SQLOperation.GROUP: 0.15,
    SQLOperation.SUBQUERY: 0.3,
    SQLOperation.WINDOW: 0.4,
    SQLOperation.CTE: 0.35,
    SQLOperation.UNION: 0.25
}
```

## 使用示例

### 基本使用
```python
# 创建工具实例
tool = OperationSelectionTool(settings)

# 定义场景
scenario = {
    "category": "销售分析",
    "complexity": DifficultyLevel.MEDIUM,
    "applicable_tables": ["orders", "customers", "products"],
    "business_purpose": "分析客户购买行为"
}

# 选择操作
result = tool.run(
    scenario=scenario,
    schema_info=schema_info
)

if result["success"]:
    data = result["data"]
    print(f"选择的操作: {data['operations']}")
    print(f"预估复杂度: {data['estimated_complexity']}")
    print(f"选择理由: {data['reasoning']}")
```

### 强制包含特定操作
```python
# 强制使用窗口函数
result = tool.run(
    scenario=scenario,
    schema_info=schema_info,
    force_operations=["WINDOW"]
)

# 输出将包含 WINDOW 操作，即使原本难度不需要
```

### 操作详情示例
```python
result = tool.run(scenario=scenario, schema_info=schema_info)

if result["success"]:
    details = result["data"]["operation_details"]
    
    for op, info in details.items():
        print(f"\n操作: {op}")
        print(f"目的: {info['purpose']}")
        print(f"示例: {info['example']}")
        print(f"复杂度影响: {info['complexity_impact']}")
```

## 输出示例

### 中等难度场景
```json
{
    "operations": ["SELECT", "JOIN", "GROUP", "ORDER"],
    "operation_details": {
        "SELECT": {
            "purpose": "选择需要的客户和订单字段",
            "example": "SELECT c.name, o.total_amount",
            "complexity_impact": "基础操作，影响较小"
        },
        "JOIN": {
            "purpose": "连接客户表和订单表",
            "example": "FROM customers c JOIN orders o ON c.id = o.customer_id",
            "complexity_impact": "增加查询复杂度，需要索引优化"
        },
        "GROUP": {
            "purpose": "按客户分组统计",
            "example": "GROUP BY c.id, c.name",
            "complexity_impact": "需要扫描和排序，影响性能"
        },
        "ORDER": {
            "purpose": "按购买金额排序",
            "example": "ORDER BY SUM(o.total_amount) DESC",
            "complexity_impact": "额外的排序操作"
        }
    },
    "reasoning": "该场景需要分析客户购买行为，需要连接多表并进行分组统计",
    "estimated_complexity": 0.65
}
```

### 专家级场景
```json
{
    "operations": ["SELECT", "JOIN", "GROUP", "WINDOW", "CTE", "SUBQUERY"],
    "operation_details": {
        "WINDOW": {
            "purpose": "计算客户购买排名和累计消费",
            "example": "ROW_NUMBER() OVER (ORDER BY total_amount DESC)",
            "complexity_impact": "高级分析功能，显著增加复杂度"
        },
        "CTE": {
            "purpose": "创建临时结果集便于复杂查询",
            "example": "WITH customer_stats AS (...)",
            "complexity_impact": "提高可读性但增加执行步骤"
        },
        "SUBQUERY": {
            "purpose": "计算平均值用于对比",
            "example": "WHERE amount > (SELECT AVG(amount) FROM ...)",
            "complexity_impact": "嵌套查询增加执行时间"
        }
    },
    "reasoning": "复杂的客户分析需要使用高级SQL特性进行多维度计算",
    "estimated_complexity": 0.95
}
```

## 操作组合策略

### 常见组合
1. **基础查询**: SELECT + WHERE
2. **简单统计**: SELECT + GROUP + COUNT/SUM
3. **多表查询**: SELECT + JOIN + WHERE
4. **分组排序**: SELECT + GROUP + ORDER + HAVING
5. **高级分析**: SELECT + WINDOW + CTE

### 避免的组合
- 过多的嵌套子查询
- 不必要的 UNION
- 冗余的 JOIN
- 过度复杂的 CTE

## 性能考虑

### 操作成本估算
- SELECT: 低成本
- JOIN: 中等成本（取决于索引）
- GROUP: 中等成本（需要排序）
- SUBQUERY: 高成本（多次扫描）
- WINDOW: 高成本（复杂计算）

### 优化建议
1. 优先使用 JOIN 而非子查询
2. 合理使用索引减少 JOIN 成本
3. 避免在 WHERE 中使用函数
4. 考虑使用 CTE 提高可读性

## 最佳实践

1. **渐进式复杂度**
   - 从简单操作开始
   - 逐步添加复杂操作
   - 验证每步的必要性

2. **场景匹配**
   - 统计类：GROUP + 聚合函数
   - 排名类：WINDOW 函数
   - 对比类：子查询或 CTE

3. **性能平衡**
   - 考虑数据量
   - 评估索引情况
   - 选择高效的操作组合

4. **可维护性**
   - 复杂查询使用 CTE
   - 避免过深的嵌套
   - 保持操作逻辑清晰

## 注意事项

1. 操作选择基于经验规则，可能需要调整
2. 实际性能取决于数据分布和索引
3. 某些数据库可能不支持所有操作
4. 建议结合执行计划验证选择的合理性