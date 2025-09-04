# SemanticSQL Agent 设计规范（精简版）

## 1. 项目概述

### 1.1 项目定位
SemanticSQL Agent 是基于 ReAct 智能体架构的 **NL2SQL 训练数据生成系统**。

**核心功能**：
- 📊 **智能数据库分析**：自动提取数据库结构、识别业务领域、分析表关系
- 🎯 **Agent自主生成**：完全由Agent自主决策生成高质量的问题-SQL对
- ✅ **执行验证机制**：实际执行生成的SQL，验证正确性
- 🔄 **智能反思优化**：分析执行结果，自动优化质量

### 1.2 设计原则
- **Agent完全自主**：无外部循环控制，Agent根据任务自主决策
- **记忆驱动协作**：工具通过记忆自动协作，无需手动传参
- **极简架构**：避免过度设计，保持代码简洁高效

## 2. 核心架构

### 2.1 Agent执行模式

```python
class SQLAgent:
    def generate_training_data(self):
        """完全由Agent自主驱动的训练数据生成"""
        
        task = "请生成高质量的NL2SQL训练问题"
        
        result = self.agent_executor.invoke({
            "input": task,
            "database_name": self.db_config.database
        })
        
        return self._extract_samples(result)
```

### 2.2 Agent内部流程

```
用户: "请生成高质量的NL2SQL训练问题"
    ↓
Thought: 检查记忆中是否有完整的数据库分析
Action: 检查记忆状态
Observation: 缺少分析，需要先分析数据库
    ↓
Thought: 先了解数据库结构
Action: schema_extraction
Observation: 数据库结构 → 保存到 memories["schema_info"]
    ↓
[按需完成其他分析工具...]
    ↓
Thought: 获取场景和操作方案
Action: scenario_operation_generation
Observation: {
    "scenario": {"name": "销售分析", "complexity": "moderate"},
    "operations": ["SELECT", "GROUP BY"],
    "generated_prompt": "场景匹配的提示词..."
} → 保存到 memories["scenario_operation"]
    ↓
Thought: 调用问题生成工具
Action: question_generation
Action Input: {}  # 工具自动从记忆中读取场景信息
Observation: "统计每月销售总额"
    ↓
Thought: 生成SQL
Action: sql_generation
Action Input: {}  # 工具自动从记忆中读取问题和场景信息
Observation: "SELECT MONTH(order_date), SUM(amount)..."
    ↓
[验证、执行、反思...]
    ↓
Final Answer: 完整的训练样本
```

## 3. 工具设计

### 3.1 工具分类

| 工具类别 | 工具名称 | 功能 |
|---------|---------|------|
| 分析工具 | schema_extraction<br>domain_analysis<br>field_analysis<br>column_analysis<br>table_analysis<br>er_analysis | 分析数据库，结果保存到记忆 |
| 生成工具 | scenario_operation_generation<br>question_generation<br>sql_generation | 基于记忆生成内容 |
| 验证工具 | sql_validation<br>sql_execution | 验证SQL正确性 |
| 反思工具 | sql_reflection | 评估质量，提供修正建议 |
| 思考工具 | sequential_thinking | 深度分析复杂问题 |

### 3.2 记忆管理（utils/memory.py）

```python
class DatabaseAnalysisMemory(BaseMemory):
    def __init__(self):
        self.memories = {}  # 存储工具结果
    
    def save_context(self, inputs, outputs):
        """工具名称自动映射到记忆键"""
        tool_name = inputs.get("tool_name")
        memory_mapping = {
            "schema_extraction": "schema_info",
            "domain_analysis": "domain_info",
            "scenario_operation_generation": "scenario_operation",
            "question_generation": "question",
            # ...
        }
        if tool_name in memory_mapping:
            self.memories[memory_mapping[tool_name]] = outputs.get("output")
```

### 3.3 反思工具返回格式

```python
# 极简的反思格式
{
    "quality_score": 0.85,              # 质量分数 0-1
    "needs_revision": False,            # 是否需要修正
    "suggested_tool": "sql_generation", # 建议的工具（可选）
    "suggestion": "修正建议文字"         # 简单建议
}
```

## 4. 提示词系统

### 4.1 分层Jinja2模板

```
prompts/templates/
├── system/main.j2           # 系统主提示词
├── tools/
│   ├── scenario_operation.j2    # 各工具专用提示词
│   ├── question_generation.j2
│   └── sql_generation.j2
└── manager.py               # 提示词管理器
```

### 4.2 系统提示词要点

- 强调记忆检查优先
- 说明工具调用的基本策略  
- 提供ReAct执行格式
- 保持Agent完全自主决策权

### 4.3 工具提示词要点

- 前置条件检查（从记忆中）
- 任务具体要求
- 输出格式规范
- 自动信息注入逻辑

## 5. CLI接口（极简）

```bash
semanticsql-agent generate --database shop_db --output data.jsonl
```

**参数**：
- `--config`: 配置文件路径
- `--database`: 数据库名称
- `--output`: 输出文件路径
- `--verbose`: 详细输出

## 6. 核心优势

1. **架构极简**：无外部循环，完全Agent自主
2. **记忆驱动**：工具自动协作，无需手动传参
3. **质量保证**：单条生成+立即反思
4. **真正ReAct**：Agent根据任务自主选择工具调用顺序

---

**这个精简版本保留了所有核心设计要点，删除了重复和错误的内容，从2507行精简到约200行。**