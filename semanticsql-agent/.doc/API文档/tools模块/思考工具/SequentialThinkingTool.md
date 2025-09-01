# SequentialThinkingTool API 文档

深度思考工具，分析问题源头并制定修正策略。

## 类定义

```python
from langchain.tools import BaseTool
from typing import Dict, Any, List
from semanticsql_agent.tools.thinking_tools import SequentialThinkingTool

class SequentialThinkingTool(BaseTool):
    """
    顺序思考工具
    
    深入分析反思结果，确定问题根源，制定精确的修正策略。
    
    Attributes:
        name: "sequential_thinking"
        description: "深度分析问题并制定修正策略"
    """
```

## 构造函数

```python
def __init__(self, llm: ChatOpenAI):
    """
    初始化思考工具
    
    Args:
        llm: LangChain 的 ChatOpenAI 实例
    """
```

## 核心方法

### _run

```python
def _run(
    self,
    problem: List[str],
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    执行深度思考
    
    Args:
        problem: 反思工具识别的问题列表
        context: 完整的执行上下文
            - scenario: 场景信息
            - operations: 操作选择
            - question: 生成的问题
            - sql: 生成的 SQL
            - execution: 执行结果
            - memory: 记忆信息
    
    Returns:
        Dict[str, Any]: 修正策略
    
    Return Format:
        ```python
        {
            "problem_step": "sql_generation",  # 问题所在步骤
            "problem_type": "memory_misuse",   # 问题类型
            "root_cause": "未正确使用表关系信息导致 JOIN 错误",
            "fix_strategy": {
                "action": "regenerate",        # 修正动作
                "target": "sql_generation",    # 目标步骤
                "requirements": [
                    "使用正确的表关系",
                    "参考 er_analysis 中的外键信息"
                ],
                "memory_hints": {
                    "focus_on": ["er_analysis", "table_meanings"],
                    "key_info": "orders 和 customers 通过 customer_id 关联"
                }
            },
            "confidence": 0.9
        }
        ```
    """
```

## 思考策略

### 1. 问题定位
- 分析错误发生在哪个步骤
- 识别问题的具体类型
- 追溯因果关系链

### 2. 根因分析
```python
PROBLEM_STEPS = {
    "question_generation": "问题生成不当",
    "sql_generation": "SQL 生成错误",
    "memory_usage": "记忆使用不当",
    "database_analysis": "数据库分析有误"
}

PROBLEM_TYPES = {
    "syntax_error": "语法错误",
    "semantic_error": "语义错误",
    "memory_misuse": "记忆信息使用不当",
    "incomplete_analysis": "分析不完整",
    "ambiguous_intent": "意图不明确"
}
```

### 3. 修正策略制定
- **重新生成**：只重新执行出错步骤
- **更新分析**：重新运行特定分析工具
- **调整参数**：修改生成参数或提示

## 使用示例

### 基本使用
```python
# 创建工具
tool = SequentialThinkingTool(llm=ChatOpenAI(model="Qwen"))

# 执行思考
result = tool.run({
    "problem": [
        "SQL 中使用了错误的表名",
        "未能识别 orders 表的正确名称"
    ],
    "context": {
        "scenario": {...},
        "operations": {...},
        "question": "查询订单信息",
        "sql": "SELECT * FROM order",  # 错误：应该是 orders
        "execution": {"success": False, "error": "Table not found"},
        "memory": {
            "schema_info": {"tables": ["orders", "customers"]},
            "table_meanings": {...}
        }
    }
})

# 使用修正策略
if result["problem_step"] == "sql_generation":
    print(f"需要重新生成 SQL")
    print(f"原因: {result['root_cause']}")
    print(f"要求: {result['fix_strategy']['requirements']}")
```

### 复杂案例
```python
# 记忆使用问题
result = tool.run({
    "problem": [
        "JOIN 条件不正确",
        "未使用正确的外键关系"
    ],
    "context": {
        "sql": "SELECT * FROM orders o JOIN customers c ON o.id = c.id",
        "memory": {
            "er_analysis": {
                "relationships": [
                    {
                        "from_table": "orders",
                        "to_table": "customers",
                        "from_column": "customer_id",
                        "to_column": "customer_id"
                    }
                ]
            }
        }
    }
})

# 结果指导修正
fix_strategy = result["fix_strategy"]
if fix_strategy["action"] == "regenerate":
    # 使用提供的记忆提示重新生成
    memory_hints = fix_strategy["memory_hints"]
    print(f"Focus on: {memory_hints['focus_on']}")
    print(f"Key info: {memory_hints['key_info']}")
```

## 决策逻辑

### 修正动作类型
1. **regenerate**: 重新生成（问题、SQL）
2. **reanalyze**: 重新分析（特定分析工具）
3. **adjust**: 调整参数或策略
4. **clarify**: 需要澄清意图

### 修正范围
- **局部修正**：只修改特定部分
- **级联修正**：需要更新后续步骤
- **全局修正**：需要重新分析

## 提示词模板

```python
THINKING_PROMPT = """
基于以下信息进行深度思考：

识别的问题：
{problems}

执行上下文：
- 场景：{scenario}
- 问题：{question}
- SQL：{sql}
- 错误：{error}

可用记忆：
- 数据库结构：{schema}
- 领域分析：{domain}
- 关系分析：{relationships}

请分析：
1. 问题发生在哪个步骤？
2. 根本原因是什么？
3. 如何修正这个问题？
4. 需要使用哪些记忆信息？

输出精确的修正策略。
"""
```

## 高级功能

### 多步骤推理
```python
def multi_step_reasoning(self, problem: Dict) -> List[Dict]:
    """
    执行多步骤推理
    
    Returns:
        推理步骤链
    """
```

### 置信度评估
```python
def evaluate_confidence(self, strategy: Dict) -> float:
    """
    评估修正策略的置信度
    
    Returns:
        0-1 之间的置信度分数
    """
```

## 注意事项

1. 专注于找到真正的问题根源
2. 提供具体可执行的修正策略
3. 充分利用上下文信息
4. 避免过度修正

---

相关文档：
- [SQLReflectionTool](../反思工具/SQLReflectionTool.md)
- [记忆管理](../../agent模块/记忆管理-API.md)