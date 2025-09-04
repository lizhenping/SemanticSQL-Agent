# SemanticSQL Agent 设计规范

## 1. 项目概述

### 1.1 项目定位
SemanticSQL Agent 是一个基于 ReAct 智能体架构的 **NL2SQL 训练数据生成系统**。

**核心功能**：
- 📊 **智能数据库分析**：自动提取数据库结构、识别业务领域、分析表关系
- 🎯 **场景化问题生成**：基于预定义业务场景模板，按设定数量生成自然语言问题和对应的 SQL 查询对
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

## 2. 功能规范

### 2.1 核心功能

#### 2.1.1 数据库分析（一次性执行，结果记忆）

**执行时机**：任务开始时执行一次，结果保存在Agent记忆中供全程使用

**分析工具链（按推荐执行顺序）**：
1. **extract_schema**：提取数据库物理结构
   - 表结构、列信息、数据类型
   - 主键、外键、索引信息
   - 约束条件（唯一、非空等）

2. **domain_analysis**：识别业务领域特征
   - 基于表名和字段名的语义分析
   - 识别业务实体（用户、订单、产品等）
   - 推断业务流程和关系

3. **field_classification**：字段语义分类
   - 标识符字段（ID、编码）
   - 时间戳字段（创建时间、更新时间）
   - 数值字段（金额、数量、比率）
   - 分类字段（状态、类型、级别）
   - 描述字段（名称、备注、说明）

4. **column_meaning**：列业务含义分析
   - 分析每个列在业务中的具体作用
   - 识别关键业务字段（如订单金额、用户等级）
   - 理解列值的业务规则和约束

5. **table_meaning**：表业务含义分析
   - 分析每个表的业务职责和功能
   - 识别核心业务表（如用户表、订单表）
   - 理解表在业务流程中的位置

6. **er_analysis**：实体关系分析
   - 显式关系（外键约束）
   - 隐式关系（命名规律推断）
   - 关系类型（一对一、一对多、多对多）
   - 实体重要性评估

#### 2.1.2 基于纯ReAct模式的数据生成流程

**核心设计原则**：
- **外部大循环**：简单的数量控制，负责迭代生成多个样本
- **内部纯ReAct**：Agent完全自主决策，拥有所有工具访问权限
- **提示词引导**：通过提示词提供思考流程指导，不强制执行顺序
- **记忆驱动**：自动管理和共享数据库分析结果

**真正的ReAct自主决策模式**：Agent通过思考-行动-观察循环，完全自主决定执行策略

**简化的执行架构图**：
```mermaid
graph TB
    Start[开始任务] --> Loop[外部大循环: for i in range(count)]
    Loop --> Task[任务: 生成第i+1个样本]
    Task --> Agent[Agent完全自主决策]
    
    Agent --> React[ReAct推理循环]
    React --> Thought[Thought: 分析当前状态]
    Thought --> Action[Action: 选择合适工具]
    Action --> Input[Action Input: 准备参数]
    Input --> Execute[执行工具]
    Execute --> Observe[Observation: 观察结果]
    
    Observe --> Complete{任务完成?}
    Complete -->|否| Thought
    Complete -->|是| Answer[Final Answer: 训练样本]
    
    Answer --> Save[保存样本]
    Save --> Next{继续下一个?}
    Next -->|是| Loop
    Next -->|否| End[完成所有生成]
    
    style Agent fill:#e1f5fe
    style React fill:#f3e5f5
    style Loop fill:#e8f5e8
```

**简化的Agent决策模式**：

Agent接收到"生成第N个训练样本"的任务后，完全自主决策执行流程：

1. **状态检查**：检查记忆中是否有足够的数据库分析信息
2. **按需分析**：如果缺少信息，自主选择需要的分析工具
3. **场景生成**：选择合适的业务场景
4. **问题构建**：生成自然语言问题
5. **SQL实现**：将问题转换为SQL查询
6. **验证测试**：确保SQL正确可执行
7. **质量评估**：反思生成质量，必要时自主修正

**关键特点**：
- **完全自主**：没有外部预设的执行步骤
- **智能记忆**：自动利用和更新数据库分析结果
- **按需执行**：根据实际需求选择工具，避免不必要的分析
- **自我修正**：基于反思结果自主选择修正策略

**记忆机制**：
- **数据库分析结果必须完整记忆**：一次性分析数据库，结果贯穿整个过程
- **上下文保持**：Agent在整个执行过程中维护分析结果的记忆
- **避免重复分析**：已分析的结构信息在后续步骤中直接使用

**工具类型区分**：
- **思考工具（sequential_thinking）**：用于深度分析和推理，在需要复杂决策时调用
- **反思工具（sql_reflection）**：SQL执行后的质量评估和问题诊断

**简化的执行机制**：

```python
# 外部：简单的大循环
def generate_training_data(self, count: int):
    results = []
    
    for i in range(count):
        # 每次迭代都是独立的ReAct任务
        task = f"生成第{i+1}个高质量NL2SQL训练样本"
        
        # 完全交给Agent自主决策
        result = self.agent_executor.invoke({
            "input": task,
            "iteration": i,
            "database_name": self.db_config.database
        })
        
        sample = self._extract_sample(result)
        if sample:
            results.append(sample)
    
    return results
```

