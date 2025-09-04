# SemanticSQL Agent 设计规范（完整版）

## 1. 项目概述

### 1.1 项目定位
SemanticSQL Agent 是一个基于 ReAct 智能体架构的 **NL2SQL 训练数据生成系统**。

**核心功能**：
- 📊 **智能数据库分析**：自动提取数据库结构、识别业务领域、分析表关系
- 🎯 **Agent自主生成**：完全由Agent自主决策生成高质量的问题-SQL对
- ✅ **执行验证机制**：实际执行生成的 SQL，验证正确性和可行性
- 🔄 **智能反思优化**：分析执行结果，自动优化 SQL 质量和性能
- 📦 **标准化输出**：生成符合训练标准的 JSON/JSONL 格式数据集

**目标用途**：为 NL2SQL 模型训练提供高质量、大规模的合成训练数据，减少人工标注成本，提升模型在特定领域的表现。

### 1.2 核心价值
- **自动化生成**：减少人工标注成本，快速生成大量训练数据
- **高质量保证**：通过验证和反思机制确保数据质量
- **领域适应**：自动识别业务领域，生成符合领域特征的数据
- **灵活扩展**：基于工具的架构，易于添加新功能

### 1.3 设计原则
- **智能体驱动**：采用 ReAct 模式，智能体自主决策执行流程
- **模块化设计**：工具职责单一，通过智能体协调
- **简洁实用**：避免过度设计，保持代码简单高效
- **可追踪性**：完整记录执行过程，便于调试和优化

## 2. 最终设计方案

### 2.1 核心设计决策

**明确采用的方案**：
- **直接调用Agent**：用户直接调用Agent，无外部循环控制
- **工具内部生成内容**：ScenarioOperationTool内部生成所有场景-操作组合
- **逐个处理模式**：问题生成阶段逐个处理ScenarioOperationTool的输出

**不采用的方案**：
- ❌ 外部遍历+Agent单条生成
- ❌ 批量生成+批量反思
- ❌ 复杂的数量控制循环

### 2.2 Agent执行流程

#### 2.2.1 用户调用方式

```python
# 极简的用户调用
agent = SQLAgent(settings, db_config)
result = agent.generate_training_data()
```

#### 2.2.2 Agent内部完整流程

```
用户: "请生成高质量的NL2SQL训练问题"
    ↓
Thought: 我需要生成训练问题，先检查记忆中是否有完整的数据库分析
Action: 检查记忆状态
Observation: memories 中缺少完整分析，需要先分析数据库
    ↓
Thought: 缺少数据库分析，需要先了解数据库结构
Action: schema_extraction
Observation: 数据库结构信息 → 自动保存到 memories["schema_info"]
    ↓
Thought: 需要理解业务领域
Action: domain_analysis  
Observation: 电商领域信息 → 自动保存到 memories["domain_info"]
    ↓
Thought: 需要分析字段类型
Action: field_analysis
Observation: 字段分类信息 → 自动保存到 memories["field_classification"]
    ↓
Thought: 需要理解列的业务含义
Action: column_analysis
Observation: 列业务含义 → 自动保存到 memories["column_meanings"]
    ↓
Thought: 需要理解表的业务职责
Action: table_analysis
Observation: 表业务含义 → 自动保存到 memories["table_meanings"]
    ↓
Thought: 最后分析表之间的关系
Action: er_analysis
Observation: 表关系信息 → 自动保存到 memories["er_relations"]
    ↓
Thought: 现在我有了完整的数据库分析，获取所有场景和操作组合
Action: scenario_operation_generation
Action Input: {"mode": "get_all_combinations"}
Observation: {
    "total_combinations": 48,
    "combinations": [
        {
            "combination_id": "sales_analysis_simple",
            "scenario": {"name": "销售分析", "complexity": "simple"},
            "operations": ["SELECT", "WHERE"],
            "generated_prompt": "基于销售分析场景的简单查询..."
        },
        {
            "combination_id": "sales_analysis_moderate", 
            "scenario": {"name": "销售分析", "complexity": "moderate"},
            "operations": ["SELECT", "GROUP BY"],
            "generated_prompt": "基于销售分析场景的聚合查询..."
        },
        ...更多组合
    ]
} → 自动保存到 memories["all_scenario_combinations"]
    ↓
Thought: 我得到了48个场景-操作组合，现在需要逐个处理生成问题
    ↓
Thought: 处理第1个组合：sales_analysis_simple
Action: question_generation
Action Input: {
    "combination": memories["all_scenario_combinations"]["combinations"][0],
    "use_prompt": memories["all_scenario_combinations"]["combinations"][0]["generated_prompt"]
}
Observation: "查询本月的销售订单" → 自动保存到 memories["question_1"]
    ↓
Thought: 为第1个问题生成SQL
Action: sql_generation
Action Input: {
    "question": memories["question_1"],
    "combination": memories["all_scenario_combinations"]["combinations"][0]
}
Observation: "SELECT * FROM orders WHERE MONTH(order_date) = MONTH(NOW())"
    ↓
Thought: 验证第1个SQL
Action: sql_validation
Observation: 语法正确
    ↓
Thought: 执行第1个SQL
Action: sql_execution
Observation: 成功返回156条记录
    ↓
Thought: 反思第1个样本质量
Action: sql_reflection
Observation: {"quality_score": 0.75, "needs_revision": false}
    ↓
Thought: 第1个样本质量良好，继续处理第2个组合：sales_analysis_moderate
Action: question_generation
Action Input: {
    "combination": memories["all_scenario_combinations"]["combinations"][1],
    "use_prompt": memories["all_scenario_combinations"]["combinations"][1]["generated_prompt"]
}
Observation: "统计每月销售总额" → 自动保存到 memories["question_2"]
    ↓
[继续逐个处理所有48个组合...]
    ↓
Thought: 我已经处理完所有48个场景组合，生成了48个高质量训练样本
Final Answer: [
    {"question": "查询本月的销售订单", "sql": "SELECT...", "quality_score": 0.75},
    {"question": "统计每月销售总额", "sql": "SELECT...", "quality_score": 0.85},
    ...48个样本
]
```

