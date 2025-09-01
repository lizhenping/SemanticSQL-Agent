# ScenarioTool API 文档

场景生成工具，从预定义模板中选择查询场景。

## 类定义

```python
from langchain.tools import BaseTool
from typing import Dict, Any, List
from semanticsql_agent.tools.generation_tools import ScenarioTool

class ScenarioTool(BaseTool):
    """
    场景生成工具
    
    基于预定义的场景模板和数据库结构选择合适的查询场景。
    
    Attributes:
        name: "scenario_tool"
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
    memory: Dict[str, Any],
    iteration: int = 0
) -> Dict[str, Any]:
    """
    选择一个查询场景
    
    功能描述：
        从预定义的场景模板库中选择一个适合当前数据库的查询场景。
        通过轮转机制确保场景的多样性，为生成多样化的训练数据奠定基础。
    
    Args:
        memory: 数据库分析记忆
            - 使用 memory["db_analysis"]["schema_info"] 验证场景所需的表
            - 使用 memory["db_analysis"]["domain_analysis"] 选择相关场景
        iteration: 当前迭代次数，用于场景轮转（从0开始）
    
    Returns:
        Dict[str, Any]: 选中的场景
    
    Return Format:
        ```python
        {
            "id": "scenario_001",
            "category": "销售分析",
            "business_purpose": "分析产品销售趋势",
            "description": "统计最近30天各产品类别的销售额和销量",
            "difficulty": "medium",
            "tables": ["orders", "order_items", "products", "categories"],
            "suggested_operations": ["JOIN", "GROUP BY", "AGGREGATE", "DATE_FILTER"]
        }
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

# 在问题生成循环中使用
for i in range(100):  # 生成100个问题
    # 选择一个场景
    scenario = tool.run({
        "memory": memory,  # 传入完整的记忆
        "iteration": i     # 用于场景轮转
    })
    
    print(f"选中场景: {scenario['description']}")
    print(f"难度: {scenario['difficulty']}")
    print(f"涉及表: {scenario['tables']}")
    
    # 继续后续的操作选择、问题生成等步骤...
```

## 场景选择策略

### 1. 轮转策略
根据迭代次数轮转使用不同的预定义场景

### 2. 领域匹配
选择与数据库领域相符的场景模板

### 3. 复杂度平衡
确保不同难度的场景均匀分布

### 4. 表覆盖
尽可能覆盖数据库中的所有重要表

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
2. 每次调用返回一个场景，不是批量返回
3. 通过迭代参数实现场景轮转
4. 支持多种业务领域的场景模板

---

相关文档：
- [OperationSelectionTool](./OperationSelectionTool.md)
- [QuestionGenerationTool](./QuestionGenerationTool.md)