**Agent内部的自主推理示例**：
```
用户: "生成第1个高质量NL2SQL训练样本"

Thought: 需要生成训练样本。先检查是否了解数据库。
Action: 检查记忆状态，必要时调用schema_extraction
Observation: 获得数据库结构信息

Thought: 选择一个业务场景。  
Action: scenario_tool
Observation: 选择了"销售分析"场景

Thought: 根据场景复杂度选择SQL操作。
Action: operation_selection
Observation: 选择了GROUP BY聚合操作

Thought: 基于场景和操作生成问题。
Action: question_generation  
Observation: "统计每月销售总额"

Thought: 将问题转换为SQL。
Action: sql_generation
Observation: "SELECT MONTH(order_date), SUM(amount) FROM orders GROUP BY MONTH(order_date)"

Thought: 验证SQL并执行测试。
Action: sql_validation -> sql_execution
Observation: 执行成功，返回12行数据

Thought: 评估生成质量。
Action: sql_reflection
Observation: 质量良好，无需修正

Thought: 样本生成完成。
Final Answer: {"question": "统计每月销售总额", "sql": "SELECT...", "quality_score": 0.85}
```

**新的设计原则**：
1. **Agent完全自主**：没有外部的阶段控制，Agent根据需求自主选择工具
2. **记忆自动管理**：分析结果自动保存和加载，跨样本共享
3. **按需分析**：只有缺少必要信息时才执行分析工具
4. **提示词引导**：通过提示词提供思考流程建议，但不强制执行

**思考工具（sequential_thinking）调用时机**：
- **初始规划**：开始任务时，思考整体执行策略
- **复杂场景设计**：当需要设计涉及多表关联的复杂查询场景时
- **错误诊断**：当SQL执行失败且原因不明时，进行深度分析
- **优化决策**：当有多种可能的SQL实现方式时，评估最优方案
- **跨步骤决策**：当需要决定是否回退到更早的步骤时

**反思工具（sql_reflection）的综合评估**：

1. **执行结果层面**：
   - SQL是否成功执行
   - 返回数据量是否合理
   - 执行时间是否可接受
   - 结果数据是否符合业务逻辑

2. **语义匹配层面**：
   - SQL是否准确实现了问题的意图
   - 问题描述与SQL逻辑是否一致
   - 是否遗漏或多余了查询条件

3. **生成质量层面**：
   - 问题的自然语言是否清晰、无歧义
   - SQL是否符合最佳实践
   - 是否充分利用了数据库结构信息

4. **记忆使用的正确性**：
   - 是否正确使用了数据库分析记忆
   - 领域理解是否准确
   - 表关系是否正确识别
   - 字段含义是否理解正确

**反思工具的智能分析**：

sql_reflection 基于SQL执行结果，能够：
- 定位问题源头（数据库分析、问题生成、SQL生成）
- 分析根本原因（为什么出错）
- 推荐修正工具（重新分析或重新生成）
- 提供参数建议（如何调用工具）

**注意**：场景和操作选择是预定义的，不会被修正

**反思后的决策流程**：
```
sql_reflection 发现问题并给出建议
    ↓
Agent 根据 recommended_action 决定：
├─ 直接调用建议的工具（简单问题）
└─ 先调用 sequential_thinking 深度分析（复杂问题）
    ↓
执行修正：
    1. 问题生成是否准确？
       - 输入：场景+操作+数据库记忆
       - 输出：自然语言问题
       - 检查：问题是否清晰、完整、无歧义
       - 检查：是否正确使用了数据库记忆
    
    2. SQL生成是否正确？
       - 输入：问题+数据库记忆
       - 输出：SQL查询
       - 检查：SQL是否准确实现问题意图
       - 检查：是否正确使用了数据库记忆
    
    3. 数据库记忆的使用情况：
       - schema_info：是否使用了正确的表名和字段名
       - field_classification：是否理解了字段的实际含义和类型
       - er_analysis：是否正确处理了表之间的关系
       - domain_analysis：是否符合业务领域的惯例
    ↓
定位问题源头步骤
    ↓
只重新执行该步骤，保持其他步骤结果不变
```

**问题源头分析示例**：

示例1 - SQL生成错误：
```python
reflection_analysis = {
    "执行错误": "Table 'orders' doesn't exist",
    "步骤分析": {
        "SQL生成": "使用了orders表，但schema中只有order_info表",
        "问题生成": "问题中提到'订单'，正确",
        "记忆检查": "memory['schema_info']中确实只有order_info表"
    },
    "问题源头": "SQL生成步骤 - 没有正确使用schema_info",
    "修正方案": "重新执行sql_generation，确保使用memory['schema_info']中的正确表名"
}
```

