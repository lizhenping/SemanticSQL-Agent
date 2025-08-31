# TableMeaningTool API 文档

表业务含义分析工具，分析每个表的业务职责和在系统中的作用。

## 类定义

```python
from langchain.tools import BaseTool
from typing import Dict, Any, List, Optional
from semanticsql_agent.tools.analysis_tools import TableMeaningTool

class TableMeaningTool(BaseTool):
    """
    表含义分析工具
    
    分析数据库表的业务职责、数据生命周期和使用模式。
    
    Attributes:
        name: "table_meaning"
        description: "分析数据库表的业务含义和职责"
    """
```

## 构造函数

```python
def __init__(self, llm: ChatOpenAI):
    """
    初始化表含义分析工具
    
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
    column_meanings: Dict[str, Any],
    focus_tables: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    执行表含义分析
    
    Args:
        schema_info: 数据库结构信息
        domain_info: 领域分析结果
        column_meanings: 列含义分析结果
        focus_tables: 可选，只分析特定表
    
    Returns:
        Dict[str, Any]: 表含义分析结果
    
    Return Format:
        ```python
        {
            "table_meanings": {
                "orders": {
                    "business_purpose": "存储客户订单信息",
                    "data_lifecycle": "订单创建 -> 支付 -> 发货 -> 完成/取消",
                    "core_entity": "订单",
                    "data_volume": "高频写入，中等读取",
                    "retention_policy": "永久保存，3年后归档",
                    "key_operations": [
                        "创建新订单",
                        "更新订单状态",
                        "查询订单历史"
                    ],
                    "relationships": {
                        "customers": "多对一，每个订单属于一个客户",
                        "order_items": "一对多，每个订单包含多个商品项"
                    },
                    "business_rules": [
                        "订单一旦创建不可删除",
                        "只有待支付订单可以取消",
                        "订单金额必须大于0"
                    ]
                },
                "inventory": {
                    "business_purpose": "管理商品库存信息",
                    "data_lifecycle": "入库 -> 销售/调拨 -> 盘点",
                    "core_entity": "库存",
                    "data_volume": "高频更新，高频读取",
                    "real_time_requirement": true,
                    "consistency_level": "强一致性",
                    "key_operations": [
                        "库存扣减",
                        "库存查询",
                        "库存预警"
                    ]
                }
            },
            "table_categories": {
                "transactional": ["orders", "payments", "shipments"],
                "master_data": ["customers", "products", "suppliers"],
                "reference": ["categories", "regions", "currencies"],
                "operational": ["inventory", "pricing"],
                "analytical": ["sales_summary", "customer_stats"]
            }
        }
        ```
    """
```

## 分析维度

### 1. 业务职责
- 表的核心业务功能
- 在业务流程中的位置
- 数据的业务价值

### 2. 数据特征
- 数据量级和增长模式
- 读写频率
- 实时性要求

### 3. 生命周期
- 数据产生方式
- 状态流转
- 保留策略

### 4. 关系网络
- 与其他表的关系
- 依赖关系
- 数据流向

## 表分类体系

- **transactional**: 事务型表（订单、支付）
- **master_data**: 主数据表（客户、产品）
- **reference**: 参考数据表（类别、地区）
- **operational**: 运营数据表（库存、价格）
- **analytical**: 分析汇总表（销售统计）

## 使用示例

```python
# 创建工具
tool = TableMeaningTool(llm=ChatOpenAI(model="Qwen"))

# 分析所有表
result = tool.run({
    "schema_info": schema_info,
    "domain_info": domain_info,
    "column_meanings": column_meanings
})

# 获取表的业务职责
order_meaning = result["table_meanings"]["orders"]
print(f"业务目的: {order_meaning['business_purpose']}")
print(f"数据生命周期: {order_meaning['data_lifecycle']}")

# 获取表分类
transactional_tables = result["table_categories"]["transactional"]
print(f"事务型表: {transactional_tables}")
```

## 提示词模板

```python
TABLE_MEANING_PROMPT = """
基于以下信息分析数据库表的业务含义：

领域：{domain}
表结构：{schema}
列含义：{column_meanings}

请为每个表提供：
1. 业务职责说明
2. 数据生命周期
3. 关键操作
4. 表间关系
5. 业务规则

并对表进行分类。

返回 JSON 格式的分析结果。
"""
```

## 高级特性

### 1. 关联分析
```python
# 分析表之间的业务关联
result = tool.run({
    "analyze_relationships": True,
    "relationship_depth": 2  # 分析二级关联
})
```

### 2. 性能建议
```python
# 基于使用模式提供索引建议
result = tool.run({
    "include_performance_hints": True
})
```

## 注意事项

1. 依赖列含义分析结果
2. 表分类影响查询策略
3. 生命周期分析帮助理解数据流
4. 可用于数据治理

---

相关文档：
- [ColumnMeaningTool](./ColumnMeaningTool.md)
- [ERAnalysisTool](./ERAnalysisTool.md)
- [SchemaExtractionTool](./SchemaExtractionTool.md)