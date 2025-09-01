# DomainAnalysisTool API 文档

领域分析工具，通过分析数据库结构和内容推断业务领域。

## 类定义

```python
from langchain.tools import BaseTool
from typing import Dict, Any, Optional
from semanticsql_agent.tools.analysis_tools import DomainAnalysisTool

class DomainAnalysisTool(BaseTool):
    """
    领域分析工具
    
    分析数据库的表名、字段名和数据特征，推断业务领域类型。
    
    Attributes:
        name: "domain_analysis"
        description: "分析数据库的业务领域"
    """
```

## 构造函数

```python
def __init__(self, llm: ChatOpenAI):
    """
    初始化领域分析工具
    
    Args:
        llm: LangChain 的 ChatOpenAI 实例
    """
```

## 核心方法

### _run

```python
def _run(
    self,
    memory: Dict[str, Any]
) -> Dict[str, Any]:
    """
    执行领域分析
    
    功能描述：
        基于数据库结构信息分析业务领域，识别主要的业务实体、流程和术语。
        通过分析表名、字段名和表关系，推断出数据库所属的业务领域。
    
    Args:
        memory: 包含数据库分析结果的记忆，使用其中的 schema_info
    
    Returns:
        Dict[str, Any]: 领域分析结果
    
    Return Format:
        ```python
        {
            "domain": "电商",  # 主要领域
            "sub_domains": ["订单管理", "库存管理", "客户管理"],
            "confidence": 0.85,
            "key_entities": ["订单", "产品", "客户", "库存"],
            "business_processes": ["下单", "支付", "发货", "退款"],
            "industry_terms": {
                "SKU": "库存单位",
                "order": "订单",
                "customer": "客户"
            }
        }
        ```
    """
```

## 分析流程

1. **表名分析**：识别常见的业务实体表
2. **字段分析**：识别业务相关的字段类型
3. **关系分析**：理解表之间的业务关系
4. **模式匹配**：匹配已知的业务领域模式

## 使用示例

```python
# 创建工具
tool = DomainAnalysisTool(llm=ChatOpenAI(model="Qwen"))

# 执行分析
result = tool.run({
    "schema_info": {
        "tables": ["orders", "products", "customers"],
        "columns": {
            "orders": ["order_id", "customer_id", "total_amount"],
            "products": ["product_id", "name", "price", "stock"]
        }
    }
})

print(f"Domain: {result['domain']}")
print(f"Sub-domains: {result['sub_domains']}")
```

## 提示词模板

```python
DOMAIN_ANALYSIS_PROMPT = """
分析以下数据库结构，推断其业务领域：

数据库结构：
{schema_info}

请分析：
1. 主要业务领域
2. 子领域
3. 核心业务实体
4. 主要业务流程
5. 行业术语映射

返回 JSON 格式的分析结果。
"""
```

## 错误处理

```python
from semanticsql_agent.models.exceptions import ToolExecutionError

try:
    result = tool.run({"memory": memory})
except ToolExecutionError as e:
    print(f"领域分析失败 [{e.error_code}]: {e.message}")
    # 可能需要检查schema_info是否完整
```

## 注意事项

1. 领域分析是后续工具的基础
2. 分析结果会存储在记忆中
3. 支持多种常见业务领域
4. 可以识别混合领域

---

相关文档：
- [SchemaExtractionTool](./SchemaExtractionTool.md)
- [FieldClassificationTool](./FieldClassificationTool.md)