### 2.3 关键设计特点

1. **Agent内部处理所有逻辑**：
   - ScenarioOperationTool一次性返回所有48个组合
   - Agent内部逐个处理每个组合
   - 无外部循环控制

2. **记忆驱动的工具协作**：
   - 所有工具结果自动保存到记忆
   - 后续工具自动从记忆中读取信息
   - Agent无需手动传递参数

3. **单条生成+立即反思**：
   - 每个样本生成后立即反思
   - 发现问题立即修正
   - 保证每个样本的质量

## 3. 工具系统设计

### 3.1 工具分类和职责

#### 3.1.1 分析工具（Analysis Tools）

**schema_extraction_tool**：
- **功能**：提取数据库物理结构
- **输出**：表结构、列信息、数据类型、主外键、约束条件
- **保存位置**：memories["schema_info"]
- **执行时机**：任务开始时，如果记忆中没有schema信息

**domain_analysis_tool**：
- **功能**：识别业务领域特征
- **输出**：业务领域类型、主要实体、业务流程特征
- **保存位置**：memories["domain_info"]
- **依赖**：需要schema_info作为输入

**field_analysis_tool**：
- **功能**：字段语义分类
- **输出**：字段类型分类（ID、时间、金额、状态、描述等）
- **保存位置**：memories["field_classification"]
- **依赖**：需要schema_info和domain_info

**column_analysis_tool**：
- **功能**：分析列的业务含义和用途
- **输出**：每个列的业务含义、取值规则、业务约束
- **保存位置**：memories["column_meanings"]
- **依赖**：需要schema_info、domain_info、field_classification

**table_analysis_tool**：
- **功能**：分析表的业务含义和职责
- **输出**：每个表的业务职责、表类型分类、业务流程位置
- **保存位置**：memories["table_meanings"]
- **依赖**：需要schema_info、domain_info、column_meanings

**er_analysis_tool**：
- **功能**：分析表之间的关系
- **输出**：显式关系（外键）、隐式关系、关系类型、实体重要性
- **保存位置**：memories["er_relations"]
- **依赖**：需要schema_info、table_meanings

#### 3.1.2 生成工具（Generation Tools）

**scenario_operation_generation**（核心工具）：
- **功能**：内部三层for循环，生成所有场景-操作组合
- **输入模式**：
  - `mode="get_all_combinations"`：返回所有48个组合
  - `mode="get_single_combination"`：返回单个组合
- **输出格式**：
```python
{
    "total_combinations": 48,
    "combinations": [
        {
            "combination_id": "sales_analysis_simple",
            "scenario": {
                "main_name": "销售分析",
                "sub_name": "销售统计", 
                "complexity": "simple",
                "focus_areas": ["销售额", "订单量"]
            },
            "operations": ["SELECT", "WHERE"],
            "generated_prompt": "基于销售分析场景，生成简单的销售数据查询问题..."
        },
        ...更多组合
    ]
}
```
- **保存位置**：memories["all_scenario_combinations"]

