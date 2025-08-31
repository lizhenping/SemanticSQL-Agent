# SequentialThinkingTool API 文档

## 概述
`SequentialThinkingTool` 是用于结构化顺序思考和分析的工具。它通过预定义或动态生成的思考步骤，对复杂问题进行深入分析，帮助智能体做出更准确的决策。

## 类定义
```python
class SequentialThinkingTool(BaseTool):
    """用于结构化分析的顺序思考工具"""
```

## 工具属性

- **名称**: `sequential_thinking`
- **类别**: `thinking`
- **描述**: 执行结构化的顺序思考和分析

## 参数定义

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|-------|------|------|--------|------|
| context | object | 是 | - | 当前上下文信息，包括已分析的数据库结构、领域信息等 |
| problem | string | 是 | - | 需要分析和思考的问题或情况 |
| thinking_steps | array | 否 | None | 预定义的思考步骤（可选） |

## 数据模型

### 输入模型
```python
class SequentialThinkingInput(ToolInput):
    context: Dict[str, Any]      # 上下文信息
    problem: str                 # 问题描述
    thinking_steps: Optional[List[str]]  # 思考步骤
```

### 输出模型
```python
class SequentialThinkingOutput(ToolOutput):
    reasoning_chain: List[Dict[str, str]]  # 推理链
    conclusion: str                        # 结论
    confidence: float                      # 置信度
    next_actions: List[str]                # 下一步行动建议
```

## 执行方法

### `run(...) -> Dict[str, Any]`

**返回数据结构：**
```python
{
    "reasoning_chain": [
        {
            "step": "分析问题类型",
            "thought": "这是一个关于销售数据聚合的查询需求",
            "observation": "需要使用 GROUP BY 和聚合函数"
        },
        {
            "step": "识别相关表",
            "thought": "涉及 orders 和 products 表",
            "observation": "需要 JOIN 操作连接两表"
        },
        ...
    ],
    "conclusion": "需要生成一个包含 JOIN 和 GROUP BY 的 SQL 查询",
    "confidence": 0.85,
    "next_actions": [
        "使用 sql_generation 工具生成 SQL",
        "验证生成的 SQL 语法",
        "执行并检查结果"
    ]
}
```

## 内部方法

### `_generate_thinking_steps(problem: str, context: Dict) -> List[str]`
生成思考步骤。

**默认思考步骤：**
1. 分析问题类型和复杂度
2. 识别关键信息和约束
3. 评估可用资源和工具
4. 制定解决策略
5. 预测潜在挑战
6. 确定成功标准

### `_perform_step_analysis(step: str, context: Dict, previous_thoughts: List) -> Dict[str, str]`
执行单步分析。

**分析过程：**
- 基于当前步骤目标
- 考虑上下文信息
- 参考之前的思考结果
- 生成观察和洞察

### `_evaluate_confidence(reasoning_chain: List[Dict]) -> float`
评估推理置信度。

**评估因素：**
- 推理步骤的完整性
- 逻辑的一致性
- 证据的充分性
- 不确定性的程度

### `_determine_next_actions(conclusion: str, context: Dict) -> List[str]`
确定下一步行动。

**行动类型：**
- 工具调用建议
- 信息收集需求
- 验证步骤
- 优化方向

## 使用示例

### 基本使用
```python
# 创建工具实例
tool = SequentialThinkingTool(settings)

# 准备上下文
context = {
    "database_schema": schema_info,
    "domain": "电商",
    "previous_analysis": {
        "main_entities": ["orders", "products", "customers"],
        "relationships": [...]
    }
}

# 定义问题
problem = "如何生成一个查询来分析过去三个月每个产品类别的销售趋势？"

# 执行思考
result = tool.run(
    context=context,
    problem=problem
)

if result["success"]:
    data = result["data"]
    
    # 查看推理过程
    print("推理步骤:")
    for step in data["reasoning_chain"]:
        print(f"\n步骤: {step['step']}")
        print(f"思考: {step['thought']}")
        print(f"观察: {step['observation']}")
    
    print(f"\n结论: {data['conclusion']}")
    print(f"置信度: {data['confidence']}")
    
    print("\n建议的下一步:")
    for action in data["next_actions"]:
        print(f"- {action}")
```

### 使用自定义思考步骤
```python
# 定义特定的思考步骤
custom_steps = [
    "识别查询的时间范围要求",
    "确定需要的聚合维度",
    "选择合适的聚合函数",
    "考虑性能优化策略",
    "验证业务逻辑合理性"
]

result = tool.run(
    context=context,
    problem=problem,
    thinking_steps=custom_steps
)
```

