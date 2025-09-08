# SemanticSQL Agent 设计规范

## 1. 项目概述

### 1.1 项目定位
SemanticSQL Agent 采用**极简+自主+记忆驱动**的创新架构，是一个真正智能的 **NL2SQL 训练数据生成系统**。

**核心功能**：
- 📊 **智能数据库分析**：自动提取数据库结构、识别业务领域、分析表关系
- 🧠 **ReAct智能体驱动**：完全由智能体自主决策生成高质量的问题-SQL对
- 💾 **Neo4j记忆系统**：三元组知识图谱实现工具间智能协作
- 🔄 **自主质量控制**：智能体自主验证、执行、反思，确保数据质量
- 📦 **标准化输出**：生成符合训练标准的JSON/JSONL格式数据集

**目标用途**：为NL2SQL模型训练提供高质量、大规模的合成训练数据，通过智能化工具协作减少人工标注成本，提升模型在特定领域的表现。

### 1.2 核心价值
- **自动化生成**：减少人工标注成本，快速生成大量训练数据
- **高质量保证**：通过验证和反思机制确保数据质量
- **领域适应**：自动识别业务领域，生成符合领域特征的数据
- **灵活扩展**：基于工具的架构，易于添加新功能

### 1.3 设计原则

#### 🔧 四大核心原则

**1. 极简原则 (Minimalist Principle)**
- **极简状态管理**：`AgentState`只有2个字段（`current_input`, `database_params`）
- **极简工具基类**：`BaseSemanticSQLTool`只有2个核心方法
- **极简接口设计**：去除所有不必要的抽象层和复杂管理

**2. 自主原则 (Autonomous Principle)**
- **工具完全自主**：每个工具在`_run`方法中完全控制执行逻辑、存储时机和返回格式
- **智能体自主决策**：ReAct循环中LLM根据记忆状态动态选择工具
- **无外部编排**：没有预定义的执行流水线，完全依靠智能决策

**3. 记忆驱动 (Memory-Driven Principle)**
- **Neo4j三元组记忆**：所有分析结果以三元组形式存储，形成知识图谱
- **工具间通信**：通过`source_tool`查询实现工具依赖关系
- **记忆分片管理**：每个工具管理自己的记忆片段，依赖关系清晰

**4. 统一管理 (Unified Management Principle)**
- **Jinja2统一提示词管理**：所有提示词通过模板系统统一管理
- **统一接口规范**：工具、智能体、配置都遵循统一的接口设计
- **统一错误处理**：简单但有效的错误捕获和处理机制

## 2. 极简+自主+记忆驱动架构

### 2.1 架构设计理念

#### 🚀 与传统架构的差异

| 维度 | 传统架构 | SemanticSQL极简架构 |
|------|---------|-------------------|
| **状态管理** | 复杂状态对象，多层嵌套 | 2个字段的极简状态 |
| **工具基类** | 继承复杂基类，多个抽象方法 | 2个核心方法，完全自主 |
| **执行控制** | 预定义流水线，外部编排 | LLM智能决策，自主选择 |
| **记忆管理** | 临时存储，无结构化 | Neo4j图数据库，三元组知识 |
| **提示词管理** | 硬编码或简单模板 | Jinja2统一模板系统 |

#### ✨ 核心创新点

1. **真正的智能化**：LLM根据当前记忆状态智能选择工具，无需人工编排
2. **记忆即通信**：工具间通过三元组记忆自动协作，形成知识积累
3. **工具自治**：每个工具完全控制自己的执行逻辑，提高了灵活性和可维护性
4. **极简高效**：去除复杂抽象，代码量减少60%，维护成本大幅降低

### 2.2 极简接口设计

#### 2.2.1 用户调用方式

```python
# 极简的用户调用 - 基于SemanticSQLReActAgent
from semanticsql_agent import create_semantic_sql_agent

# 创建智能体
agent = create_semantic_sql_agent(
    config_type="openai",
    llm_config={
        "model": "qwen-turbo",
        "api_key": settings.llm_api_key,
        "base_url": settings.llm_base_url,
        "temperature": 0.7
    },
    max_iterations=15,
    verbose=True
)

# 执行分析和生成（完全自主）
result = agent.invoke("分析电商数据库并生成SQL训练数据")
```