**question_generation_tool**：
- **功能**：基于场景组合生成自然语言问题
- **输入**：特定的场景组合信息
- **输出**：清晰、具体的自然语言问题
- **依赖**：自动从记忆中读取场景信息和生成的提示词

**sql_generation_tool**：
- **功能**：将问题转换为SQL查询
- **输入**：问题和场景信息
- **输出**：符合场景要求的SQL查询
- **依赖**：自动从记忆中读取问题、场景、schema等信息

#### 3.1.3 验证工具（Validation Tools）

**sql_validation_tool**：
- **功能**：验证SQL语法正确性
- **输入**：SQL语句
- **输出**：语法验证结果

**sql_execution_tool**：
- **功能**：安全执行SQL并返回结果
- **输入**：SQL语句
- **输出**：执行结果、行数、执行时间

#### 3.1.4 反思工具（Reflection Tools）

**sql_reflection_tool**：
- **功能**：评估SQL生成质量，提供修正建议
- **输入**：SQL、执行结果、问题
- **输出格式**：
```python
{
    "quality_score": 0.85,              # 质量分数 0-1
    "needs_revision": False,            # 是否需要修正
    "suggested_tool": "sql_generation", # 建议的工具（可选）
    "suggestion": "修正建议文字"         # 简单建议
}
```

#### 3.1.5 思考工具（Thinking Tools）

**sequential_thinking_tool**：
- **功能**：深度分析复杂问题，制定修正策略
- **使用时机**：遇到复杂问题或多次修正失败时
- **输入**：问题描述和上下文
- **输出**：分析结果和建议策略

### 3.2 工具使用规范

| 工具类别 | 工具名称 | 主要特点 | Agent使用策略 |
|---------|---------|---------|-------------|
| 分析工具 | schema_extraction<br>domain_analysis<br>field_analysis<br>column_analysis<br>table_analysis<br>er_analysis | 结果保存在记忆中<br>可重复执行更新记忆 | 按需调用，优先检查记忆 |
| 生成工具 | scenario_operation_generation<br>question_generation<br>sql_generation | 基于记忆和上下文生成内容 | 核心生成流程必需 |
| 验证工具 | sql_validation<br>sql_execution | 确保SQL正确性和可执行性 | 生成SQL后必须验证 |
| 反思工具 | sql_reflection | 评估质量，提供修正建议 | 执行后自主决定是否反思 |
| 思考工具 | sequential_thinking | 深度分析复杂问题 | 遇到复杂情况时自主调用 |

## 4. 记忆管理系统

### 4.1 DatabaseAnalysisMemory设计

基于 `utils/memory.py` 的实际实现：

```python
from langchain_core.memory import BaseMemory

class DatabaseAnalysisMemory(BaseMemory):
    """数据库分析结果记忆管理"""
    
    def __init__(self):
        self.memories = {}  # 存储所有分析结果
        self.memory_key = "db_analysis"
    
    @property
    def memory_variables(self) -> List[str]:
        return [self.memory_key]
    
    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """加载记忆变量"""
        return {self.memory_key: self.memories}
    
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> None:
        """根据工具名称自动保存结果"""
        tool_name = inputs.get("tool_name") or inputs.get("action", {}).get("tool")
        
        # 工具名称到记忆键的映射
        memory_mapping = {
            "schema_extraction": "schema_info",
            "domain_analysis": "domain_info", 
            "field_analysis": "field_classification",
            "column_analysis": "column_meanings",
            "table_analysis": "table_meanings",
            "er_analysis": "er_relations",
            "scenario_operation_generation": "all_scenario_combinations",
            "question_generation": "current_question",
            "sql_generation": "current_sql"
        }
        
        if tool_name in memory_mapping:
            memory_key = memory_mapping[tool_name]
            data = outputs.get("output", outputs)
            self.memories[memory_key] = data
            logger.info(f"💾 Saved {tool_name} results to memory['{memory_key}']")
```

### 4.2 记忆使用方式

**Agent通过提示词访问记忆**：
```jinja2
## 当前可用信息
{% if db_analysis.schema_info %}
- ✅ 数据库结构: {{db_analysis.schema_info.table_count}} 个表
{% endif %}
{% if db_analysis.domain_info %}
- ✅ 业务领域: {{db_analysis.domain_info.primary_domain}}
{% endif %}
{% if db_analysis.all_scenario_combinations %}
- ✅ 场景组合: {{db_analysis.all_scenario_combinations.total_combinations}} 个
{% endif %}
```