示例2 - 记忆使用不当：
```python
reflection_analysis = {
    "执行结果": "SQL执行成功但结果不合理",
    "步骤分析": {
        "SQL": "SELECT * FROM users WHERE status = 'active'",
        "问题": "查询所有有效用户",
        "记忆检查": {
            "field_classification": "status字段被分类为'状态码'，值为0/1",
            "domain_analysis": "该系统使用数字表示状态"
        }
    },
    "问题源头": "SQL生成时没有参考field_classification的字段类型信息",
    "修正方案": "重新执行sql_generation，使用field_classification理解status字段"
}

# 修正执行
new_sql = sql_generation(
    question="查询所有有效用户",
    schema_info=memory["schema_info"],
    field_info=memory["field_classification"]  # 确保使用字段分类信息
)
# 结果：SELECT * FROM users WHERE status = 1
```

**核心特点**：
- **动态适应**：Agent根据数据库特征调整生成策略
- **智能反思**：执行SQL后主动反思结果质量
- **自主优化**：根据反思结果自动优化或重新生成
- **完全自主**：所有决策由Agent基于提示词引导做出，无硬编码步骤

#### 2.1.3 验证与优化
- **语法验证**：检查 SQL 语法正确性
- **执行测试**：实际执行 SQL 验证可行性
- **反思优化**：分析执行结果，提供优化建议

#### 2.1.4 简化的工具使用规范

**统一的工具访问原则**：
- Agent拥有所有工具的访问权限，无外部限制
- 根据任务需求和当前状态自主选择工具
- 记忆系统自动管理分析结果的保存和加载

**工具分类及特点**：

| 工具类别 | 工具名称 | 主要特点 | Agent使用策略 |
|---------|---------|---------|-------------|
| 分析工具 | schema_extraction<br>domain_analysis<br>field_classification<br>column_meaning<br>table_meaning<br>er_analysis | 结果保存在记忆中<br>可重复执行更新记忆 | 按需调用，优先检查记忆 |
| 生成工具 | scenario_tool<br>operation_selection<br>question_generation<br>sql_generation | 基于记忆和上下文生成内容 | 每个样本都需要调用 |
| 验证工具 | sql_validation<br>sql_execution | 确保SQL正确性和可执行性 | 生成SQL后必须验证 |
| 反思工具 | sql_reflection | 评估质量，提供修正建议 | 执行后自主决定是否反思 |
| 思考工具 | sequential_thinking | 深度分析复杂问题 | 遇到复杂情况时自主调用 |

**记忆机制简化要点**：
1. 所有分析结果自动保存在记忆中
2. Agent自动从记忆中获取所需信息
3. 记忆内容可以动态更新
4. 跨样本自动共享分析结果

**工具使用的核心原则**：

Agent通过提示词指导，自主决策工具的使用时机和顺序：

```python
# 简化的代码架构示例
class SQLAgent:
    def generate_training_data(self, count: int):
        """外部大循环 + 内部纯ReAct"""
        results = []
        
        for i in range(count):
            # 每个样本都是独立的ReAct任务
            task = f"生成第{i+1}个高质量NL2SQL训练样本"
            
            # Agent完全自主决策执行流程
            result = self.agent_executor.invoke({
                "input": task,
                "iteration": i,
                "database_name": self.db_config.database
            })
            
            sample = self._extract_sample(result)
            if sample:
                results.append(sample)
        
        return results
```

**Agent自主决策的典型流程**：
1. **智能检查**：优先检查记忆中是否有所需信息
2. **按需分析**：缺少信息时自主选择分析工具
3. **场景选择**：根据iteration和数据库特点选择场景
4. **内容生成**：依次生成问题和SQL
5. **质量保证**：验证、执行、反思
6. **自主修正**：发现问题时自主选择修正策略

**关键优势**：
- **架构简单**：只有一个Agent类，一个大循环
- **完全自主**：Agent根据提示词自主决策，无外部控制
- **高效记忆**：分析结果跨样本自动共享
- **智能修正**：基于反思结果自主选择修正工具

### 2.2 分析工具详细说明

#### 2.2.1 列业务含义分析工具（column_meaning）

**功能定位**：
- 深入理解每个列在业务中的具体含义和作用
- 识别列的业务规则、取值范围、业务约束
- 为后续的问题生成和SQL生成提供列级别的业务理解

**输入依赖**：
- `schema_info`：基础的表结构信息
- `domain_analysis`：业务领域信息，帮助理解业务上下文
- `field_classification`：字段分类结果，了解字段的基本类型

**分析内容**：
1. **业务含义识别**：
   - 订单金额列 → 记录每笔订单的总金额，包含税费
   - 用户等级列 → 表示用户的会员等级（普通/银牌/金牌/钻石）
   - 创建时间列 → 记录数据首次创建的时间戳

2. **业务规则推断**：
   - 状态列的有效值（如：待支付/已支付/已取消/已退款）
   - 金额列的取值范围（如：必须大于0）
   - 日期列的有效范围（如：不能早于系统上线日期）

3. **列间关系理解**：
   - 订单总额 = 商品金额 + 运费 - 优惠金额
   - 更新时间必须晚于或等于创建时间

#### 2.2.2 表业务含义分析工具（table_meaning）