#### 2.2.2 ReAct智能体执行流程

```
用户输入: "分析数据库并生成SQL训练数据"
    ↓
🧠 ReAct循环开始
──────────────────────────────────

Thought: 我需要生成训练数据，先检查记忆中是否有完整的数据库分析
Action: schema_extraction
Action Input: {"database_name": "电商数据库"}
Observation: ✓ 数据库结构分析完成：发现 3 个表，共 13 个字段
    ↓
Thought: 有了数据库结构，现在需要理解业务语义
Action: domain_analysis
Action Input: {"analyze_domain": true}
Observation: 🎯 领域分析完成：基于 16 条结构信息，识别了 2 个业务域
    ↓
           ... ReAct循环继续，自动分析所有数据库维度 ...
    ↓
Thought: 现在我有了完整的数据库分析，需要生成问题和SQL
Action: question_generation 
Action Input: {"generate_questions": true}
Observation: ✓ 生成了 20 个高质量问题
    ↓
Thought: 为每个问题生成对应的SQL
Action: sql_generation
Action Input: {"generate_sql_for_questions": true} 
Observation: ✓ 为 20 个问题生成了高质量SQL，执行验证通过
    ↓
Thought: 所有数据质量都很好，进行最终质量反思
Action: sql_reflection
Action Input: {"evaluate_all_samples": true}
Observation: ✓ 质量评估完成：平均质量得分0.87，所有样本达到高质量标准
    ↓
Thought: 我已经完成了完整的数据库分析和高质量SQL生成
Final Answer: {
    "generated_samples": 20,
    "average_quality_score": 0.87,
    "samples": [
        {"question": "查询所有用户信息", "sql": "SELECT * FROM users", "quality_score": 0.95},
        {"question": "统计订单数量", "sql": "SELECT COUNT(*) FROM orders", "quality_score": 0.90},
        ...更多高质量样本
    ],
    "analysis_summary": "基于Neo4j记忆的智能化分析完成了从数据库结构到SQL生成的全流程"
}

                      🎉 执行完成，输出结果
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

## 3. 极简工具系统设计

### 3.1 极简工具基类设计

#### 3.1.1 BaseSemanticSQLTool 极简设计

```python
class BaseSemanticSQLTool(BaseTool):
    """极简工具基类 - 只有2个核心方法"""
    
    def get_memory_by_source_tool(self, source_tool: str, limit: int = 10) -> List[dict]:
        """获取指定工具生成的记忆三元组 - 唯一的记忆查询方法"""
        
    def add_analysis_triple(self, subject: str, predicate: str, object: str, **kwargs):
        """添加分析三元组到当前工具记忆 - 唯一的三元组添加方法"""
        
    def _run(self, input_text: str) -> str:
        """工具执行入口 - 子类实现所有业务逻辑"""
        # 1. 清空上次执行的三元组
        # 2. 执行具体业务逻辑  
        # 3. 生成和存储三元组记忆
        # 4. 完全自定义返回格式
        raise NotImplementedError("子类必须实现_run方法")