**工具自动从记忆读取信息**：
- 工具在执行时自动检查记忆中的前置条件
- 自动注入所需的信息到工具的提示词中
- 无需Agent手动传递参数

## 5. ScenarioOperationTool详细设计

### 5.1 工具核心功能

**ScenarioOperationTool** 是整个系统的核心生成工具，负责：

1. **内部三层for循环遍历**：
   - 主场景（sales_analysis、inventory_management、customer_analysis等）
   - 子场景（sales_statistics、sales_trends等）
   - 复杂度级别（simple、moderate、complex、expert）

2. **生成匹配的提示词**：
   - 为每个组合生成专门的问题生成提示词
   - 提示词包含场景描述、操作要求、复杂度指导

3. **操作组合映射**：
   - 根据场景复杂度自动选择合适的SQL操作组合
   - simple: ["SELECT", "WHERE"]
   - moderate: ["SELECT", "GROUP BY", "HAVING"]
   - complex: ["SELECT", "JOIN", "SUBQUERY"]
   - expert: ["SELECT", "WINDOW_FUNCTION", "CTE"]

### 5.2 工具实现逻辑

```python
class ScenarioOperationTool(BaseTool):
    """场景-操作组合生成工具"""
    
    name = "scenario_operation_generation"
    description = "生成所有场景-操作组合，内部处理三层for循环遍历"
    
    def _run(self, mode: str = "get_all_combinations", **kwargs):
        if mode == "get_all_combinations":
            return self._generate_all_combinations()
        elif mode == "get_single_combination":
            return self._generate_single_combination(kwargs.get("iteration", 0))
    
    def _generate_all_combinations(self):
        """内部三层for循环，生成所有场景组合"""
        
        # 加载配置
        scenarios = self._load_scenarios()
        operation_mapping = self._load_operation_mapping()
        complexity_config = self._load_complexity_config()
        
        all_combinations = []
        combination_index = 0
        
        # 三层for循环（参考pipeline设计）
        for main_key, main_data in scenarios.items():
            if main_key in ['scenario_types', 'total_scenarios']:
                continue
                
            for sub_key, sub_data in main_data['sub_scenarios'].items():
                for complexity in ['simple', 'moderate', 'complex', 'expert']:
                    
                    # 检查是否有对应的操作映射
                    if self._has_operation_mapping(main_key, sub_key, complexity):
                        
                        # 获取操作组合
                        operations = self._get_operations_for_combination(
                            main_key, sub_key, complexity, operation_mapping
                        )
                        
                        # 生成专门的提示词模板
                        generated_prompt = self._generate_prompt_for_combination(
                            main_data, sub_data, complexity, operations
                        )
                        
                        combination = {
                            "combination_id": f"{main_key}_{sub_key}_{complexity}",
                            "index": combination_index,
                            "scenario": {
                                "main_key": main_key,
                                "main_name": main_data['name'],
                                "main_description": main_data['description'],
                                "sub_key": sub_key,
                                "sub_name": sub_data['name'],
                                "focus_areas": sub_data['focus_areas'],
                                "complexity": complexity
                            },
                            "operations": operations,
                            "generated_prompt": generated_prompt,
                            "complexity_config": complexity_config[complexity]
                        }
                        
                        all_combinations.append(combination)
                        combination_index += 1
        
        return {
            "total_combinations": len(all_combinations),
            "combinations": all_combinations,
            "generation_strategy": "三层遍历：主场景×子场景×复杂度"
        }
    
    def _generate_prompt_for_combination(self, main_data, sub_data, complexity, operations):
        """为特定组合生成专门的提示词"""
        
        prompt_template = f"""
基于{main_data['name']}场景的{sub_data['name']}任务，生成{complexity}级别的问题。

## 场景描述
{main_data['description']}

## 任务焦点
{', '.join(sub_data['focus_areas'])}

## SQL操作要求
必须使用以下操作: {', '.join(operations)}

## 复杂度要求
{self._get_complexity_description(complexity)}

请生成一个符合上述要求的自然语言问题。
"""
        return prompt_template.strip()
```

### 5.3 问题生成的逐个处理机制

Agent获得所有场景组合后，会逐个处理：