**功能定位**：
- 理解每个表在整个业务系统中的职责和定位
- 识别核心业务表、辅助表、字典表等不同类型
- 为场景生成提供表级别的业务理解

**输入依赖**：
- `schema_info`：基础的表结构信息
- `domain_analysis`：业务领域信息
- `column_meanings`：列的业务含义，帮助理解表的整体职责

**分析内容**：
1. **表职责识别**：
   - 用户表：存储系统所有注册用户的基本信息和状态
   - 订单表：记录所有交易订单的详细信息
   - 商品表：维护商品目录和库存信息

2. **表类型分类**：
   - 核心业务表：用户表、订单表、商品表
   - 关系表：用户收藏表、购物车表
   - 字典表：地区表、分类表、配置表
   - 日志表：操作日志表、登录日志表

3. **表在业务流程中的位置**：
   - 上游表：基础数据表（用户、商品）
   - 中游表：交易过程表（购物车、订单）
   - 下游表：结果数据表（评价、售后）

### 2.3 数据生成规范

#### 2.3.1 场景类型
- **基础查询**：单表查询、条件筛选
- **关联查询**：多表 JOIN、子查询
- **聚合统计**：GROUP BY、聚合函数
- **时间分析**：时间范围、趋势分析
- **复杂查询**：窗口函数、CTE、复杂条件

#### 2.3.2 难度分布
```yaml
difficulty_distribution:
  easy: 30%    # 基础单表查询
  medium: 20%  # 关联和聚合查询
  hard: 30%    # 复杂查询和高级特性
  expert: 20%    # 专家级别查询和高级特性
```

#### 2.3.3 质量标准
- SQL 语法必须正确
- 问题表述自然流畅
- SQL 与问题语义匹配
- 执行结果合理有效

## 3. 实现规范（基于 LangChain 框架）

### 3.1 LangChain 集成策略

#### 3.1.1 核心组件映射

**使用 LangChain 实现的组件**：
1. **Agent 框架**：
   - 使用 `langchain.agents.create_react_agent` 实现 ReAct 模式
   - 使用 `AgentExecutor` 管理执行流程
   - 利用 LangChain 的工具调用机制

2. **记忆管理**：
   - 基于 `langchain.memory.BaseMemory` 实现自定义记忆
   - 可选使用 `ConversationSummaryMemory` 存储摘要
   - 支持 `VectorStoreMemory` 进行相似性检索

3. **LLM 调用**：
   - 使用 `langchain.chat_models.ChatOpenAI` 连接 Qwen
   - 自动的重试和错误处理
   - 支持流式输出（如需要）

4. **工具系统**：
   - 继承 `langchain.tools.BaseTool`
   - 自动的参数验证和序列化
   - 与 Agent 的无缝集成

5. **提示词管理**：
   - 使用 `langchain.prompts` 模块
   - 结构化的提示词模板
   - 支持 Few-shot 学习

6. **回调系统**：
   - 基于 `langchain.callbacks`
   - 自动的执行跟踪
   - 支持自定义回调

### 3.2 Agent实现规范

#### 3.2.1 简化的SQLAgent设计

**核心实现原则**：
```python
# ✅ 简化的ReAct Agent实现
from langchain.agents import create_react_agent, AgentExecutor
from langchain.chat_models import ChatOpenAI

class SQLAgent:
    """简化的SQL Agent - 真正的ReAct模式"""
    
    def __init__(self, settings, db_config):
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
        prompt = self._get_simple_prompt()
        agent = create_react_agent(self.llm, self.tools, prompt)
        
        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            memory=self.memory,
            verbose=True,
            max_iterations=30,
            callbacks=[TrajectoryCallback()]
        )
    
    def generate_training_data(self, count: int) -> List[Dict]:
        """外部大循环 + 内部纯ReAct"""
        results = []
        
        # 🔄 统一的大循环
        for i in range(count):
            print(f"🎯 生成第 {i+1}/{count} 个样本...")
            
            # 每次迭代都是独立的ReAct任务
            sample = self._generate_single_sample(i)
            
            if sample:
                results.append(sample)
                print(f"✅ 成功生成样本 {i+1}")
            else:
                print(f"❌ 样本 {i+1} 生成失败")
        
        return results
    
    def _generate_single_sample(self, iteration: int) -> Optional[Dict]:
        """生成单个样本 - 完全由Agent自主决策"""
        
        task = f"""生成一个高质量的NL2SQL训练样本（第{iteration + 1}个）。
        
要求：
1. 确保对数据库有充分理解
2. 选择合适的业务场景  
3. 生成清晰的自然语言问题
4. 生成正确的SQL查询
5. 验证SQL可执行性
6. 确保问题与SQL语义匹配

请完全自主决策执行流程。"""

        try:
            # 完全交给Agent自主决策
            result = self.agent_executor.invoke({
                "input": task,
                "iteration": iteration,
                "database_name": self.db_config.database
            })
            
            return self._extract_sample_from_result(result)
            
        except Exception as e:
            self.logger.error(f"Sample {iteration + 1} generation failed: {e}")
            return None
```