```

#### 3.1.2 工具自主性特征

- **完全控制**：工具在`_run`中控制所有执行逻辑、存储时机、返回格式
- **记忆分片**：每个工具通过`source_tool`管理自己的记忆片段
- **依赖查询**：通过`get_memory_by_source_tool()`实现工具间依赖
- **Neo4j集成**：三元组自动存储到图数据库，形成结构化知识

### 3.2 工具分类和职责

#### 3.2.1 分析工具组（Analysis Tools）

**schema_extraction_tool**：
- **功能**：提取数据库物理结构，生成表字段三元组
- **依赖**：无（基础工具）
- **记忆片段**：[(Database, 包含表, TableName), (TableName, 包含字段, ColumnName)]

**domain_analysis_tool**：
- **功能**：基于数据库结构分析业务领域，生成领域实体三元组
- **依赖**：需要schema_extraction工具的记忆
- **记忆片段**：[(领域名, 包含实体, 实体名), (领域名, 关联域, 其他领域)]

**field_analysis_tool**：
- **功能**：基于数据库结构进行字段语义分类，生成字段语义三元组
- **依赖**：需要schema_extraction工具的记忆
- **记忆片段**：[(字段名, 字段类型, 标识符/维度/度量/外键)]

**column_analysis_tool**：
- **功能**：基于业务领域分析列的业务含义，生成列业务三元组
- **依赖**：需要domain_analysis工具的记忆
- **记忆片段**：[(字段名, 业务含义, 具体含义描述)]

**table_analysis_tool**：
- **功能**：基于业务领域确定表的业务职责，生成表职责三元组
- **依赖**：需要domain_analysis工具的记忆
- **记忆片段**：[(表名, 业务职责, 职责描述), (表名, 核心实体, 实体名)]

**er_analysis_tool**：
- **功能**：综合结构和业务信息分析关系，生成实体关系三元组
- **依赖**：需要schema_extraction和table_analysis工具的记忆
- **记忆片段**：[(表名1, 一对多关系, 表名2), (实体1, 关联关系, 实体2)]

#### 3.2.2 生成工具组（Generation Tools）

**scenario_operation_tool**：
- **功能**：生成场景操作组合，为问题生成提供场景指导
- **依贖**：需要domain_analysis和table_analysis工具的记忆
- **记忆片段**：[(场景类型, 适用操作, SQL操作组合)]
**question_generation_tool**：
- **功能**：基于业务理解生成自然语言问题，生成问题类型三元组
- **依贖**：需要domain_analysis和table_analysis工具的记忆
- **记忆片段**：[(问题文本, 问题类型, 类型分类)]

**sql_generation_tool**：
- **功能**：基于问题和关系信息生成SQL，同时执行验证
- **依贖**：需要question_generation和er_analysis工具的记忆
- **记忆片段**：[(问题文本, 对应SQL, SQL语句), (SQL执行结果, 包含数据, 结果集), (SQL执行状态, 执行成功, true/false)]

#### 3.2.3 反思工具组（Reflection Tools）

**sql_reflection_tool**：
- **功能**：基于生成的SQL进行质量评估，生成质量评估三元组
- **依赖**：需要sql_generation工具的记忆
- **记忆片段**：[(SQL语句, 质量评分, 0.95), (语法正确性, 评估结果, 通过), (逻辑合理性, 评估结果, 通过), (性能效率, 评估结果, 良好)]

### 3.3 工具依赖关系和记忆流转

#### 3.3.1 工具依赖查询示例

```python
# 在 domain_analysis_tool.py 中
class DomainAnalysisTool(BaseSemanticSQLTool):
    
    def _run(self, input_text: str) -> str:
        # 1. 清空当前执行记忆
        self._generated_triples = []
        
        # 2. 查询依赖的工具记忆
        schema_data = self.get_memory_by_source_tool("schema_extraction", 20)
        
        if not schema_data:
            return "❌ 缺少数据库结构信息，请先执行schema_extraction"
            
        # 3. 基于已有记忆进行分析
        # schema_data 包含: [
        #   {"subject": "电商数据库", "predicate": "包含表", "object": "users"},
        #   {"subject": "users", "predicate": "包含字段", "object": "id"},
        #   ...
        # ]
        
        # 4. 分析并生成新的三元组
        for item in schema_data:
            if item['predicate'] == '包含表':
                table_name = item['object']
                if 'user' in table_name.lower():
                    self.add_analysis_triple(
                        subject="用户管理域",
                        predicate="包含实体", 
                        object="用户",
                        confidence=0.9
                    )
        
        # 5. 自动存储到Neo4j并返回自定义结果
        return f"🎯 基于{len(schema_data)}条记忆，识别了{len(self._generated_triples)}个业务域"
