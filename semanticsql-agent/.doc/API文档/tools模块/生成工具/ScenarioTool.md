# ScenarioTool API 文档

场景生成工具，基于预定义模板生成查询场景。

## 类定义

```python
from langchain.tools import BaseTool
from typing import Dict, Any, List
from semanticsql_agent.tools.generation_tools import ScenarioTool

class ScenarioTool(BaseTool):
    """
    场景生成工具
    
    基于预定义的场景模板和数据库结构生成查询场景。
    
    Attributes:
        name: "scenario_generation"
        description: "生成查询场景"
    """
```

## 构造函数

```python
def __init__(self):
    """
    初始化场景生成工具
    
    加载预定义的场景模板库。
    """
```

## 核心方法

### _run

```python
def _run(
    self,
    schema_info: Dict[str, Any],
    domain_info: Dict[str, Any],
    count: int = 10,
    difficulty_distribution: Dict[str, float] = None
) -> List[Dict[str, Any]]:
    """
    生成查询场景
    
    Args:
        schema_info: 数据库结构信息
        domain_info: 领域分析结果
        count: 生成场景数量
        difficulty_distribution: 难度分布，如 {"easy": 0.3, "medium": 0.5, "hard": 0.2}
    
    Returns:
        List[Dict[str, Any]]: 生成的场景列表
    
    Return Format:
        ```python
        [
            {
                "id": "scenario_001",
                "category": "销售分析",
                "business_purpose": "分析产品销售趋势",
                "description": "统计最近30天各产品类别的销售额和销量",
                "difficulty": "medium",
                "tables": ["orders", "order_items", "products", "categories"],
                "suggested_operations": ["JOIN", "GROUP BY", "AGGREGATE", "DATE_FILTER"]
            }
        ]
        ```
    """
```

## 预定义场景模板

### 电商领域
```python
ECOMMERCE_SCENARIOS = {
    "sales_analysis": {
        "templates": [
            {
                "category": "销售分析",
                "patterns": [
                    "统计{time_period}的{metric}",
                    "分析{dimension}的{metric}分布",
                    "比较{dimension1}和{dimension2}的{metric}"
                ],
                "variables": {
                    "time_period": ["今天", "本周", "本月", "最近30天"],
                    "metric": ["销售额", "订单数", "客单价"],
                    "dimension": ["产品类别", "客户地区", "支付方式"]
                }
            }
        ]
    }
}
```

### 难度级别定义
- **easy**: 单表查询，简单条件
- **medium**: 2-3表连接，聚合统计
- **hard**: 多表连接，复杂计算
- **expert**: 窗口函数，递归查询

## 使用示例

```python
# 创建工具
tool = ScenarioTool()

# 生成场景（默认分布）
scenarios = tool.run({
    "schema_info": schema_info,
    "domain_info": {"domain": "电商"},
    "count": 20
})

# 自定义难度分布
scenarios = tool.run({
    "schema_info": schema_info,
    "domain_info": {"domain": "电商"},
    "count": 50,
    "difficulty_distribution": {
        "easy": 0.2,
        "medium": 0.5,
        "hard": 0.25,
        "expert": 0.05
    }
})

# 处理生成的场景
for scenario in scenarios:
    print(f"场景: {scenario['description']}")
    print(f"难度: {scenario['difficulty']}")
    print(f"涉及表: {scenario['tables']}")
```

## 场景生成策略

### 1. 模板匹配
根据领域和表结构选择合适的模板

### 2. 变量填充
根据实际数据库内容填充模板变量

### 3. 复杂度控制
根据难度要求选择操作组合

### 4. 多样性保证
避免生成重复或过于相似的场景

## 扩展场景模板

```python
# 添加自定义场景模板
def add_custom_scenarios(domain: str, scenarios: Dict):
    """
    添加领域特定的场景模板
    
    Args:
        domain: 领域名称
        scenarios: 场景模板定义
    """
    pass
```

## 注意事项

1. 场景基于预定义模板，不依赖 LLM
2. 支持多种业务领域
3. 可扩展场景模板库
4. 生成结果的多样性和覆盖度有保证

---

相关文档：
- [OperationSelectionTool](./OperationSelectionTool.md)
- [QuestionGenerationTool](./QuestionGenerationTool.md)