**关键简化点**：
- **去除阶段管理**：删除所有`_determine_execution_stage()`等复杂逻辑
- **统一工具访问**：Agent拥有所有工具，无外部过滤
- **简单循环控制**：外部只负责数量控制，内部完全自主
- **提示词驱动**：通过提示词引导，而非硬编码流程

#### 3.2.2 简化的提示词系统设计

**关键原则**：在提示词中提供思考流程指导，但不强制执行顺序

**简化的系统提示词模板**：
```python
from langchain.prompts import ChatPromptTemplate

# 简化的系统提示词 - 提供指导但不强制流程
system_prompt = """你是专业的NL2SQL训练数据生成专家。

## 当前任务  
{{input}}

## 环境信息
- 数据库: {{database_name}}
- 样本编号: {{iteration + 1}}
- 记忆状态: {{memory_summary}}

## 可用工具
{{tools}}

## 思考流程建议（仅供参考，可自主调整）

### 🧠 生成单个样本的常见思考路径：

1. **状态检查**：
   - 我是否已经了解数据库结构？
   - 记忆中有哪些可用的分析信息？

2. **按需分析**（如果记忆中信息不足）：
   - schema_extraction: 了解表结构
   - domain_analysis: 识别业务领域
   - field_classification: 理解字段类型
   - column_meaning/table_meaning: 理解业务含义
   - er_analysis: 分析表关系

3. **场景构建**：
   - scenario_tool: 选择合适的业务场景
   - operation_selection: 根据场景选择SQL操作类型

4. **内容生成**：
   - question_generation: 生成自然语言问题
   - sql_generation: 将问题转换为SQL

5. **质量保证**：
   - sql_validation: 验证SQL语法
   - sql_execution: 执行SQL测试
   - sql_reflection: 评估质量，决定是否需要修正

6. **智能修正**（如果质量不达标）：
   - sequential_thinking: 深度分析问题根源
   - 重新调用相应工具进行修正

### 🎯 决策原则
- **记忆优先**: 优先使用已有的分析结果
- **按需执行**: 只调用真正需要的工具
- **质量导向**: 确保每个样本都是高质量的
- **自主决策**: 根据实际情况灵活调整执行策略

## ReAct格式
Thought: 分析当前情况，决定下一步
Action: 工具名称
Action Input: {{"参数": "值"}}  
Observation: 工具返回结果
... (重复直到完成)
Final Answer: 最终的训练样本

**记住**: 这些建议只是参考，你有完全的自主决策权！根据实际需求灵活选择工具和执行顺序。

### 💡 ReAct反思的正确方式

当你发现质量问题时，应该这样自主推理：

```
Thought: 反思发现问题，我需要分析具体原因。
Action: sequential_thinking
Observation: 分析结果指出具体问题

Thought: 根据分析结果，我认为需要重新生成更好的问题。
Action: question_generation
Observation: 生成了改进的问题

Thought: 现在用新问题生成SQL。
Action: sql_generation
Observation: 生成了新的SQL
```

**注意**：不要想着"回到某个步骤"，而是"我现在需要做什么"。
"""

# 创建简化的提示词模板
prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("human", "{input}"),
    ("assistant", "{agent_scratchpad}")
])
```

### **🎯 提示词设计的ReAct兼容性原则**

#### **✅ 正确的提示词设计方式**

1. **提供思考建议，不强制执行**：
```python
# ✅ 正确：给出建议但强调自主决策
"""
## 常见思考路径（仅供参考）：
1. 检查记忆状态
2. 按需分析数据库
3. 选择场景和操作
4. 生成问题和SQL
5. 验证和反思

**记住**：这只是建议，你可以根据实际情况灵活调整！
"""

# ❌ 错误：硬性要求执行顺序
"""
## 执行步骤（必须按顺序）：
1. 首先执行 schema_extraction
2. 然后执行 domain_analysis
3. 接下来执行 question_generation
"""
```

2. **描述工具用途，不指定使用时机**：
```python
# ✅ 正确：描述工具功能
"""
可用工具：
- schema_extraction: 提取数据库表结构信息
- sql_reflection: 评估SQL质量，分析问题特征
- sequential_thinking: 深度分析复杂问题
"""

# ❌ 错误：指定使用时机
"""
工具使用规则：
- 必须先调用 schema_extraction
- SQL执行失败时必须调用 sql_reflection
- 发现问题时必须调用 sequential_thinking
"""
```

3. **鼓励自主思考，不提供决策树**：
```python
# ✅ 正确：鼓励自主推理
"""
根据当前情况自主决策：
- 我需要什么信息？
- 哪个工具能帮助我？
- 现在最重要的是什么？
"""

# ❌ 错误：提供决策树
"""
决策规则：
if 缺少schema信息:
    调用 schema_extraction
elif 需要生成问题:
    调用 question_generation
"""
```

#### **🧠 思考流程指导的最佳实践**

提示词中的思考流程指导应该：

1. **启发式而非指令式**：
   - ✅ "你可能需要考虑..."
   - ❌ "你必须执行..."