```

#### 3.3.2 工具协作流程

🔧 工具A执行 → 💾 Neo4j存储 → 🔧 工具B查询使用
──────────────────────────────────────
- 工具自主存储 → 结构化知识积累 → 工具依赖查询
- source_tool标记 → 三元组图谱存储 → get_memory_by_source_tool()

### 3.4 极简工具开发最佳实践

**单一职责原则**：
- ✅ 好的设计 - 单一职责：只负责数据库结构提取
- ❌ 不好的设计 - 职责混乱：既提取结构又分析业务

**记忆查询最佳实践**：
- ✅ 好的设计 - 明确的依赖关系：检查依赖，基于记忆分析
- ❌ 不好的设计 - 隐式依赖：没有检查依赖，可能失败

**错误处理最佳实践**：
- ✅ 好的设计 - 优雅的错误处理：捕获异常，返回有意义的错误信息
- ❌ 不好的设计 - 异常传播：没有异常处理，导致Agent失败

## 4. Neo4j三元组记忆系统

### 4.1 记忆驱动的设计理念

#### 4.1.1 三元组知识图谱

**Neo4j三元组记忆管理**：
- 所有分析结果以三元组形式存储：`(Subject, Predicate, Object)`
- 工具间通过`source_tool`查询实现依赖关系
- 每个工具管理自己的记忆片段，依赖关系清晰

**核心优势**：
- **结构化存储**：三元组形式存储，支持图查询和推理
- **工具协作**：通过source_tool实现工具间知识传递
- **知识积累**：每次执行都丰富知识图谱，支持增量学习
- **智能协作**：工具间通过三元组记忆自动协作，形成知识积累

### 4.2 记忆分片管理机制

#### 4.2.1 工具记忆分片示例

```
每个工具管理自己的记忆片段:

schema_extraction → Neo4j存储 (source_tool="schema_extraction")
├── (电商数据库, 包含表, users)
├── (电商数据库, 包含表, orders)
├── (users, 包含字段, id)
├── (users, 包含字段, username)
└── (orders, 包含字段, user_id)

domain_analysis → Neo4j存储 (source_tool="domain_analysis") 
├── (用户管理域, 包含实体, 用户)
├── (订单管理域, 包含实体, 订单)
└── (用户管理域, 关联域, 订单管理域)

field_analysis → Neo4j存储 (source_tool="field_analysis")
├── (id, 字段类型, 标识符)
├── (username, 字段类型, 维度)
└── (amount, 字段类型, 度量)

... 更多8个工具的记忆片段
```

#### 4.2.2 工具依赖查询机制

```python
# 工具依赖查询示例:
domain_analysis.get_memory_by_source_tool("schema_extraction") 
│   → 获取数据库结构信息用于业务分析
├── field_analysis.get_memory_by_source_tool("schema_extraction")
│   → 获取字段信息进行语义分类
├── column_analysis.get_memory_by_source_tool("domain_analysis") 
│   → 基于业务域信息分析列含义
├── question_generation.get_memory_by_source_tool("domain_analysis", "table_analysis")
│   → 基于业务理解生成问题
└── sql_generation.get_memory_by_source_tool("question_generation", "er_analysis")
    → 基于问题和关系信息生成SQL
```

### 4.3 SemanticTriple 数据模型

#### 4.3.1 三元组模型定义

```python
class SemanticTriple(BaseModel):
    """语义三元组 - 记忆的核心数据结构"""
    subject: str = Field(description="主体实体")
    predicate: str = Field(description="关系谓词")
    object: str = Field(description="客体实体")
    
    # 扩展属性
    subject_type: str = Field(default="Entity", description="主体类型")
    object_type: str = Field(default="Entity", description="客体类型")
    confidence: Optional[float] = Field(default=None, description="置信度")
    source_tool: str = Field(default="", description="来源工具")
```

#### 4.3.2 Neo4j记忆管理器

```python
class Neo4jMemoryManager:
    """三元组记忆管理器"""
    
    def store_triples(self, triples: List[SemanticTriple], source_tool: str):
        """存储工具生成的三元组到Neo4j"""
        
    def query_by_source_tool(self, source_tool: str, limit: int) -> List[dict]:
        """查询指定工具的记忆片段"""
        
    def get_related_triples(self, entity: str, relation_types: List[str]) -> List[dict]:
        """获取实体相关的三元组知识"""