```
Thought: 我有了48个场景组合，现在逐个处理生成问题

# 处理第1个组合
Thought: 处理组合1：sales_analysis_simple
Action: question_generation
Action Input: {
    "combination_index": 0,
    "use_combination": memories["all_scenario_combinations"]["combinations"][0]
}
Observation: 生成的问题

# 立即生成对应的SQL
Thought: 为这个问题生成SQL
Action: sql_generation
Observation: 生成的SQL

# 立即验证和反思
[验证、执行、反思流程...]

# 处理第2个组合
Thought: 处理组合2：sales_analysis_moderate
Action: question_generation
Action Input: {
    "combination_index": 1,
    "use_combination": memories["all_scenario_combinations"]["combinations"][1]
}
[重复流程...]
```

## 6. Agent实现规范

### 6.1 SQLAgent核心实现

```python
class SQLAgent(BaseAgent):
    """SQL生成智能体 - 基于ReAct模式"""
    
    def __init__(self, settings: Settings, db_config: DatabaseConfig):
        # 初始化LLM
        self.llm = ChatOpenAI(
            openai_api_base=settings.llm_base_url,
            model=settings.llm_model,
            temperature=0.7
        )
        
        # 初始化记忆
        self.memory = DatabaseAnalysisMemory()
        
        # 创建所有工具（不分类，不过滤）
        self.tools = self._initialize_all_tools()
        
        # 创建统一的Agent（拥有所有工具访问权限）
        prompt = self._get_system_prompt()
        agent = create_react_agent(self.llm, self.tools, prompt)
        
        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            memory=self.memory,
            verbose=True,
            max_iterations=50,  # 需要足够的迭代次数处理48个组合
            callbacks=[TrajectoryCallback()]
        )
    
    def generate_training_data(self) -> List[Dict]:
        """完全由Agent自主驱动的训练数据生成"""
        
        task = "请生成高质量的NL2SQL训练数据集，覆盖所有场景组合"
        
        result = self.agent_executor.invoke({
            "input": task,
            "database_name": self.db_config.database
        })
        
        return self._extract_all_samples(result)
    
    def _extract_all_samples(self, agent_result) -> List[Dict]:
        """从Agent执行结果中提取所有生成的样本"""
        # 从执行轨迹或最终答案中提取48个样本
        # 实现逻辑根据实际的Agent输出格式
        pass
```

### 6.2 Agent工作流程详解

#### 6.2.1 数据库分析阶段

```
Thought: 我需要生成训练数据集，首先检查是否了解数据库
Action: 检查记忆状态
Observation: memories 为空，需要完整分析数据库
    ↓
Thought: 先提取数据库结构
Action: schema_extraction
Observation: 数据库结构信息 → memories["schema_info"]
    ↓
Thought: 理解业务领域
Action: domain_analysis
Observation: 业务领域信息 → memories["domain_info"]
    ↓
Thought: 分析字段语义
Action: field_analysis
Observation: 字段分类信息 → memories["field_classification"]
    ↓
Thought: 分析列的业务含义
Action: column_analysis
Observation: 列含义信息 → memories["column_meanings"]
    ↓
Thought: 分析表的业务职责
Action: table_analysis
Observation: 表含义信息 → memories["table_meanings"]
    ↓
Thought: 分析表之间的关系
Action: er_analysis
Observation: 表关系信息 → memories["er_relations"]
```

#### 6.2.2 场景组合生成阶段

```
Thought: 现在我有了完整的数据库分析，获取所有场景-操作组合
Action: scenario_operation_generation
Action Input: {"mode": "get_all_combinations"}
Observation: {
    "total_combinations": 48,
    "combinations": [
        {
            "combination_id": "sales_analysis_simple",
            "scenario": {...},
            "operations": ["SELECT", "WHERE"],
            "generated_prompt": "专门的问题生成提示词..."
        },
        ...47个更多组合
    ]
} → 自动保存到 memories["all_scenario_combinations"]
```

#### 6.2.3 逐个问题生成阶段