2. **示例式而非规则式**：
   - ✅ "典型的思考路径可能是..."
   - ❌ "执行规则是..."

3. **建议式而非强制式**：
   - ✅ "建议的工作流程（可自主调整）"
   - ❌ "标准工作流程（必须遵循）"

这样的提示词设计既能给Agent提供有用的指导，又完全符合ReAct的自主决策原则。

### **❌ 错误的反思决策流程 vs ✅ 正确的ReAct推理**

#### **❌ 错误示例：外部控制的决策树**
```python
# 这是错误的设计 - 违背ReAct原则
def handle_reflection_result(reflection_result):
    if reflection_result["needs_revision"]:
        if reflection_result["problem_type"] == "sql_error":
            return call_tool("sql_generation")  # 硬编码的决策
        elif reflection_result["problem_type"] == "question_unclear":
            return call_tool("question_generation")  # 硬编码的决策
    else:
        return save_sample()  # 硬编码的流程
```

#### **✅ 正确示例：Agent自主推理**
```
Agent完全自主的推理过程：

Thought: 我刚执行了SQL，现在评估一下质量。
Action: sql_reflection
Action Input: {"sql": "SELECT * FROM users", "execution_result": {...}}
Observation: {"quality_score": 0.3, "issues": ["查询过于简单，缺乏业务价值"]}

Thought: 质量分数很低，问题确实太简单了。我需要重新思考这个业务场景。
Action: sequential_thinking  
Action Input: {"problem": "生成的查询缺乏业务价值", "context": {...}}
Observation: {"analysis": "应该添加筛选条件和聚合分析，体现更复杂的业务需求"}

Thought: 分析得对，我需要重新设计一个更有价值的问题。
Action: question_generation
Action Input: {"scenario": "用户分析", "operations": ["WHERE", "GROUP BY"], "complexity": "medium"}
Observation: {"question": "统计不同城市的活跃用户数量"}

Thought: 这个问题更好，现在生成对应的SQL。
Action: sql_generation
Action Input: {"question": "统计不同城市的活跃用户数量", "schema_info": {...}}
Observation: {"sql": "SELECT city, COUNT(*) FROM users WHERE status='active' GROUP BY city"}

Thought: 验证新的SQL。
Action: sql_validation
Action Input: {"sql": "SELECT city, COUNT(*) FROM users WHERE status='active' GROUP BY city"}
Observation: {"valid": true}

Thought: 执行SQL测试。
Action: sql_execution
Action Input: {"sql": "..."}
Observation: {"success": true, "row_count": 25}

Thought: 再次评估质量。
Action: sql_reflection
Action Input: {"sql": "...", "execution_result": {...}, "question": "统计不同城市的活跃用户数量"}
Observation: {"quality_score": 0.87, "issues": [], "needs_revision": false}

Thought: 现在质量很好，样本生成完成。
Final Answer: {"question": "统计不同城市的活跃用户数量", "sql": "SELECT city, COUNT(*) FROM users WHERE status='active' GROUP BY city", "quality_score": 0.87}
```

#### **关键差异总结**

| 方面 | ❌ 错误的流程控制 | ✅ 正确的ReAct推理 |
|------|-----------------|------------------|
| **决策主体** | 外部代码根据规则决策 | Agent根据思考自主决策 |
| **工具选择** | 预设的问题类型→工具映射 | Agent根据实际需求选择工具 |
| **执行流程** | 固定的"回到某步骤"逻辑 | 自然的"我现在需要做什么"推理 |
| **错误处理** | 硬编码的if-else分支 | Agent自主分析和应对 |
| **灵活性** | 受限于预设的决策规则 | 完全灵活，适应各种情况 |

**简化的记忆机制实现**：
```python
from langchain.memory import BaseMemory

class DatabaseAnalysisMemory(BaseMemory):
    """简化的数据库分析记忆管理"""
    
    def __init__(self):
        self.analysis_data = {}  # 存储所有分析结果
        self.generation_count = 0  # 跟踪生成进度
    
    @property
    def memory_variables(self) -> List[str]:
        return ["memory_summary", "analysis_data"]
    
    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """自动加载所有分析结果供Agent使用"""
        return {
            "memory_summary": self._get_summary(),
            **self.analysis_data  # 直接提供所有分析数据
        }
    
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> None:
        """自动识别和保存工具执行结果"""
        # 自动识别分析工具的输出并保存
        self._auto_save_analysis_results(outputs)
    
    def _get_summary(self) -> str:
        """生成记忆状态摘要"""
        if not self.analysis_data:
            return "初始状态，无分析数据"
        
        available_info = list(self.analysis_data.keys())
        return f"已有分析: {', '.join(available_info)}"
```

#### 3.2.3 Agent自主的反思-修正机制

**完全由Agent自主执行的反思流程**：

Agent在生成样本过程中，会自主决定何时进行反思和修正：