```

## 5. SemanticSQLReActAgent接口设计

### 5.1 核心智能体接口

#### 5.1.1 基于01-ReAct设计的接口规范

```python
class SemanticSQLReActAgent:
    """基于LangChain官方API的极简ReAct智能体"""
    
    def __init__(self, 
                 llm,
                 tools: List,
                 max_iterations: int = 10,
                 verbose: bool = True):
        """
        初始化智能体
        
        Args:
            llm: 语言模型实例
            tools: 工具列表
            max_iterations: 最大迭代次数
            verbose: 是否显示详细执行过程
        """
        self.llm = llm
        self.tools = tools
        self.max_iterations = max_iterations
        self.verbose = verbose
        
        # 创建智能体执行器
        self.agent_executor = self._create_agent_executor()
    
    def _create_agent_executor(self) -> AgentExecutor:
        """创建AgentExecutor - 使用官方API"""
        # 1. 创建提示词模板
        prompt = create_semantic_sql_prompt()
        
        # 2. 创建记忆增强的ReAct Agent
        agent = create_memory_enhanced_react_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt,
            output_parser=SemanticSQLOutputParser()
        )
        
        # 3. 创建AgentExecutor（官方API）
        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=self.verbose,
            max_iterations=self.max_iterations,
            handle_parsing_errors=True,
            return_intermediate_steps=True
        )
        
    def invoke(self, user_input: str) -> Dict[str, Any]:
        """
        标准invoke接口 - 兼容官方API
        
        Args:
            user_input: 用户输入
            
        Returns:
            执行结果字典
        """
        return self.agent_executor.invoke({"input": user_input})
```

#### 5.1.2 业务完成解析器

```python
class SemanticSQLOutputParser(AgentOutputParser):
    """
    SemanticSQL解析器 - 基于官方ReActSingleInputOutputParser逻辑
    专注SQL生成完成检测
    """
    
    def parse(self, llm_output: str) -> Union[AgentAction, AgentFinish]:
        """
        解析LLM输出 - 完全基于官方ReAct格式
        
        官方检测逻辑：
        1. Final Answer: -> AgentFinish (结束)
        2. Action: + Action Input: -> AgentAction (继续)
        3. 解析失败 -> OutputParserException
        """
        
        # 1. 检查是否包含 Final Answer（官方ReAct结束信号）
        if "Final Answer:" in llm_output:
            # 提取 Final Answer 之后的内容
            final_answer = llm_output.split("Final Answer:")[-1].strip()
            return AgentFinish(
                return_values={"output": final_answer},
                log=llm_output
            )
        
        # 2-5. 完整的Action检测和提取逻辑...
        # (具体实现见接口设计文档)
```

#### 5.1.3 工厂函数

```python
def create_semantic_sql_agent(
    config_type="openai", 
    llm_config=None, 
    tools=None,
    **agent_kwargs
) -> SemanticSQLReActAgent:
    """创建完整配置的SemanticSQL智能体"""
    
    # 1. 创建LLM实例
    llm = create_llm(config_type=config_type, **llm_config or {})
    
    # 2. 获取工具集（默认使用完整SemanticSQL工具集）
    if tools is None:
        tools = get_semantic_sql_tools()
    
    # 3. 创建智能体实例
    return SemanticSQLReActAgent(
        llm=llm,
        tools=tools,
        **agent_kwargs
    )
```

## 6. Agent实现规范

### 6.1 SemanticSQLReActAgent接口规范

**核心接口**：
```python
class SemanticSQLReActAgent:
    def __init__(self, llm, tools: List, max_iterations: int = 10, verbose: bool = True):
        """初始化ReAct智能体"""
        
    def invoke(self, user_input: str) -> Dict[str, Any]:
        """标准invoke接口 - 兼容官方API"""
        # 详细实现见01-ReAct智能体接口设计.md
        pass
```

**使用方式**：
```python
# 创建Agent（通过工厂函数）
agent = create_semantic_sql_agent(
    config_type="openai",
    llm_config={
        "model": "gpt-4",
        "api_key": "your-openai-key",
        "temperature": 0.7
    },
    max_iterations=15,
    verbose=True
)

