# QuestionGenerationTool API 文档

问题生成工具，根据场景和操作生成自然语言问题。

## 类定义

```python
from langchain.tools import BaseTool
from typing import Dict, Any
from semanticsql_agent.tools.generation_tools import QuestionGenerationTool

class QuestionGenerationTool(BaseTool):
    """
    问题生成工具
    
    根据场景、操作和数据库信息生成自然语言问题。
    
    Attributes:
        name: "question_generation"
        description: "生成自然语言查询问题"
    """
```

## 构造函数

```python
def __init__(self, llm: ChatOpenAI):
    """
    初始化问题生成工具
    
    Args:
        llm: LangChain 的 ChatOpenAI 实例
    """
```

## 核心方法

### _run

```python
def _run(
    self,
    scenario: Dict[str, Any],
    operations: Dict[str, Any],
    memory: Dict[str, Any]
) -> Dict[str, Any]:
    """
    生成自然语言问题
    
    Args:
        scenario: 查询场景
        operations: 选定的操作
        memory: 完整的数据库分析记忆（包含schema_info、领域、字段含义等）
    
    Returns:
        Dict[str, Any]: 生成的问题
    
    Return Format:
        ```python
        {
            "question": "请统计2024年1月各产品类别的销售总额，并按销售额降序排列显示前10个类别",
            "question_type": "analytical",
            "key_elements": {
                "time_range": "2024年1月",
                "metric": "销售总额",
                "dimension": "产品类别",
                "operation": "统计并排序",
                "limit": 10
            },
            "expected_columns": ["category_name", "total_sales"],
            "natural_language_hints": [
                "需要连接订单和产品表",
                "按类别分组统计",
                "计算销售总额"
            ]
        }
        ```
    """
```

## 生成策略

### 1. 模板填充
基于场景类型选择问题模板

### 2. 业务术语使用
利用记忆中的领域知识使用准确的业务术语

### 3. 复杂度匹配
根据操作复杂度生成相应复杂度的问题

### 4. 自然性优化
确保生成的问题符合自然语言习惯

## 提示词模板

```python
QUESTION_GENERATION_PROMPT = """
基于以下信息生成自然语言查询问题：

场景描述：{scenario_description}
业务目的：{business_purpose}
涉及的表：{tables}
操作类型：{operations}
领域知识：{domain_info}

要求：
1. 使用自然、流畅的中文表达
2. 包含明确的查询意图
3. 使用领域相关的业务术语
4. 符合实际业务场景

生成一个清晰、具体的查询问题。
"""
```

## 使用示例

```python
# 创建工具
tool = QuestionGenerationTool(llm=ChatOpenAI(model="Qwen"))

# 生成问题
result = tool.run({
    "scenario": {
        "category": "销售分析",
        "business_purpose": "分析销售趋势",
        "tables": ["orders", "products"]
    },
    "operations": {
        "operations": ["JOIN", "GROUP BY", "SUM"],
        "aggregations": ["SUM", "COUNT"]
    },
    "memory": memory  # 包含所有数据库分析结果
})

print(f"生成的问题: {result['question']}")
print(f"关键要素: {result['key_elements']}")
```

## 问题类型

- **simple**: 简单查询（单表、基础条件）
- **analytical**: 分析型查询（聚合、分组）
- **comparative**: 对比型查询（多维度对比）
- **trend**: 趋势型查询（时间序列分析）

## 质量控制

### 1. 完整性检查
确保问题包含所有必要信息

### 2. 歧义检测
避免生成有歧义的问题

### 3. 可执行性验证
确保问题可以转换为 SQL

## 注意事项

1. 充分利用记忆中的业务知识
2. 生成的问题应该自然、清晰
3. 避免过于技术化的表达
4. 确保与场景和操作一致

---

相关文档：
- [ScenarioTool](./ScenarioTool.md)
- [OperationSelectionTool](./OperationSelectionTool.md)
- [SQLGenerationTool](./SQLGenerationTool.md)