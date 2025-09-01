# SemanticSQL Agent 架构文档

## 1. 系统架构概览

### 1.1 架构原则
- **模块化设计**：清晰的模块划分，职责单一
- **工具驱动**：通过专业工具完成各项任务
- **反思机制**：执行后反思，持续优化生成质量
- **配置灵活**：支持多环境、多数据库配置

### 1.2 技术栈
- **编程语言**: Python 3.8+
- **核心框架**:
  - LangChain: Agent 框架、记忆管理、工具集成、LLM 调用
  - SQLAlchemy: 数据库操作
  - Pydantic: 数据模型验证
  - Jinja2: 提示词模板
  - Click: CLI 框架
- **LLM支持**: Qwen (通过 LangChain 的 OpenAI 兼容接口)

## 2. 项目结构设计

```
semanticsql-agent/
├── config/
│   ├── __init__.py
│   ├── settings.py              # 全局配置
│   └── database.py              # 数据库配置
│
├── models/
│   ├── __init__.py
│   ├── schemas.py               # Pydantic 模型定义
│   └── exceptions.py            # 异常定义
│
├── tools/
│   ├── __init__.py
│   ├── base_tool.py                  # 工具基类
│   │
│   ├── analysis_tools/          # 分析工具（可重新执行更新记忆）
│   │   ├── __init__.py
│   │   ├── schema_extraction_tool.py    # 数据库结构提取
│   │   ├── domain_analysis_tool.py      # 业务领域分析
│   │   ├── field_classification_tool.py # 字段语义分类
│   │   ├── column_meaning_tool.py       # 列业务含义分析
│   │   ├── table_meaning_tool.py        # 表业务含义分析
│   │   └── er_analysis_tool.py          # 实体关系分析
│   │
│   ├── generation_tools/        # 生成工具
│   │   ├── __init__.py
│   │   ├── scenario_tool.py             # 场景生成（基于预定义模板）
│   │   ├── operation_selection_tool.py  # 操作选择（基于预定义规则）
│   │   ├── question_generation_tool.py  # 问题生成（使用场景+操作+记忆）
│   │   └── sql_generation_tool.py       # SQL生成（使用问题+记忆）
│   │
│   ├── validation_tools/        # 验证工具
│   │   ├── __init__.py
│   │   ├── sql_validation_tool.py       # SQL验证
│   │   └── sql_execution_tool.py        # SQL执行测试
│   │
│   ├── reflection_tools/        # 反思工具
│   │   ├── __init__.py
│   │   └── sql_reflection_tool.py       # SQL执行反思（评估质量和问题诊断）
│   │
│   └── thinking_tools/          # 思考工具
│       ├── __init__.py
│       └── sequential_thinking_tool.py   # 深度思考（分析问题源头和修正策略）
│
├── prompts/
│   ├── __init__.py
│   ├── templates/              # Jinja2 模板
│   │   ├── system/             # 系统提示词
│   │   ├── tools/              # 工具描述
│   │   └── analysis/           # 分析提示词
│   └── manager.py              # 提示词管理器
│
├── agent/
│   ├── __init__.py
│   ├── base_agent.py           # 基础Agent（含执行流程控制和ReAct循环）
│   └── sql_agent.py            # SQL智能体（批量训练数据生成）
│
├── utils/
│   ├── __init__.py
│   ├── database.py              # 数据库连接管理
│   ├── llm_client.py            # LLM客户端（支持使用标准OpenAI库调用Qwen）
│   ├── memory.py                # 记忆管理（存储和更新数据库分析结果）
│   ├── trajectory.py            # 执行轨迹记录（保存执行历史）
│   └── callbacks.py             # 执行回调（轨迹记录、进度通知等）
│
└── cli.py                       # 命令行接口
```

## 3. 核心组件详解

### 3.1 配置管理 (config/)

#### settings.py
- 使用 Pydantic BaseSettings，支持环境变量覆盖
- 管理 LLM 配置、Agent 参数、工具开关等
- 支持多环境配置（开发、测试、生产）

#### database.py
- 数据库连接配置，专注于 MySQL
- 连接池管理
- 数据库连接参数管理

### 3.2 数据模型 (models/)

#### schemas.py
- 使用 Pydantic 定义所有数据模型
- 包括 QueryScenario、SQLQueryResult、TrainingExample 等
- 提供数据验证和序列化功能

#### exceptions.py
- 定义所有自定义异常类
- 继承自 SemanticSQLException 基类
- 包括配置错误、数据库错误、LLM错误、工具错误等
- 统一的错误代码和消息格式

### 3.3 工具系统 (tools/)