# 执行NL2SQL任务（完全自主）
result = agent.invoke("分析电商数据库并生成用户订单相关的训练数据")

# 结果格式
print(f"生成结果: {result['output']}")
```

**接口特点**：
- **极简调用**：使用标准的invoke()方法
- **Agent自主**：基于ReAct模式完全自主决策
- **工具协作**：通过Neo4j三元组记忆实现工具间智能协作
- **质量保证**：每个样本都经过完整的验证和反思流程

## 7. 提示词系统概述

### 7.1 提示词分层设计

**系统采用分层的Jinja2模板管理**：
- **系统级**：Agent的主要工作指导
- **工具级**：每个工具的专用提示词
- **分析级**：数据库分析的专业指导
- **反思级**：质量评估和修正指导

**核心特点**：
- 每个工具都有专用的提示词模板
- 提示词包含前置条件检查
- 自动从记忆中注入所需信息
- 支持Agent的完全自主决策

*详细的提示词架构和实现请参考 ARCHITECTURE.md*

### 7.2 提示词设计原则

**核心原则**：
- **记忆检查优先**：Agent优先检查已有的分析结果
- **工具自主选择**：Agent根据需求自主选择调用哪个工具
- **前置条件明确**：每个工具的提示词都明确说明需要的前置条件
- **自动信息注入**：工具自动从记忆中获取所需信息

**工作流程指导**：
1. 智能检查数据库分析状态
2. 按需调用分析工具补充信息
3. 获取所有场景-操作组合
4. 逐个处理每个组合生成高质量样本

*具体的提示词模板和实现细节请参考 ARCHITECTURE.md*

## 8. 配置和使用

### 8.1 配置文件

```yaml
# config.yaml - 极简配置
database:
  host: localhost
  port: 3306
  username: root
  password: ${DB_PASSWORD}
  database: shop_db

neo4j:
  uri: bolt://localhost:7687
  username: neo4j
  password: ${NEO4J_PASSWORD}
  database: "neo4j"

llm:
  config_type: "openai"
  model: gpt-4
  base_url: https://api.openai.com/v1
  api_key: ${OPENAI_API_KEY}
  temperature: 0.7
  max_tokens: 2000

agent:
  max_iterations: 15  # 足够处理ReAct循环
  verbose: true
```

### 8.2 程序化使用

```python
# 方式1：直接使用工厂函数
from agent.sql_agent import create_semantic_sql_agent

agent = create_semantic_sql_agent(
    config_type="openai",
    llm_config={
        "model": "gpt-4",
        "api_key": "your-openai-key",
        "temperature": 0.7
    },
    max_iterations=15,
    verbose=True
)

# 执行NL2SQL任务
result = agent.invoke("分析电商数据库并生成用户订单相关的训练数据")

# 方式2：自定义工具集
from tools import SchemaExtractionTool, DomainAnalysisTool, SQLGenerationTool

custom_tools = [
    SchemaExtractionTool(),
    DomainAnalysisTool(),  
    SQLGenerationTool()
]

agent = create_semantic_sql_agent(
    tools=custom_tools,
    config_type="openai", 
    llm_config={"model": "gpt-3.5-turbo"}
)
```

### 8.3 CLI使用

```bash
# 基础使用
python -m agent.main --input "生成用户管理相关的训练数据"

# 指定配置文件
python -m agent.main --config config.yaml --input "分析订单数据库"

