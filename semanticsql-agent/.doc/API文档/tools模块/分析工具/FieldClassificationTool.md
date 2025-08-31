# FieldClassificationTool API 文档

字段语义分类工具，对数据库字段进行语义分类。

## 类定义

```python
from langchain.tools import BaseTool
from typing import Dict, Any, List
from semanticsql_agent.tools.analysis_tools import FieldClassificationTool

class FieldClassificationTool(BaseTool):
    """
    字段分类工具
    
    对数据库中的字段进行语义分类，识别字段的业务含义。
    
    Attributes:
        name: "field_classification"
        description: "对数据库字段进行语义分类"
    """
```

## 构造函数

```python
def __init__(self, llm: ChatOpenAI):
    """
    初始化字段分类工具
    
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
    domain_info: Dict[str, Any]
) -> Dict[str, Any]:
    """
    执行字段分类
    
    Args:
        schema_info: 数据库结构信息
        domain_info: 领域分析结果
    
    Returns:
        Dict[str, Any]: 字段分类结果
    
    Return Format:
        ```python
        {
            "classifications": {
                "orders": {
                    "order_id": {
                        "type": "identifier",
                        "business_type": "订单编号",
                        "nullable": false
                    },
                    "created_at": {
                        "type": "timestamp",
                        "business_type": "创建时间",
                        "nullable": false
                    },
                    "total_amount": {
                        "type": "measure",
                        "business_type": "订单金额",
                        "nullable": false
                    }
                },
                "customers": {
                    "email": {
                        "type": "contact",
                        "business_type": "邮箱地址",
                        "nullable": true
                    }
                }
            },
            "field_types": {
                "identifier": ["order_id", "customer_id", "product_id"],
                "measure": ["total_amount", "price", "quantity"],
                "timestamp": ["created_at", "updated_at"],
                "contact": ["email", "phone"],
                "descriptive": ["name", "description"],
                "status": ["order_status", "payment_status"]
            }
        }
        ```
    """
```

## 字段类型分类

### 基础类型
- **identifier**: 标识符字段（主键、外键）
- **measure**: 度量字段（金额、数量、分数）
- **timestamp**: 时间戳字段
- **descriptive**: 描述性字段（名称、说明）
- **status**: 状态字段（订单状态、支付状态）
- **contact**: 联系方式字段

### 业务类型
根据领域动态识别，如：
- 电商：订单号、SKU、库存量
- 金融：账户号、交易额、利率
- 社交：用户名、点赞数、关注数

## 使用示例

```python
# 创建工具
tool = FieldClassificationTool(llm=ChatOpenAI(model="Qwen"))

# 执行分类
result = tool.run({
    "schema_info": schema_info,
    "domain_info": {
        "domain": "电商",
        "key_entities": ["订单", "产品", "客户"]
    }
})

# 获取特定类型的字段
identifiers = result["field_types"]["identifier"]
measures = result["field_types"]["measure"]
```

## 提示词模板

```python
FIELD_CLASSIFICATION_PROMPT = """
基于以下信息对数据库字段进行分类：

数据库结构：{schema_info}
业务领域：{domain}

请对每个字段进行：
1. 基础类型分类（identifier/measure/timestamp等）
2. 业务类型识别
3. 重要性评估

返回 JSON 格式的分类结果。
"""
```

## 注意事项

1. 依赖于领域分析结果
2. 分类结果影响 SQL 生成策略
3. 支持自定义字段类型
4. 可用于数据质量检查

---

相关文档：
- [DomainAnalysisTool](./DomainAnalysisTool.md)
- [ColumnMeaningTool](./ColumnMeaningTool.md)