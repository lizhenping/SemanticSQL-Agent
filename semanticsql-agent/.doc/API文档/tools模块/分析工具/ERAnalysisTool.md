# ERAnalysisTool API 文档

实体关系分析工具，分析表之间的关系和约束。

## 类定义

```python
from langchain.tools import BaseTool
from typing import Dict, Any, List
from semanticsql_agent.tools.analysis_tools import ERAnalysisTool

class ERAnalysisTool(BaseTool):
    """
    实体关系分析工具
    
    分析数据库中表之间的关系，包括外键、引用关系和业务关联。
    
    Attributes:
        name: "er_analysis"
        description: "分析数据库表之间的实体关系"
    """
```

## 构造函数

```python
def __init__(self, db_config: DatabaseConfig):
    """
    初始化 ER 分析工具
    
    Args:
        db_config: 数据库配置
    """
```

## 核心方法

### _run

```python
def _run(
    self,
    schema_info: Dict[str, Any],
    table_meanings: Dict[str, Any]
) -> Dict[str, Any]:
    """
    执行实体关系分析
    
    Args:
        schema_info: 数据库结构信息
        table_meanings: 表含义分析结果
    
    Returns:
        Dict[str, Any]: 实体关系分析结果
    
    Return Format:
        ```python
        {
            "relationships": [
                {
                    "name": "customer_orders",
                    "from_table": "customers",
                    "to_table": "orders",
                    "type": "one_to_many",
                    "from_column": "customer_id",
                    "to_column": "customer_id",
                    "constraint": "FK_orders_customers",
                    "cascade": "RESTRICT",
                    "business_meaning": "客户与订单的所属关系"
                },
                {
                    "name": "order_items",
                    "from_table": "orders",
                    "to_table": "order_items",
                    "type": "one_to_many",
                    "from_column": "order_id",
                    "to_column": "order_id",
                    "constraint": "FK_order_items_orders",
                    "cascade": "CASCADE",
                    "business_meaning": "订单与订单项的包含关系"
                }
            ],
            "entities": {
                "customers": {
                    "type": "master",
                    "key": "customer_id",
                    "relationships": ["customer_orders", "customer_addresses"],
                    "cardinality": "medium"
                },
                "orders": {
                    "type": "transactional",
                    "key": "order_id",
                    "relationships": ["customer_orders", "order_items", "order_payments"],
                    "cardinality": "high"
                }
            },
            "relationship_graph": {
                "nodes": ["customers", "orders", "order_items", "products"],
                "edges": [
                    ["customers", "orders"],
                    ["orders", "order_items"],
                    ["order_items", "products"]
                ]
            }
        }
        ```
    """
```

## 关系类型

### 基数关系
- **one_to_one**: 一对一关系
- **one_to_many**: 一对多关系
- **many_to_many**: 多对多关系（通过中间表）

### 约束类型
- **CASCADE**: 级联删除/更新
- **RESTRICT**: 限制删除/更新
- **SET NULL**: 设置为空
- **NO ACTION**: 无动作

## 分析功能

### 1. 外键分析
```python
# 获取所有外键关系
foreign_keys = result["relationships"]
for fk in foreign_keys:
    print(f"{fk['from_table']}.{fk['from_column']} -> {fk['to_table']}.{fk['to_column']}")
```

### 2. 关系路径查找
```python
# 查找两个表之间的关系路径
def find_join_path(from_table: str, to_table: str, relationships: List[Dict]) -> List[str]:
    """找到连接两个表的最短路径"""
    pass
```

### 3. 实体分类
```python
# 根据关系数量和类型对实体分类
entities = result["entities"]
master_entities = [e for e, info in entities.items() if info["type"] == "master"]
```

## 使用示例

```python
# 创建工具
tool = ERAnalysisTool(db_config=db_config)

# 执行分析
result = tool.run({
    "schema_info": schema_info,
    "table_meanings": table_meanings
})

# 使用关系信息生成 JOIN
relationships = result["relationships"]
customer_order_rel = next(r for r in relationships if r["name"] == "customer_orders")

join_sql = f"""
SELECT *
FROM {customer_order_rel['from_table']} t1
JOIN {customer_order_rel['to_table']} t2
ON t1.{customer_order_rel['from_column']} = t2.{customer_order_rel['to_column']}
"""
```

## 可视化支持

```python
# 生成 Mermaid 图
def generate_er_diagram(result: Dict) -> str:
    """
    生成 Mermaid ER 图
    
    Returns:
        str: Mermaid 格式的 ER 图定义
    """
    diagram = "erDiagram\n"
    for rel in result["relationships"]:
        diagram += f"    {rel['from_table']} ||--o{{ {rel['to_table']} : {rel['business_meaning']}\n"
    return diagram
```

## 注意事项

1. 需要数据库读取权限
2. 分析结果缓存在记忆中
3. 支持推断隐式关系
4. 可用于优化 JOIN 查询

---

相关文档：
- [SchemaExtractionTool](./SchemaExtractionTool.md)
- [TableMeaningTool](./TableMeaningTool.md)
- [SQLGenerationTool](../生成工具/SQLGenerationTool.md)