```
Thought: 我得到了48个场景组合，现在需要逐个处理生成问题和SQL

# 处理第1个组合
Thought: 处理第1个组合：sales_analysis_simple
Action: question_generation
Action Input: {
    "combination_index": 0,
    "use_combination": "第1个组合的信息"
}
Observation: "查询本月的销售订单"
    ↓
Thought: 为这个问题生成SQL
Action: sql_generation
Action Input: {
    "question": "查询本月的销售订单",
    "combination_index": 0
}
Observation: "SELECT * FROM orders WHERE MONTH(order_date) = MONTH(NOW())"
    ↓
Thought: 验证SQL语法
Action: sql_validation
Action Input: {"sql": "SELECT * FROM orders..."}
Observation: {"valid": true, "message": "语法正确"}
    ↓
Thought: 执行SQL测试
Action: sql_execution
Action Input: {"sql": "SELECT * FROM orders..."}
Observation: {"success": true, "row_count": 156, "execution_time": 0.05}
    ↓
Thought: 反思这个样本的质量
Action: sql_reflection
Action Input: {
    "sql": "SELECT * FROM orders...",
    "question": "查询本月的销售订单",
    "execution_result": {"success": true, "row_count": 156}
}
Observation: {
    "quality_score": 0.75,
    "needs_revision": false,
    "suggestion": "质量良好"
}
    ↓
Thought: 第1个样本完成，继续处理第2个组合

# 处理第2个组合
Thought: 处理第2个组合：sales_analysis_moderate
Action: question_generation
Action Input: {
    "combination_index": 1,
    "use_combination": "第2个组合的信息"
}
Observation: "统计每月销售总额"
    ↓
[重复相同的生成、验证、反思流程...]

# 继续处理所有48个组合...

Thought: 我已经处理完所有48个场景组合，生成了48个训练样本
Final Answer: [
    {"question": "查询本月的销售订单", "sql": "SELECT...", "quality_score": 0.75},
    {"question": "统计每月销售总额", "sql": "SELECT...", "quality_score": 0.85},
    ...46个更多样本
]
```

## 7. 提示词系统设计

### 7.1 分层Jinja2模板架构

```
prompts/
├── templates/
│   ├── system/
│   │   └── main.j2                    # Agent系统提示词
│   ├── tools/
│   │   ├── schema_extraction.j2       # 数据库结构提取提示词
│   │   ├── domain_analysis.j2         # 业务领域分析提示词
│   │   ├── scenario_operation.j2      # 场景-操作生成提示词
│   │   ├── question_generation.j2     # 问题生成提示词
│   │   ├── sql_generation.j2          # SQL生成提示词
│   │   └── sql_reflection.j2          # 反思评估提示词
│   └── analysis/
│       └── database_analysis.j2       # 数据库分析专用提示词
└── manager.py                         # 提示词管理器
```

### 7.2 系统提示词（system/main.j2）

```jinja2
你是专业的NL2SQL训练数据生成专家，基于ReAct模式工作。

## 当前任务
{{input}}

## 环境信息
- 数据库: {{database_name}}
{% if db_analysis %}
- 记忆状态: 已有数据库分析信息
{% else %}
- 记忆状态: 需要先分析数据库
{% endif %}

## 工作流程指导

### 🧠 智能工作策略：

1. **记忆检查优先**：
   - 检查 {{db_analysis}} 中是否有完整的数据库分析
   - 如果缺少关键分析，先调用相应的分析工具

2. **获取所有场景组合**：
   - 调用 scenario_operation_generation 获取所有场景-操作组合
   - 工具内部会完成三层for循环遍历

3. **逐个处理组合**：
   - 对每个组合调用 question_generation（工具自动注入对应的提示词）
   - 对每个问题调用 sql_generation（工具自动注入问题和场景信息）
   - 对每个SQL进行验证、执行、反思

4. **质量保证**：
   - 每个样本都要经过完整的验证和反思流程

## 可用工具
{{tools}}

## ReAct执行格式
Thought: 分析当前情况，决定下一步
Action: 工具名称
Action Input: 工具参数
Observation: 工具结果
...
Final Answer: 最终的训练数据集

**记住**：你有完全的自主决策权，根据实际需求灵活选择工具和执行顺序。
```

### 7.3 工具专用提示词

#### 7.3.1 scenario_operation.j2

```jinja2
你需要生成所有的场景-操作组合用于NL2SQL训练数据生成。

## 前置条件检查
{% if db_analysis.schema_info %}
- ✅ 数据库结构: {{db_analysis.schema_info.table_count}} 个表
{% endif %}
{% if db_analysis.domain_info %}
- ✅ 业务领域: {{db_analysis.domain_info.primary_domain}}
{% endif %}

## 任务要求
基于数据库分析结果，生成所有可能的场景-操作组合。

内部需要完成三层for循环：
1. 主场景遍历（sales_analysis、inventory_management等）
2. 子场景遍历（每个主场景的具体子任务）
3. 复杂度遍历（simple、moderate、complex、expert）

## 输出格式
返回包含所有组合的JSON：
{
    "total_combinations": 48,
    "combinations": [
        {
            "combination_id": "场景标识",
            "scenario": "场景详细信息",
            "operations": "SQL操作列表",
            "generated_prompt": "为该组合专门生成的问题提示词"
        },
        ...
    ]
}

每个组合都要生成专门的问题生成提示词。
```

