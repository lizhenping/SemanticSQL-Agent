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
- **domain_analysis_tool**: 识别业务领域特征
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
- **sql_reflection_tool**: 评估执行结果质量，分析问题特征，提供质量评分

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

## 4. 执行流程（基于真正的ReAct模式）

### 4.1 初始化流程（简化的LangChain集成）
```
1. 加载配置 (Settings)
2. 初始化数据库连接 (DatabaseManager)  
3. 创建 LangChain LLM 实例 (ChatOpenAI)
4. 初始化 LangChain Memory (DatabaseAnalysisMemory)
5. 创建完整的 LangChain Tools 列表（所有工具，不分类）
6. 使用 create_react_agent 创建统一的 Agent
7. 配置 AgentExecutor
```

```python
# 简化的初始化代码
from langchain.agents import create_react_agent, AgentExecutor
from langchain.chat_models import ChatOpenAI

class SQLAgent:
    def __init__(self, settings, db_config):
        # 初始化 LLM
        self.llm = ChatOpenAI(openai_api_base=config.llm_base_url)
        
        # 初始化记忆
        self.memory = DatabaseAnalysisMemory()
        
        # 创建所有工具（不分类，不过滤）
        self.tools = self._initialize_all_tools()
        
        # 创建统一的 Agent（拥有所有工具的访问权限）
        agent = create_react_agent(self.llm, self.tools, self._get_prompt())
        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            memory=self.memory,
            verbose=True,
            callbacks=[TrajectoryCallback()]
        )
```

### 4.2 统一的执行流程（外部大循环 + 内部纯ReAct）

```python
def generate_training_data(self, count: int) -> List[Dict]:
    """外部大循环控制数量，内部完全由Agent自主决策"""
    results = []
    
    # 🔄 外部大循环：简单的数量控制
    for i in range(count):
        print(f"🎯 生成第 {i+1}/{count} 个样本...")
        
        # 每次迭代都是独立的ReAct任务
        sample = self._generate_single_sample(i)
        
        if sample:
            results.append(sample)
        
    return results

def _generate_single_sample(self, iteration: int) -> Optional[Dict]:
    """生成单个样本 - 完全由Agent自主决策执行流程"""
    
    task = f"生成第{iteration + 1}个高质量NL2SQL训练样本"
    
    # 完全交给Agent自主决策，不预设任何执行步骤
    result = self.agent_executor.invoke({
        "input": task,
        "iteration": iteration,
        "database_name": self.db_config.database
    })
    
    return self._extract_sample_from_result(result)
```

### 4.3 Agent内部的完全自主决策

**核心原则**：
- Agent通过提示词引导，完全自主决定执行流程
- 没有外部的阶段控制或工具过滤
- 基于当前状态和任务需求动态选择工具

**典型的Agent推理流程**：
```
用户: "生成第1个高质量NL2SQL训练样本"

Thought: 我需要生成训练样本。首先检查是否了解数据库结构。
Action: 检查记忆或调用schema_extraction
Observation: [获得数据库结构信息]

Thought: 现在选择一个业务场景。
Action: scenario_tool
Observation: [选择了"销售分析"场景]

Thought: 根据场景选择SQL操作类型。
Action: operation_selection  
Observation: [选择了聚合查询操作]

Thought: 生成自然语言问题。
Action: question_generation
Observation: [生成了问题]

Thought: 生成对应的SQL查询。
Action: sql_generation
Observation: [生成了SQL]

Thought: 验证并执行SQL。
Action: sql_validation -> sql_execution
Observation: [执行结果]

Thought: 评估生成质量。
Action: sql_reflection
Observation: [质量评估结果]

Thought: 质量良好，任务完成。
Final Answer: {"question": "...", "sql": "...", "quality_score": 0.85}
```

### 4.4 ReAct执行模式的关键特征

1. **完全自主**：Agent拥有所有工具的访问权限
2. **按需分析**：只有当缺少信息时才调用分析工具
3. **记忆驱动**：充分利用已有的分析结果
4. **错误自愈**：执行失败时自主选择修正策略

### 4.5 记忆管理的简化

```python
class DatabaseAnalysisMemory(BaseMemory):
    """简化的记忆管理 - 自动保存和加载分析结果"""
    
    def __init__(self):
        self.analysis_data = {}  # 存储所有分析结果
    
    def load_memory_variables(self, inputs: Dict) -> Dict:
        """自动加载相关分析结果"""
        return {
            "memory_summary": self._get_summary(),
            **self.analysis_data  # 直接提供所有分析数据
        }
    
    def save_context(self, inputs: Dict, outputs: Dict) -> None:
        """自动保存工具执行结果"""
        # 自动识别和保存分析工具的输出
        self._auto_save_analysis_results(outputs)
```

### 4.6 Agent自主的反思-修正机制

**完全由Agent根据提示词指导自主执行**：

```
Agent内部推理：

Thought: SQL执行完成，我需要评估质量。
Action: sql_reflection
Observation: 发现问题 - SQL语法错误

Thought: 有语法错误，我需要重新生成SQL。
Action: sql_generation  
Observation: 生成了新的SQL

Thought: 重新验证和执行。
Action: sql_validation -> sql_execution
Observation: 执行成功

Thought: 再次评估质量。
Action: sql_reflection
Observation: 质量良好，无需进一步修正

Thought: 样本生成完成。
Final Answer: 完整的训练样本
```

**关键特点**：
- 没有外部控制的修正逻辑
- Agent根据工具输出自主决定下一步
- 提示词提供指导，但不强制执行顺序
- 记忆系统自动管理分析结果的更新



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
- **质量评估组件**: SQL 质量评分和优化建议

**注意**：不再需要复杂的"批量生成Chain"，而是使用简单的外部循环 + 内部ReAct模式。

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