```
Agent内部推理（无外部控制）：

Thought: SQL执行完成，我需要评估质量。
Action: sql_reflection
Action Input: {"sql": "...", "execution_result": "...", "question": "..."}
Observation: {"quality_score": 0.6, "needs_revision": true, "issues": ["SQL语法错误"]}

Thought: 质量不达标，有语法错误。我需要重新生成SQL。
Action: sql_generation
Action Input: {"question": "...", "schema_info": "..."}
Observation: 生成了修正后的SQL

Thought: 重新验证和执行修正后的SQL。
Action: sql_validation
Action Input: {"sql": "..."}
Observation: 语法正确

Action: sql_execution  
Action Input: {"sql": "..."}
Observation: 执行成功

Thought: 再次评估质量。
Action: sql_reflection
Action Input: {"sql": "...", "execution_result": "..."}
Observation: {"quality_score": 0.85, "needs_revision": false}

Thought: 质量达标，样本生成完成。
Final Answer: {"question": "...", "sql": "...", "quality_score": 0.85}
```

**关键特点**：
- **完全自主**：没有外部的修正控制逻辑
- **智能反思**：Agent自主决定何时反思和如何修正
- **记忆驱动**：自动利用记忆中的分析结果
- **提示词引导**：通过提示词建议，但不强制执行

**简化的实现要点**：

1. **自动记忆管理**：
```python
# 记忆系统自动识别和保存分析结果
class DatabaseAnalysisMemory(BaseMemory):
    def save_context(self, inputs, outputs):
        # 自动识别工具类型并保存结果
        self._auto_save_tool_results(outputs)
    
    def load_memory_variables(self, inputs):
        # 自动加载所有可用的分析数据
        return {"memory_summary": "...", **self.analysis_data}
```

2. **Agent自主的工具选择**：
```python
# Agent完全根据提示词和当前状态自主选择工具
# 无外部的工具过滤或流程控制
```

3. **提示词中的流程建议**：
```python
# 在提示词中提供思考建议（不强制执行）
system_prompt = """
## 思考流程建议：
1. 检查记忆中是否有足够信息
2. 按需调用分析工具
3. 选择场景和操作
4. 生成问题和SQL
5. 验证和反思
6. 必要时自主修正

**记住**：这只是建议，你可以根据实际情况灵活调整！
"""
```

## 4. 接口规范

### 4.1 工具接口（基于 LangChain）

```python
from langchain.tools import BaseTool as LangChainBaseTool
from langchain.pydantic_v1 import BaseModel, Field

class BaseTool(LangChainBaseTool):
    """继承 LangChain 的工具基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """工具唯一标识，用于注册和调用"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """工具功能描述，用于 LLM 理解"""
        pass
    
    @abstractmethod
    def run(self, **kwargs) -> Dict[str, Any]:
        """
        工具执行接口
        
        返回格式：
        {
            "success": bool,      # 执行是否成功
            "data": Any,         # 成功时的返回数据
            "error": str,        # 失败时的错误信息
            "metadata": dict     # 可选的元数据
        }
        """
        pass

# 示例：基于 LangChain 的工具实现
class SchemaExtractionTool(BaseTool):
    """数据库结构提取工具"""
    name = "extract_schema"
    description = "提取数据库的表结构、列信息、约束等"
    
    # 定义输入参数
    class InputSchema(BaseModel):
        database_name: str = Field(description="要分析的数据库名称")
    
    args_schema = InputSchema
    
    def _run(self, database_name: str) -> dict:
        """同步执行"""
        # 连接数据库
        # 提取结构信息
        # 返回结果
        return {
            "tables": [...],
            "columns": [...],
            "constraints": [...]
        }
    
    async def _arun(self, database_name: str) -> dict:
        """异步执行（可选）"""
        # 异步实现
        pass
```

### 4.2 智能体接口

```python
class BaseAgent(ABC):
    """智能体基类接口规范"""
    
    @abstractmethod
    def run(self, task: str, context: Dict = None) -> AgentExecution:
        """执行任务"""
        pass
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """获取系统提示词"""
        pass
    
    def register_tool(self, tool: BaseTool) -> None:
        """注册工具"""
        pass
```

### 4.3 命令行接口

```bash
# 基础生成命令
semanticsql-agent generate [OPTIONS]

Options:
  --config PATH           配置文件路径
  --count INTEGER        生成数据条数 [default: 100]
  --db-type TEXT         数据库类型 [mysql]
  --host TEXT            数据库主机
  --port INTEGER         数据库端口
  --database TEXT        数据库名称
  --username TEXT        用户名
  --password TEXT        密码
  --output PATH          输出文件路径
  --format TEXT          输出格式 [json|jsonl|csv]
  --verbose              详细输出
  --help                 显示帮助信息

# 其他命令
semanticsql-agent test-connection  # 测试数据库连接
semanticsql-agent init            # 初始化配置
semanticsql-agent version         # 显示版本信息
```

## 4. 数据模型规范

### 4.1 核心数据结构

