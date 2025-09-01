# OperationSelectionTool API 文档

操作选择工具，基于场景选择合适的 SQL 操作组合。

## 类定义

```python
from langchain.tools import BaseTool
from typing import Dict, Any, List
from semanticsql_agent.tools.generation_tools import OperationSelectionTool

class OperationSelectionTool(BaseTool):
    """
    操作选择工具
    
    根据场景的复杂度和特点，基于预定义规则选择 SQL 操作。
    
    Attributes:
        name: "operation_selection"
        description: "为查询场景选择合适的 SQL 操作"
    """
```

## 构造函数

```python
def __init__(self):
    """
    初始化操作选择工具
    
    加载预定义的操作选择规则。
    """
```

## 核心方法

### _run

```python
def _run(
    self,
    scenario: Dict[str, Any],
    memory: Dict[str, Any]
) -> Dict[str, Any]:
    """
    选择 SQL 操作
    
    功能描述：
        基于场景的复杂度和业务需求，根据预定义规则选择合适的SQL操作组合。
        确保生成的SQL既满足业务需求，又具有良好的性能。
    
    Args:
        scenario: 查询场景（来自 scenario_tool 的输出）
            - 必须包含: category, difficulty, tables, suggested_operations
        memory: 数据库分析记忆
            - 使用 memory["db_analysis"]["schema_info"] 验证表是否存在
            - 使用 memory["db_analysis"]["er_analysis"] 确定JOIN路径
    
    Returns:
        Dict[str, Any]: 选择的操作组合
    
    Return Format:
        ```python
        {
            "operations": ["SELECT", "JOIN", "WHERE", "GROUP BY", "HAVING"],
            "join_type": "INNER",
            "aggregations": ["SUM", "COUNT"],
            "filters": {
                "time_filter": True,
                "status_filter": True
            },
            "ordering": "ORDER BY total_amount DESC",
            "limit": 10,
            "complexity_score": 0.7,
            "operation_sequence": [
                "1. JOIN orders with customers",
                "2. Filter by date range",
                "3. Group by customer",
                "4. Calculate aggregations",
                "5. Order and limit results"
            ]
        }
        ```
    """
```

## 预定义规则

### 基础规则映射
```python
OPERATION_RULES = {
    "easy": {
        "max_tables": 1,
        "operations": ["SELECT", "WHERE"],
        "allow_aggregation": False,
        "allow_join": False
    },
    "medium": {
        "max_tables": 3,
        "operations": ["SELECT", "JOIN", "WHERE", "GROUP BY"],
        "allow_aggregation": True,
        "allow_join": True,
        "join_types": ["INNER", "LEFT"]
    },
    "hard": {
        "max_tables": 5,
        "operations": ["SELECT", "JOIN", "WHERE", "GROUP BY", "HAVING", "UNION"],
        "allow_aggregation": True,
        "allow_join": True,
        "join_types": ["INNER", "LEFT", "RIGHT"],
        "allow_subquery": True
    }
}
```

### 场景类别规则
```python
CATEGORY_RULES = {
    "销售分析": {
        "common_operations": ["GROUP BY", "SUM", "COUNT"],
        "common_filters": ["date_range", "product_category"],
        "common_dimensions": ["time", "product", "region"]
    },
    "客户分析": {
        "common_operations": ["JOIN", "COUNT", "AVG"],
        "common_filters": ["customer_segment", "registration_date"],
        "common_dimensions": ["customer_type", "region", "channel"]
    }
}
```

## 操作选择逻辑

### 1. 难度映射
根据场景难度确定可用操作集

### 2. 表关系分析
根据涉及的表确定 JOIN 策略

### 3. 业务逻辑映射
根据业务目的选择聚合函数

### 4. 性能考虑
避免产生笛卡尔积等性能问题

## 使用示例

```python
# 创建工具
tool = OperationSelectionTool()

# 为场景选择操作
scenario = {
    "category": "销售分析",
    "difficulty": "medium",
    "tables": ["orders", "products", "categories"],
    "business_purpose": "分析各类别产品销售额"
}

operations = tool.run({
    "scenario": scenario,
    "memory": memory  # 使用记忆中的schema_info
})

print(f"选择的操作: {operations['operations']}")
print(f"JOIN类型: {operations['join_type']}")
print(f"聚合函数: {operations['aggregations']}")

# 使用操作序列指导 SQL 生成
for step in operations['operation_sequence']:
    print(step)
```

## 高级特性

### 1. 操作优化
```python
# 基于表大小优化 JOIN 顺序
def optimize_join_order(tables: List[str], table_stats: Dict) -> List[str]:
    """根据表统计信息优化 JOIN 顺序"""
    pass
```

### 2. 操作验证
```python
# 验证操作组合的合理性
def validate_operations(operations: List[str], schema: Dict) -> bool:
    """检查操作组合是否可行"""
    pass
```

## 注意事项

1. 基于预定义规则，不依赖 LLM
2. 规则可根据领域定制
3. 考虑性能影响
4. 生成的操作组合指导后续 SQL 生成

---

相关文档：
- [ScenarioTool](./ScenarioTool.md)
- [QuestionGenerationTool](./QuestionGenerationTool.md)
- [SQLGenerationTool](./SQLGenerationTool.md)