#### 3.3.1 基础设计（基于 LangChain）
- **BaseTool**: 继承自 `langchain.tools.BaseTool`
  - 统一的 `_run()` 接口实现
  - 利用 LangChain 的参数验证机制
  - 自动的错误处理和日志
  - 与 LangChain Agent 无缝集成
  - 支持同步和异步执行

#### 3.3.2 工具分类

**分析工具** (analysis_tools/)
- **schema_extraction_tool**: 提取表结构、列信息、约束
- **domain_analysis_tool**: 识别业务领域特征（电商、金融、医疗等）
- **field_classification_tool**: 字段语义分类（ID、时间、金额、状态等）
- **column_meaning_tool**: 分析列的业务含义和用途
- **table_meaning_tool**: 分析表的业务含义和职责
- **er_analysis_tool**: 分析表关系（主外键、隐式关联）
- 特点：可重新执行，结果更新到记忆模块

**生成工具** (generation_tools/)
- **scenario_tool**: 基于预定义模板生成查询场景
- **operation_selection_tool**: 根据场景复杂度选择SQL操作
- **question_generation_tool**: 生成自然语言问题
- **sql_generation_tool**: 将问题转换为SQL
- 特点：使用记忆模块中的数据库分析结果

**验证工具** (validation_tools/)
- **sql_validation_tool**: 语法验证
- **sql_execution_tool**: 安全执行SQL并返回结果

**反思工具** (reflection_tools/)
- **sql_reflection_tool**: 评估执行结果质量，定位问题源头，推荐修正工具

**思考工具** (thinking_tools/)
- **sequential_thinking_tool**: 深度分析问题，制定修正策略

### 3.4 智能体系统 (agent/)

#### base_agent.py（基于 LangChain AgentExecutor）
- 使用 `langchain.agents.AgentExecutor` 实现 ReAct 模式
- 利用 `langchain.agents.create_react_agent` 创建智能体
- 集成 LangChain 的工具管理机制
- 使用 `langchain.callbacks` 进行执行跟踪
- 支持自定义的 OutputParser 处理响应

#### sql_agent.py
- 继承 BaseAgent，配置专门的 SQL 生成系统提示词
- 系统提示词引导 Agent 自主决策执行流程
- Agent 根据工具输出和反思结果决定下一步行动
- 集成 LangChain 的错误处理机制

### 3.5 记忆管理（基于 LangChain Memory）

#### 使用 LangChain 的记忆组件
- **ConversationSummaryMemory**: 存储数据库分析摘要
- **VectorStoreMemory**: 存储和检索相关的表结构信息
- **自定义 AnalysisMemory**: 继承 `BaseMemory`，专门管理分析结果

```python
from langchain.memory import BaseMemory

class DatabaseAnalysisMemory(BaseMemory):
    """专门用于存储数据库分析结果的记忆"""
    memory_variables = ["schema_info", "domain_analysis", 
                       "field_classification", "column_meanings",
                       "table_meanings", "er_analysis"]
    
    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """加载相关的分析结果"""
        # 返回与当前任务相关的记忆内容
    
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> None:
        """保存或更新分析结果"""
        # 更新记忆中的分析内容
```

- 与 LangChain Agent 自动集成
- 支持持久化到文件或数据库
- 可以使用 LangChain 的记忆链功能

### 3.6 提示词管理（集成 LangChain）

#### 使用 LangChain 的提示词组件
- **PromptTemplate**: 基础提示词模板
- **ChatPromptTemplate**: 对话式提示词
- **FewShotPromptTemplate**: 少样本学习提示词
- **SystemMessagePromptTemplate**: 系统消息模板

```python
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate

# 系统提示词
system_prompt = SystemMessagePromptTemplate.from_template(
    "你是一个SQL生成专家，负责分析数据库并生成高质量的训练数据..."
)

# 工具使用提示词
tool_prompt = ChatPromptTemplate.from_template(
    "使用 {tool_name} 工具来 {task_description}"
)
```

#### 提示词管理器
- 继承 LangChain 的 `BasePromptTemplate`
- 支持动态变量注入
- 与 LangChain Chain 无缝集成

### 3.6 工具类 (utils/)

#### database.py
- DatabaseManager: MySQL 数据库访问接口
- 连接池管理
- 安全的SQL执行

#### llm_client.py（基于 LangChain LLM）
- 使用 `langchain.chat_models.ChatOpenAI` 
- 配置 Qwen 的 API endpoint
- 利用 LangChain 的重试和错误处理机制
- 支持流式输出和回调

```python
from langchain.chat_models import ChatOpenAI

llm = ChatOpenAI(
    model_name="Qwen",
    openai_api_base="http://localhost:9991/v1",
    temperature=0.7
)
```