#### 7.3.2 question_generation.j2

```jinja2
你需要基于特定的场景组合生成自然语言问题。

## 前置条件检查
{% if db_analysis.all_scenario_combinations %}
- ✅ 场景组合: {{db_analysis.all_scenario_combinations.total_combinations}} 个可用
{% else %}
- ❌ 缺少场景组合，需要先调用 scenario_operation_generation
{% endif %}

## 当前处理的组合
{# 这里会被Agent传入的combination_index动态注入 #}
{% if combination_index is defined %}
{% set current_combination = db_analysis.all_scenario_combinations.combinations[combination_index] %}
- 组合ID: {{current_combination.combination_id}}
- 场景: {{current_combination.scenario.main_name}} - {{current_combination.scenario.sub_name}}
- 复杂度: {{current_combination.scenario.complexity}}
- 操作: {{current_combination.operations}}

## 专门的生成指导
{{current_combination.generated_prompt}}
{% endif %}

## 数据库上下文
{% if db_analysis.schema_info %}
可用表: {{db_analysis.schema_info.tables | map(attribute='name') | join(', ')}}
{% endif %}

基于上述信息，生成一个清晰、具体的自然语言问题。
```

#### 7.3.3 sql_generation.j2

```jinja2
你需要将自然语言问题转换为SQL查询。

## 前置条件检查
{% if db_analysis.current_question %}
- ✅ 当前问题: {{db_analysis.current_question}}
{% else %}
- ❌ 缺少问题，需要先调用 question_generation
{% endif %}

{% if db_analysis.all_scenario_combinations and combination_index is defined %}
{% set current_combination = db_analysis.all_scenario_combinations.combinations[combination_index] %}
- ✅ 场景: {{current_combination.scenario.main_name}}
- ✅ 操作要求: {{current_combination.operations}}
- ✅ 复杂度: {{current_combination.scenario.complexity}}
{% endif %}

## 数据库结构
{% if db_analysis.schema_info %}
{% for table in db_analysis.schema_info.tables %}
表: {{table.name}}
{% for column in table.columns %}
  - {{column.name}} ({{column.type}}) {{column.comment or ''}}
{% endfor %}
{% endfor %}
{% endif %}

## 业务理解
{% if db_analysis.domain_info %}
业务领域: {{db_analysis.domain_info.primary_domain}}
{% endif %}

## 任务要求
基于问题"{{db_analysis.current_question}}"生成SQL查询。

必须满足：
1. 使用正确的表名和字段名
2. 包含要求的SQL操作: {{current_combination.operations}}
3. 符合{{current_combination.scenario.complexity}}复杂度要求

生成准确、高效的SQL查询。
```

## 8. 错误处理和反思机制

### 8.1 反思工具设计

**sql_reflection_tool** 的简化返回格式：

```python
{
    "quality_score": 0.85,              # 质量分数 0-1
    "needs_revision": False,            # 是否需要修正
    "suggested_tool": "sql_generation", # 建议的工具（可选）
    "suggestion": "修正建议文字"         # 简单建议
}
```

### 8.2 Agent自主修正流程

```
Thought: SQL执行失败，我需要反思分析原因
Action: sql_reflection
Observation: {
    "quality_score": 0.3,
    "needs_revision": true,
    "suggested_tool": "sql_generation",
    "suggestion": "重新生成SQL，使用正确的表名"
}
    ↓
Thought: 反思建议我重新调用sql_generation。这很合理。
Action: sql_generation
Action Input: {"focus": "使用正确表名"}
Observation: 修正后的SQL
    ↓
Thought: 重新验证修正后的SQL
Action: sql_validation
Observation: 语法正确，修正成功
```

### 8.3 错误类型和处理策略

**常见错误类型**：
1. **语法错误**：SQL语法不正确
2. **表名错误**：使用了不存在的表名
3. **字段错误**：使用了不存在的字段名
4. **语义不匹配**：SQL没有正确实现问题意图
5. **复杂度不符**：生成的SQL复杂度与要求不符

**Agent自主处理策略**：
- 简单错误：直接重新调用相应工具
- 复杂错误：先调用 sequential_thinking 深度分析
- 多次失败：可能需要重新分析数据库某些方面

## 9. 配置和部署

### 9.1 配置文件设计

