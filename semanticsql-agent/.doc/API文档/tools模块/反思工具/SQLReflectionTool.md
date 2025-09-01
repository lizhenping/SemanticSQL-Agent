# SQLReflectionTool API 文档

SQL 执行反思工具，评估 SQL 质量并诊断问题。

## 类定义

```python
from langchain.tools import BaseTool
from typing import Dict, Any, Optional
from semanticsql_agent.tools.reflection_tools import SQLReflectionTool

class SQLReflectionTool(BaseTool):
    """
    SQL 反思工具
    
    综合评估 SQL 执行结果，分析问题根源，提出改进建议。
    
    Attributes:
        name: "sql_reflection"
        description: "反思 SQL 执行结果并诊断问题"
    """
```

## 构造函数

```python
def __init__(self, llm: ChatOpenAI):
    """
    初始化 SQL 反思工具
    
    Args:
        llm: LangChain 的 ChatOpenAI 实例
    """
```

## 核心方法

### _run

```python
def _run(
    self,
    sql: str,
    execution_result: Dict[str, Any],
    question: str,
    scenario: Dict[str, Any],
    operations: Dict[str, Any],
    memory_usage: Dict[str, Any]
) -> Dict[str, Any]:
    """
    执行反思分析
    
    Args:
        sql: 生成的 SQL 语句
        execution_result: SQL 执行结果
        question: 原始自然语言问题
        scenario: 使用的场景
        operations: 选择的操作
        memory_usage: 记忆使用情况
    
    Returns:
        Dict[str, Any]: 反思结果
    
    Return Format:
        ```python
        {
            "needs_revision": false,
            "quality_score": 0.85,
            "issues": [],
            "evaluation": {
                "correctness": {
                    "score": 0.9,
                    "reason": "SQL correctly implements the query logic"
                },
                "performance": {
                    "score": 0.8,
                    "concerns": ["Missing index on date column"]
                },
                "completeness": {
                    "score": 0.85,
                    "missing": []
                }
            },
            "problem_source": null,  # 问题来源：question_generation/sql_generation/memory_usage/database_analysis
            "root_cause_analysis": {
                "component": null,  # 出问题的组件/工具
                "reason": null,     # 问题原因
                "affected_tool": null  # 需要重新执行的工具
            },
            "recommended_action": {
                "tool_to_call": null,  # 建议调用的工具：如 sql_generation, er_analysis 等
                "reason": null,        # 为什么需要调用这个工具
                "parameters_hint": {}  # 调用时的参数建议
            },
            "suggestions": [
                "Consider adding index on orders.created_at"
            ]
        }
        ```
    """
```

## 评估维度

### 1. 正确性评估
- SQL 是否正确实现了问题意图
- 结果是否符合预期
- 业务逻辑是否准确

### 2. 性能评估
- 查询效率
- 索引使用
- 潜在性能瓶颈

### 3. 完整性评估
- 是否遗漏重要信息
- 边界条件处理
- 异常情况考虑

### 4. 记忆使用评估
- 是否充分利用数据库分析结果
- 字段理解是否准确
- 关系使用是否恰当

## 问题诊断

### 问题类型识别
```python
PROBLEM_TYPES = {
    "execution_error": "SQL 执行失败",
    "semantic_mismatch": "SQL 未正确实现意图",
    "question_ambiguity": "问题描述不清",
    "memory_misuse": "记忆信息使用不当",
    "analysis_flaw": "数据库分析有误"
}
```

### 根因分析
```python
def analyze_root_cause(self, issues: List[Dict]) -> str:
    """
    分析问题根本原因
    
    Returns:
        问题源头：question_generation/sql_generation/memory_usage/database_analysis
    """
```

## 反思结果示例

### 示例1：SQL生成错误
```python
# 当SQL使用了错误的表名
{
    "needs_revision": true,
    "quality_score": 0.3,
    "issues": ["Table 'orders' doesn't exist"],
    "problem_source": "sql_generation",
    "root_cause_analysis": {
        "component": "sql_generation",
        "reason": "使用了orders表，但schema中只有order_info表",
        "affected_tool": "sql_generation"
    },
    "recommended_action": {
        "tool_to_call": "sql_generation",
        "reason": "需要使用正确的表名重新生成SQL",
        "parameters_hint": {
            "focus": "使用memory中的schema_info获取正确表名"
        }
    }
}
```

### 示例2：数据库分析不足
```python
# 当缺少必要的表关系导致SQL错误
{
    "needs_revision": true,
    "quality_score": 0.5,
    "issues": ["Missing JOIN between orders and customers"],
    "problem_source": "database_analysis", 
    "root_cause_analysis": {
        "component": "er_analysis",
        "reason": "ER分析未能识别orders和customers的关系",
        "affected_tool": "er_analysis"
    },
    "recommended_action": {
        "tool_to_call": "er_analysis",
        "reason": "需要重新分析表关系",
        "parameters_hint": {
            "focus_tables": ["orders", "customers"]
        }
    }
}
```

## 使用示例

### 成功案例反思
```python
# 创建工具
tool = SQLReflectionTool(llm=ChatOpenAI(model="Qwen"))

# 执行反思
result = tool.run({
    "sql": "SELECT COUNT(*) FROM orders WHERE status = 'completed'",
    "execution_result": {
        "success": True,
        "data": [{"count": 150}],
        "execution_time": 0.05
    },
    "question": "统计已完成的订单数量",
    "scenario": {...},
    "operations": {...},
    "memory_usage": {
        "schema": {...},
        "domain": {...}
    }
})

print(f"需要修正: {result['needs_revision']}")
print(f"质量分数: {result['quality_score']}")
```

### 问题案例反思
```python
# 执行失败的反思
result = tool.run({
    "sql": "SELECT * FROM order WHERE ...",  # 表名错误
    "execution_result": {
        "success": False,
        "error": "Table 'order' doesn't exist"
    },
    "question": "查询订单信息",
    "scenario": {...},
    "operations": {...},
    "memory_usage": {...}
})

# 分析结果
if result["needs_revision"]:
    print(f"问题源头: {result['problem_source']}")
    print(f"根本原因: {result['root_cause']}")
    for issue in result["issues"]:
        print(f"- {issue}")
```

## 反思决策树

```python
def make_revision_decision(reflection_result: Dict) -> Dict[str, Any]:
    """
    基于反思结果做出修正决策
    
    Returns:
        {
            "action": "revise_sql",  # 或 revise_question, update_analysis
            "target": "sql_generation",
            "reason": "表名使用错误"
        }
    """
```

## 提示词模板

```python
REFLECTION_PROMPT = """
请反思以下 SQL 执行结果：

原始问题：{question}
生成的 SQL：{sql}
执行结果：{execution_result}

使用的记忆信息：
- 数据库结构：{schema_summary}
- 领域知识：{domain_info}
- 字段含义：{field_meanings}

请评估：
1. SQL 是否正确实现了问题意图？
2. 是否充分利用了记忆信息？
3. 执行结果是否符合预期？
4. 是否存在性能或逻辑问题？

如果存在问题，请分析根本原因。
"""
```

## 注意事项

1. 综合评估整个生成链路
2. 不仅看执行结果，还要看过程
3. 记忆使用情况是重要评估指标
4. 提供可操作的改进建议

---

相关文档：
- [SequentialThinkingTool](../思考工具/SequentialThinkingTool.md)
- [SQLGenerationTool](../生成工具/SQLGenerationTool.md)