#### trajectory.py（集成 LangChain Callbacks）
- 实现 `langchain.callbacks.BaseCallbackHandler`
- 自动记录 Agent 的思考和行动
- 支持导出为 LangSmith 格式
- 与 LangChain 的调试工具集成

#### callbacks.py（基于 LangChain Callbacks）
- 继承 `AsyncCallbackHandler` 支持异步操作
- 实现 `on_tool_start`, `on_tool_end` 等钩子
- 与 LangChain 的事件系统集成
- 支持自定义的进度通知
```

## 4. 执行流程

### 4.1 初始化流程（LangChain 集成）
```
1. 加载配置 (Settings)
2. 初始化数据库连接 (DatabaseManager)
3. 创建 LangChain LLM 实例 (ChatOpenAI)
4. 初始化 LangChain Memory (DatabaseAnalysisMemory)
5. 创建 LangChain Tools 列表
6. 使用 create_react_agent 创建 Agent
7. 配置 AgentExecutor 与 Callbacks
```

```python
# 示例代码
from langchain.agents import create_react_agent, AgentExecutor
from langchain.chat_models import ChatOpenAI

# 初始化 LLM
llm = ChatOpenAI(openai_api_base=config.llm_base_url)

# 初始化记忆
memory = DatabaseAnalysisMemory()

# 创建工具列表
tools = [SchemaExtractionTool(), DomainAnalysisTool(), ...]

# 创建 Agent
agent = create_react_agent(llm, tools, prompt)
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    memory=memory,
    callbacks=[TrajectoryCallback()]
)
```

### 4.2 数据库分析阶段（只执行一次）
```
开始任务
    ↓
sequential_thinking（规划执行策略）
    ↓
按顺序执行分析工具：
1. extract_schema → 记忆模块（提取基础结构）
2. domain_analysis → 记忆模块（识别业务领域）
3. field_classification → 记忆模块（字段语义分类）
4. column_meaning → 记忆模块（分析列业务含义）
5. table_meaning → 记忆模块（分析表业务职责）
6. er_analysis → 记忆模块（分析表间关系）
```

### 4.3 问题生成流程
```
根据设定的问题生成数量N，循环遍历预定义场景模板：
    ↓
for i in range(N):  # 生成N个问题
    ├─ scenario_tool（从预定义模板中选择一个场景）【不可修正】
    ├─ operation_selection（基于场景选择SQL操作）【不可修正】
    ├─ question_generation（生成自然语言问题）【可修正】
    ├─ sql_generation（生成SQL语句）【可修正】
    ├─ sql_validation（验证语法）
    ├─ sql_execution（执行测试）
    └─ sql_reflection（基于执行结果反思，定位问题）
         ↓
    需要修正？
    ├─ 否 → 保存生成的问题和SQL，继续下一个
    └─ 是 → Agent根据recommended_action决定：
            ├─ 直接调用建议的工具（如sql_generation）
            └─ 调用sequential_thinking深度分析
                    ↓
       基于分析结果执行修正：
       ├─ 数据库分析有误 → 重新执行相应分析工具 → 更新记忆
       │   ├─ 领域理解错误 → 重新执行 domain_analysis
       │   ├─ 字段分类错误 → 重新执行 field_classification
       │   ├─ 列含义错误 → 重新执行 column_meaning
       │   ├─ 表含义错误 → 重新执行 table_meaning
       │   └─ 关系理解错误 → 重新执行 er_analysis
       ├─ 问题生成有误 → 重新执行 question_generation
       └─ SQL生成有误 → 重新执行 sql_generation
```

### 4.4 Agent 自主决策机制

**核心原则**：
- Agent 通过系统提示词引导，自主决定执行流程
- 不是硬编码的步骤，而是基于工具输出的智能决策
- 反思工具提供建议，Agent 决定是否采纳

**决策示例**：
1. **反思后的决策**：
   - sql_reflection 返回 `recommended_action.tool_to_call = "sql_generation"`
   - Agent 可以：
     - 直接调用 sql_generation 重新生成SQL
     - 先调用 sequential_thinking 深入分析
     - 如果是数据库分析问题，重新执行相应分析工具

2. **不可修改的内容**：
   - 场景选择（scenario_tool的结果固定）
   - 操作选择（operation_selection的结果固定）
   - 这两个是预定义的，确保生成的多样性和覆盖性

3. **可修正的内容**：
   - 数据库分析结果（如果理解有误）
   - 问题生成（如果不够清晰）
   - SQL生成（如果有错误）

### 4.5 ReAct 执行模式
```
用户输入/工具结果
    ↓
Thought（分析当前状态，决定下一步）
    ↓
Action（选择工具）
    ↓