### 复杂问题分析
```python
# 复杂的多步骤问题
complex_problem = """
需要创建一个报表，显示：
1. 每个客户的生命周期价值
2. 客户的购买频率和最近购买时间
3. 预测客户流失风险
这需要考虑哪些因素？如何设计查询？
"""

result = tool.run(
    context={
        "database_schema": schema_info,
        "available_tools": ["sql_generation", "sql_validation"],
        "constraints": {
            "performance": "查询需要在5秒内完成",
            "accuracy": "准确率要求 > 90%"
        }
    },
    problem=complex_problem
)
```

## 推理链示例

### 简单查询分析
```json
{
    "reasoning_chain": [
        {
            "step": "分析问题类型",
            "thought": "这是一个简单的数据检索查询",
            "observation": "只需要 SELECT 和 WHERE 条件"
        },
        {
            "step": "识别数据源",
            "thought": "查询涉及 users 表",
            "observation": "单表查询，无需 JOIN"
        },
        {
            "step": "确定筛选条件",
            "thought": "需要按注册时间筛选",
            "observation": "使用 created_at 字段"
        }
    ],
    "conclusion": "生成简单的 SELECT 查询with WHERE 条件",
    "confidence": 0.95,
    "next_actions": ["生成 SQL", "执行查询"]
}
```

### 复杂分析思考
```json
{
    "reasoning_chain": [
        {
            "step": "分解复杂需求",
            "thought": "需求包含 CLV 计算、RFM 分析和流失预测",
            "observation": "需要多个子查询或 CTE"
        },
        {
            "step": "评估数据完整性",
            "thought": "需要订单历史、客户信息和时间序列数据",
            "observation": "数据跨越多个表，需要复杂 JOIN"
        },
        {
            "step": "选择计算策略",
            "thought": "CLV 需要历史总额，RFM 需要聚合统计",
            "observation": "使用窗口函数可能更高效"
        },
        {
            "step": "考虑性能影响",
            "thought": "大量历史数据可能导致查询缓慢",
            "observation": "建议使用物化视图或分批处理"
        }
    ],
    "conclusion": "需要设计多阶段查询策略，可能需要创建中间表",
    "confidence": 0.75,
    "next_actions": [
        "创建 CLV 计算的 CTE",
        "设计 RFM 评分逻辑",
        "考虑使用机器学习模型进行流失预测",
        "优化查询性能"
    ]
}
```

## 思考模式

### 问题分解模式
1. 识别核心需求
2. 分解为子问题
3. 确定依赖关系
4. 设计解决顺序

### 资源评估模式
1. 可用数据评估
2. 工具能力匹配
3. 性能约束考虑
4. 替代方案准备

### 风险识别模式
1. 数据质量风险
2. 性能瓶颈风险
3. 逻辑错误风险
4. 结果准确性风险

## 最佳实践

1. **提供充分的上下文**
   - 包含所有相关的分析结果
   - 说明约束和限制
   - 提供历史决策信息

2. **问题描述清晰**
   - 明确目标和期望
   - 说明优先级
   - 提供必要的背景

3. **利用思考步骤**
   - 针对特定领域自定义步骤
   - 保持步骤的逻辑顺序
   - 避免步骤过于细碎

4. **关注置信度**
   - 低置信度时考虑更多信息
   - 使用置信度指导决策
   - 记录不确定性来源

## 扩展应用

### 与其他工具配合
```python
# 思考 -> 生成 -> 验证 流程
thinking_result = thinking_tool.run(context, problem)

if thinking_result["data"]["confidence"] > 0.8:
    # 高置信度，直接执行建议的行动
    for action in thinking_result["data"]["next_actions"]:
        if "sql_generation" in action:
            sql_result = sql_tool.run(...)
```

### 迭代思考
```python
# 基于反馈进行迭代思考
initial_result = thinking_tool.run(context, problem)

# 执行建议的行动并获得反馈
feedback = execute_actions(initial_result["data"]["next_actions"])

# 更新上下文并重新思考
updated_context = {**context, "feedback": feedback}
refined_result = thinking_tool.run(updated_context, problem)
```

## 注意事项

1. 思考过程基于启发式方法，不保证最优解
2. 复杂问题可能需要多轮思考
3. 置信度评估是相对的，需要结合实际情况
4. 思考步骤的质量影响最终结果
5. 避免过度思考导致分析瘫痪