```yaml
# config.yaml - 极简配置
database:
  host: localhost
  port: 3306
  username: root
  password: ${DB_PASSWORD}
  database: shop_db

llm:
  model: Qwen3-14B
  base_url: http://localhost:9991/v1
  api_key: ${LLM_API_KEY}
  temperature: 0.7
  max_tokens: 4096

agent:
  max_steps: 50  # 需要足够步骤处理所有组合
  verbose: true
```

### 9.2 CLI接口

```bash
# 极简命令行接口
semanticsql-agent generate [OPTIONS]

Options:
  --config PATH           配置文件路径
  --database TEXT        数据库名称
  --output PATH          输出文件路径 [default: training_data.jsonl]
  --verbose              详细输出

# 使用示例
semanticsql-agent generate --database shop_db --output data.jsonl
```

### 9.3 输出格式

```json
[
  {
    "id": "sample_001",
    "combination_id": "sales_analysis_simple",
    "question": "查询本月的销售订单",
    "sql": "SELECT * FROM orders WHERE MONTH(order_date) = MONTH(NOW())",
    "scenario": {
      "main_name": "销售分析",
      "sub_name": "销售统计",
      "complexity": "simple"
    },
    "operations": ["SELECT", "WHERE"],
    "validation": {
      "syntax_valid": true,
      "execution_success": true,
      "row_count": 156
    },
    "quality_score": 0.75,
    "timestamp": "2024-01-15T10:30:00Z"
  },
  ...47个更多样本
]
```

## 10. 实现细节

### 10.1 关键类设计

#### SQLAgent类
- 继承BaseAgent
- 初始化所有工具和记忆
- 提供generate_training_data()方法
- 处理Agent执行结果的提取

#### ScenarioOperationTool类
- 最重要的工具，内部封装三层for循环
- 支持get_all_combinations模式
- 为每个组合生成专门的提示词
- 参考pipeline的遍历逻辑

#### DatabaseAnalysisMemory类
- 基于langchain_core.memory.BaseMemory
- 自动的工具名称到记忆键映射
- 支持Agent通过提示词访问记忆

### 10.2 工具间协作机制

1. **分析工具**：按需执行，结果保存到记忆
2. **场景工具**：一次性生成所有组合，保存到记忆
3. **生成工具**：逐个处理组合，自动从记忆读取信息
4. **验证工具**：对每个生成的SQL进行验证
5. **反思工具**：评估质量，提供简单的修正建议

### 10.3 质量保证机制

- **语法验证**：确保SQL语法正确
- **执行测试**：实际执行SQL验证可行性
- **反思评估**：评估问题-SQL的语义匹配度
- **自主修正**：Agent根据反思建议自主选择修正策略

## 11. 架构优势

### 11.1 设计优势

1. **Agent完全自主**：
   - 无外部循环控制逻辑
   - Agent根据任务自主决策所有工具调用
   - 符合ReAct的自主决策原则

2. **记忆驱动协作**：
   - 工具结果自动保存到记忆
   - 后续工具自动从记忆读取信息
   - 无需手动参数传递

3. **质量优先**：
   - 每个样本都经过完整的生成-验证-反思流程
   - 单条生成+立即反思，确保质量
   - Agent可以自主修正问题

4. **架构简洁**：
   - 核心逻辑封装在工具内部
   - Agent接口极简
   - 易于维护和扩展

### 11.2 与传统方案的对比

| 特征 | ❌ 传统流水线方案 | ✅ Agent自主方案 |
|------|-----------------|-----------------|
| **控制方式** | 外部循环控制 | Agent完全自主 |
| **工具调用** | 硬编码调用顺序 | Agent自主选择 |
| **参数传递** | 手动传递参数 | 记忆自动协作 |
| **错误处理** | 外部异常处理 | Agent自主修正 |
| **扩展性** | 修改流程代码 | 添加工具即可 |

## 12. 开发指南

### 12.1 添加新工具

1. 继承BaseTool
2. 实现_run方法
3. 在memory_mapping中添加映射
4. 创建工具专用提示词模板

### 12.2 修改场景配置

1. 编辑scenarios.yaml配置文件
2. 更新operation_mapping.yaml
3. ScenarioOperationTool自动加载新配置

### 12.3 调试和优化

1. 使用--verbose查看详细执行过程
2. 检查trajectory记录了解Agent决策过程
3. 分析memory状态确认工具协作正常

---

**本文档保留了所有核心设计要点，删除了重复和错误内容，确保逻辑一致性和实用性。**