Action Input（准备参数，可能使用记忆）
    ↓
执行工具
    ↓
Observation（观察结果）
    ↓
[判断是否完成]
├─ 否 → 继续 Thought
└─ 是 → Final Result
```

### 4.5 反思-修正机制
```
SQL执行结果
    ↓
sql_reflection 评估：
├─ 执行成功性
├─ 结果合理性
├─ 语义匹配度
├─ 问题清晰度
└─ 记忆使用情况
    ↓
发现问题？
├─ 否 → 继续
└─ 是 → sequential_thinking 分析
        ├─ 确定问题步骤
        ├─ 制定修正策略
        └─ 执行修正（只修正出问题的步骤）
```



## 5. LangChain 集成优势

### 5.1 使用 LangChain 的好处
- **统一的 Agent 框架**：利用成熟的 ReAct 实现，减少自定义代码
- **强大的记忆管理**：多种记忆类型，支持向量存储和持久化
- **丰富的工具生态**：可以轻松集成 LangChain 社区的工具
- **完善的回调系统**：内置的执行跟踪和调试功能
- **错误处理机制**：自动重试、超时控制、错误恢复
- **提示词工程**：结构化的提示词模板和管理
- **LLM 抽象**：轻松切换不同的 LLM 提供商

### 5.2 LangChain 组件映射
| 我们的组件 | LangChain 组件 | 说明 |
|---------|--------------|------|
| BaseTool | langchain.tools.BaseTool | 工具基类 |
| BaseAgent | langchain.agents.AgentExecutor | Agent 执行器 |
| Memory | langchain.memory.BaseMemory | 记忆基类 |
| LLMClient | langchain.chat_models.ChatOpenAI | LLM 客户端 |
| Callbacks | langchain.callbacks.BaseCallbackHandler | 回调处理器 |
| PromptManager | langchain.prompts.BasePromptTemplate | 提示词模板 |

### 5.3 自定义扩展
虽然使用 LangChain，但我们仍需要自定义：
- **DatabaseAnalysisMemory**: 专门管理数据库分析结果
- **SQL 专用工具**: 针对 SQL 生成的特定工具
- **批量生成 Chain**: 处理大规模数据生成的流程
- **质量评估组件**: SQL 质量评分和优化建议

## 6. 核心特性

### 6.1 记忆模块
- 存储数据库分析结果供后续使用
- 支持动态更新（根据反思结果）
- 跨工具共享上下文

### 6.2 反思-修正循环
- 自动评估生成质量
- 精确定位问题源头
- 只重新执行出错步骤
- 支持分析工具重新执行

### 6.3 执行轨迹
- 记录完整的执行历史
- 支持调试和分析
- JSON格式持久化

### 6.4 工具设计原则
- 单一职责：每个工具只做一件事
- 标准接口：统一的输入输出格式
- 错误处理：优雅的错误处理机制
- 可组合性：工具间可以灵活组合



## 7. 部署和运行

### 7.1 环境准备
```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 设置数据库和LLM连接信息
```

### 7.2 命令行使用
```bash
# 生成训练数据
python cli.py generate --count 100 --output data.json

# 查看执行轨迹
python cli.py trajectory --latest
```

### 7.3 API使用（基于 LangChain）
```python
from semanticsql_agent import SQLAgent
from langchain.callbacks import StdOutCallbackHandler
from config import Settings, DatabaseConfig

# 初始化
settings = Settings()
db_config = DatabaseConfig.from_env()

# 创建 Agent（内部使用 LangChain）
agent = SQLAgent(
    settings=settings,
    callbacks=[StdOutCallbackHandler()]  # LangChain 回调
)

# 生成训练数据（使用 AgentExecutor）
result = agent.generate_training_data(
    count=100,
    output_file="training_data.json"
)

# 获取执行轨迹（通过 LangChain Callbacks）
trajectory = agent.get_trajectory()
```

## 8. 最佳实践

### 8.1 Agent设计原则
- **提示词驱动**：通过提示词引导行为，避免硬编码流程
- **自主决策**：让Agent根据上下文自主选择工具
- **记忆机制**：利用记忆模块在工具间共享上下文
- **反思循环**：执行后评估质量，必要时自动修正

### 8.2 工具开发指南
- **单一职责**：每个工具专注一个任务
- **标准接口**：统一的输入输出格式
- **错误处理**：提供清晰的错误信息
- **可测试性**：便于单元测试和集成测试

### 8.3 部署建议
- **环境配置**：使用环境变量管理敏感信息
- **日志记录**：详细的执行日志便于调试
- **错误处理**：完善的异常处理机制
- **监控指标**：生成成功率、执行时间等



