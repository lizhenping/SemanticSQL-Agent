# ColumnMeaningTool API 文档

列业务含义分析工具，深入分析每个列的业务含义和使用场景。

## 类定义

```python
from langchain.tools import BaseTool
from typing import Dict, Any, List, Optional
from semanticsql_agent.tools.analysis_tools import ColumnMeaningTool

class ColumnMeaningTool(BaseTool):
    """
    列含义分析工具
    
    基于领域知识和字段分类，深入分析每个列的业务含义。
    
    Attributes:
        name: "column_meaning"
        description: "分析数据库列的业务含义"
    """
```

## 构造函数

```python
def __init__(self, llm: ChatOpenAI):
    """
    初始化列含义分析工具
    
    Args:
        llm: LangChain 的 ChatOpenAI 实例
    """
```

## 核心方法

### _run

```python
def _run(
    self,
    schema_info: Dict[str, Any],
    domain_info: Dict[str, Any],
    field_classification: Dict[str, Any],
    focus_columns: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    执行列含义分析
    
    Args:
        schema_info: 数据库结构信息
        domain_info: 领域分析结果
        field_classification: 字段分类结果
        focus_columns: 可选，只分析特定列
    
    Returns:
        Dict[str, Any]: 列含义分析结果
    
    Return Format:
        ```python
        {
            "column_meanings": {
                "orders.total_amount": {
                    "business_meaning": "订单总金额，包含商品价格、运费和税费",
                    "calculation_logic": "商品总价 + 运费 + 税费 - 折扣",
                    "usage_scenarios": [
                        "计算销售额统计",
                        "生成财务报表",
                        "分析客户消费水平"
                    ],
                    "constraints": {
                        "min_value": 0,
                        "currency": "CNY",
                        "precision": 2
                    },
                    "related_columns": ["subtotal", "shipping_fee", "tax", "discount"]
                },
                "customers.vip_level": {
                    "business_meaning": "客户VIP等级",
                    "value_mapping": {
                        "0": "普通会员",
                        "1": "银卡会员",
                        "2": "金卡会员",
                        "3": "钻石会员"
                    },
                    "usage_scenarios": [
                        "差异化营销策略",
                        "优惠折扣计算",
                        "客户价值分析"
                    ],
                    "business_rules": [
                        "根据累计消费金额自动升级",
                        "享受不同的折扣权益"
                    ]
                }
            }
        }
        ```
    """
```

## 分析维度

### 1. 业务含义
- 字段的实际业务意义
- 在业务流程中的作用
- 与其他字段的关系

### 2. 数据特征
- 值域范围
- 数据分布
- 约束条件

### 3. 使用场景
- 常见查询场景
- 计算逻辑
- 业务规则

## 使用示例

```python
# 创建工具
tool = ColumnMeaningTool(llm=ChatOpenAI(model="Qwen"))

# 分析所有列
result = tool.run({
    "schema_info": schema_info,
    "domain_info": domain_info,
    "field_classification": field_classification
})

# 只分析特定列
result = tool.run({
    "schema_info": schema_info,
    "domain_info": domain_info,
    "field_classification": field_classification,
    "focus_columns": ["orders.total_amount", "customers.vip_level"]
})

# 使用分析结果
amount_meaning = result["column_meanings"]["orders.total_amount"]
print(f"含义: {amount_meaning['business_meaning']}")
print(f"计算逻辑: {amount_meaning['calculation_logic']}")
```

## 提示词模板

```python
COLUMN_MEANING_PROMPT = """
基于以下信息分析数据库列的业务含义：

领域：{domain}
表结构：{schema}
字段分类：{classification}

请为每个列提供：
1. 详细的业务含义说明
2. 计算逻辑（如适用）
3. 使用场景
4. 业务规则和约束
5. 相关列关系

返回 JSON 格式的分析结果。
"""
```

## 高级特性

### 1. 增量分析
```python
# 只分析新增或修改的列
tool.run({
    "focus_columns": ["orders.new_field"],
    "incremental": True
})
```

### 2. 领域特定分析
```python
# 使用领域特定的分析策略
tool.run({
    "analysis_strategy": "financial",  # 金融领域专用
    "include_compliance": True  # 包含合规性分析
})
```

## 注意事项

1. 依赖于前置分析结果
2. 可以增量更新分析
3. 支持领域特定的分析策略
4. 分析结果直接影响 SQL 生成质量

---

相关文档：
- [FieldClassificationTool](./FieldClassificationTool.md)
- [TableMeaningTool](./TableMeaningTool.md)
- [ERAnalysisTool](./ERAnalysisTool.md)