#### 4.1.1 执行记录
```python
@dataclass
class AgentStep:
    """单个执行步骤"""
    step_type: AgentStepType  # thought/action/observation
    content: str              # 步骤内容
    timestamp: datetime       # 时间戳
    tool_name: Optional[str]  # 使用的工具
    tool_output: Optional[Any]  # 工具输出
    error: Optional[str]      # 错误信息

@dataclass
class AgentExecution:
    """完整执行记录"""
    task_id: str              # 任务ID
    task: str                 # 任务描述
    started_at: datetime      # 开始时间
    completed_at: Optional[datetime]  # 结束时间
    steps: List[AgentStep]    # 执行步骤
    final_result: Optional[Any]  # 最终结果
    status: str               # running/completed/failed
    error: Optional[str]      # 错误信息
```

#### 4.1.2 生成数据
```python
@dataclass
class QueryScenario:
    """查询场景"""
    id: str
    category: str            # 场景类别
    business_purpose: str    # 业务目的
    complexity: str          # easy/medium/hard
    applicable_tables: List[str]

@dataclass
class GeneratedExample:
    """生成的训练样本"""
    id: str
    scenario_id: str
    question: str            # 自然语言问题
    sql: str                # SQL 查询
    difficulty: str          # 难度级别
    validation_result: Dict  # 验证结果
    execution_result: Dict   # 执行结果
    quality_score: float     # 质量分数
```

### 4.2 配置规范

```yaml
# 完整配置示例
database:
  type: mysql              # 数据库类型
  host: localhost         
  port: 3306              
  username: root          
  password: ${DB_PASSWORD}  # 支持环境变量
  database: shop_db       
  
llm:
  model: Qwen3-14B        # 模型名称
  base_url: http://192.168.200.216:9991/v1
  api_key: ${DASHSCOPE_API_KEY}
  temperature: 0.7        # 生成温度
  max_tokens: 4096        # 最大token数
  
agent:
  max_steps: 30           # 最大执行步骤
  enable_reflection: true # 启用反思
  verbose: true           # 详细日志
  
generation:
  default_count: 100           # 默认生成数量
  output_format: "jsonl"       # 输出格式
    
output:
  directory: ./output     # 输出目录
  format: json           # 默认格式
  save_intermediate: false  # 是否保存中间结果
```

## 5. 错误处理规范

### 5.1 错误分类
- **配置错误**：配置文件缺失、格式错误、必需参数缺失
- **连接错误**：数据库连接失败、LLM API 连接失败
- **执行错误**：工具执行失败、SQL 执行错误
- **验证错误**：SQL 语法错误、数据验证失败
- **系统错误**：内存不足、权限问题

### 5.2 错误处理策略

#### 使用统一的异常体系
所有异常都定义在 `models/exceptions.py` 中：
- `SemanticSQLException`: 基础异常类
- `ConfigurationError`: 配置相关异常
- `DatabaseError`: 数据库相关异常
- `LLMError`: LLM相关异常
- `ToolError`: 工具相关异常
- `AgentError`: Agent相关异常
- `ValidationError`: 验证相关异常

#### 工具级错误处理
```python
from semanticsql_agent.models.exceptions import (
    ToolExecutionError,
    ToolParameterError
)

# 在工具的 _run 方法中
def _run(self, **kwargs):
    try:
        # 参数验证
        if "memory" not in kwargs:
            raise ToolParameterError(
                tool_name=self.name,
                param_name="memory",
                reason="Missing required parameter"
            )
        
        # 执行逻辑
        result = self._execute(**kwargs)
        return result  # LangChain 会自动包装结果
        
    except Exception as e:
        # 转换为工具执行错误
        raise ToolExecutionError(
            tool_name=self.name,
            reason=str(e)
        ) from e

# Agent 级错误恢复
def _execute_with_retry(self, action: Dict, max_retries: int = 3):
    """带重试的执行"""
    for attempt in range(max_retries):
        try:
            return self._execute_tool(action)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            self.logger.warning(f"执行失败，重试 {attempt + 1}/{max_retries}")
            time.sleep(2 ** attempt)  # 指数退避
```

## 6. 日志规范

### 6.1 日志级别
- **DEBUG**：详细的调试信息，包括 LLM 交互
- **INFO**：正常的执行流程信息
- **WARNING**：警告信息，如重试、降级
- **ERROR**：错误信息，但不影响继续执行
- **CRITICAL**：严重错误，导致程序终止

### 6.2 日志格式
```python
# 日志配置
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'detailed': {
            'format': '%(asctime)s [%(levelname)s] %(name)s.%(funcName)s:%(lineno)d - %(message)s'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
            'stream': 'ext://sys.stdout'
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'detailed',
            'filename': 'semanticsql-agent.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console', 'file']
    }
}
```

## 7. 文档规范

### 7.1 代码文档
- 所有公共接口必须有 docstring
- 复杂逻辑添加行内注释
- 示例代码保持可运行

### 7.2 用户文档
- README.md：项目介绍和快速开始
- INSTALL.md：详细安装指南
- USAGE.md：使用教程
- API.md：API 参考

### 7.3 开发文档
- CONTRIBUTING.md：贡献指南
- DEVELOPMENT.md：开发环境搭建
- ARCHITECTURE.md：架构设计
- DESIGN.md：设计决策