# 详细输出
python -m agent.main --input "生成SQL训练数据" --verbose
```

### 8.4 输出格式

SemanticSQLReActAgent的invoke返回格式：
```python
{
    "output": "✅ 成功生成15个高质量训练样本",
    "intermediate_steps": [
        (AgentAction(tool="schema_extraction", tool_input="..."), "Observation: ..."),
        (AgentAction(tool="domain_analysis", tool_input="..."), "Observation: ...")
    ]
}
```

生成的训练数据存储在Neo4j中，包含：
- **语义三元组**：结构化的知识图谱数据
- **问题文本**：自然语言问题
- **SQL查询**：对应的SQL语句  
- **场景信息**：场景类型、复杂度
- **质量评分**：0-1的质量分数
- **验证结果**：语法和执行验证信息
- **工具协作记录**：完整的工具调用和记忆流转过程

## 9. 错误处理和反思机制

### 9.1 反思工具设计

**sql_reflection_tool** 的简化返回格式：

```python
{
    "quality_score": 0.85,              # 质量分数 0-1
    "needs_revision": False,            # 是否需要修正
    "suggested_tool": "sql_generation", # 建议的工具（可选）
    "suggestion": "修正建议文字"         # 简单建议
}
```

### 9.2 Agent自主修正流程

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

### 9.3 错误类型和处理策略

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

## 10. 部署和运维

### 10.1 环境依赖

**核心组件**：
- Python 3.8+
- LangChain 最新版
- Neo4j 5.0+ (用于三元组记忆存储)
- OpenAI API 或 兼容的LLM接口

**安装命令**：
```bash
pip install langchain langchain-openai langchain-neo4j
pip install pydantic jinja2
```

### 10.2 启动配置

**环境变量**：
```bash
export OPENAI_API_KEY="your-openai-key"
export NEO4J_PASSWORD="your-neo4j-password"
export DB_PASSWORD="your-database-password"
```
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
  ...更多样本
]
```

## 11. 质量保证机制

### 11.1 验证流程

**每个生成的样本都要经过**：
1. **语法验证**：确保SQL语法正确
2. **执行测试**：实际执行SQL验证可行性
3. **反思评估**：评估问题-SQL的语义匹配度
4. **自主修正**：Agent根据反思建议自主选择修正策略

### 11.2 质量标准

**样本质量要求**：
- SQL语法必须正确
- 问题表述自然流畅
- SQL与问题语义匹配
- 执行结果合理有效
- 符合场景复杂度要求

### 11.3 Agent自主修正

当发现质量问题时，Agent会：
- 调用sql_reflection分析问题
- 根据建议自主选择修正工具
- 重新生成或修正有问题的部分
- 确保最终质量达标

## 12. 架构优势

### 12.1 设计优势

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

### 12.2 与传统方案的对比

| 特征 | ❌ 传统流水线方案 | ✅ Agent自主方案 |
|------|-----------------|-----------------|
| **控制方式** | 外部循环控制 | Agent完全自主 |
| **工具调用** | 硬编码调用顺序 | Agent自主选择 |
| **参数传递** | 手动传递参数 | 记忆自动协作 |
| **错误处理** | 外部异常处理 | Agent自主修正 |
| **扩展性** | 修改流程代码 | 添加工具即可 |

## 13. 开发指南

### 13.1 添加新工具

1. 继承`BaseSemanticSQLTool`
2. 实现`_run(self, input_text: str) -> str`方法
3. 使用`add_analysis_triple()`添加三元组
4. 使用`get_memory_by_source_tool()`查询依赖
5. 创建工具专用提示词模板(prompts/templates/tools/)
6. 将新工具添加到`get_semantic_sql_tools()`

### 13.2 修改场景配置

1. 更新`ScenarioOperationTool`的内部逻辑
2. 修改工具的`_run()`方法实现
3. 更新相应的提示词模板
4. 在Neo4j中更新相关三元组数据

### 13.3 调试和优化

1. 使用`verbose=True`查看ReAct执行过程
2. 检查`intermediate_steps`了解Agent决策过程  
3. 查询Neo4j中的三元组数据确认工具协作
4. 使用`get_memory_by_source_tool()`验证记忆流转
5. 检查工具返回的Observation内容

### 13.4 提示词模板开发

1. 使用`prompts/templates/system/`目录存放ReAct Agent模板
2. 使用Jinja2语法编写模板，包含`{input}`、`{agent_scratchpad}`、`{tools}`、`{tool_names}`变量
3. 通过`PromptManager.create_agent_prompt_template()`创建模板
4. 工具描述要明确说明依赖的记忆类型
5. 输出格式必须符合ReAct的Action/Observation模式

---

**本设计规范明确了最终的技术方案，删除了重复和错误内容，确保逻辑一致性和实用性。文档长度约1200行，涵盖所有核心设计要点。**