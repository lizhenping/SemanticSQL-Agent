# SemanticSQL Agent 工作流程

## 完整执行流程

### 阶段1：数据库分析（只执行一次）

按以下顺序执行，每步结果自动保存到记忆：

```
1. schema_extraction
   ↓ → memory["schema_info"]
2. domain_analysis  
   ↓ → memory["domain_info"]
3. field_classification
   ↓ → memory["field_classification"]
4. column_meaning_analysis
   ↓ → memory["column_meanings"]
5. table_meaning_analysis
   ↓ → memory["table_meanings"]
6. er_analysis
   ↓ → memory["er_relations"]
```

### 阶段2：训练数据生成（循环N次）

对每个样本执行完整的7步流程：

```
for i in range(N):
    1. scenario_tool(iteration=i)
       ↓
    2. operation_selection(scenario_id=..., complexity=...)
       ↓
    3. question_generation(scenario_id=..., operations=[...])
       ↓
    4. sql_generation(question=..., scenario={...})
       ↓
    5. sql_validation(sql=...)
       ↓
    6. sql_execution(sql=...)
       ↓
    7. sql_reflection(sql=..., execution_result=...)
       ↓
    需要修正？
    ├─ 否 → 保存结果，继续下一个样本
    └─ 是 → 根据recommended_action修正
```

### 修正流程

当sql_reflection返回needs_revision=true时：

1. **分析问题**：
   - problem_source: 问题来源
   - recommended_action: 建议行动

2. **执行修正**：
   - 如果是问题生成错误 → 重新执行question_generation
   - 如果是SQL生成错误 → 重新执行sql_generation
   - 如果需要深度分析 → 使用sequential_thinking

3. **重新验证**：
   - 修正后重新执行validation → execution → reflection

## 工具调用示例

```
Thought: 开始数据库分析，首先提取结构
Action: schema_extraction
Action Input: {"database": "testdb"}

Thought: 已获得结构，现在分析业务领域
Action: domain_analysis
Action Input: {}

Thought: 开始生成第1个样本，选择场景
Action: scenario_tool
Action Input: {"iteration": 0}

Thought: 根据场景选择SQL操作
Action: operation_selection
Action Input: {"scenario_id": "xxx", "complexity": "medium"}
```

## 记忆使用原则

- 数据库分析结果永久保存在记忆中
- 生成工具从记忆读取，不重复分析
- 每个工具的输出自动保存到对应的记忆槽位