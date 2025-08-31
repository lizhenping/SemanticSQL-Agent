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
  - LangChain: Agent 框架
  - SQLAlchemy: 数据库操作
  - Pydantic: 数据模型验证
  - Jinja2: 提示词模板
  - Click: CLI 框架
- **LLM支持**: Qwen (OpenAI 兼容 API)

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
│   └── schemas.py               # Pydantic 模型定义
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
│   └── sql_agent.py            # SQL智能体（支持单次查询和批量生成两种模式）
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
- 数据库连接配置，支持 MySQL、PostgreSQL、SQLite
- 连接池管理
- 统一的数据库类型枚举

### 3.2 工具系统 (tools/)

#### 3.2.1 基础设计
- **BaseTool**: 所有工具的基类
  - 统一的 `run()` 接口
  - 自动参数验证
  - 执行计时和错误处理
  - 标准返回格式：`{"success": bool, "data": Any, "error": str}`

#### 3.2.2 工具分类

**分析工具** (analysis_tools/)
- **schema_extraction_tool**: 提取表结构、列信息、约束
- **domain_analysis_tool**: 识别业务领域特征
- **field_classification_tool**: 字段语义分类（ID、时间、金额等）
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
- **sql_reflection_tool**: 评估执行结果质量，诊断问题

**思考工具** (thinking_tools/)
- **sequential_thinking_tool**: 深度分析问题，制定修正策略

### 3.3 智能体系统 (agent/)

#### base_agent.py
- 实现 ReAct 模式的核心循环
- 工具注册和调用机制
- 执行步骤记录
- 与记忆模块和轨迹系统的集成

#### sql_agent.py
- 继承 BaseAgent
- 支持两种模式：
  - **查询模式**: 用户问题 → SQL生成 → 执行结果
  - **批量生成模式**: 场景批量生成 → 循环处理 → 训练数据
- 管理工具调用顺序
- 实现反思-修正循环

### 3.4 记忆管理 (utils/memory.py)

存储和管理数据库分析结果：
```python
memory = {
    "schema_info": {},        # 数据库结构
    "domain_analysis": {},    # 领域分析
    "field_classification": {}, # 字段分类
    "er_analysis": {}         # 关系分析
}
```
- 初始执行时填充
- 可根据反思结果更新
- 为所有生成工具提供数据支持

### 3.5 提示词管理 (prompts/)

#### 模板组织
- `templates/system/`: Agent 系统提示词
- `templates/tools/`: 各工具的使用说明
- `templates/analysis/`: 数据分析提示词

#### manager.py
- Jinja2 模板渲染
- 变量注入
- 提示词版本管理

### 3.6 工具类 (utils/)

#### database.py
- DatabaseManager: 统一的数据库访问接口
- 支持多种数据库
- 连接池管理
- 安全的SQL执行

#### llm_client.py
- 封装 OpenAI API 调用
- 支持 Qwen 等兼容模型
- 重试机制
- 流式输出支持

#### trajectory.py
- 记录完整的执行历史
- JSON 格式持久化
- 用于调试和分析
- 自动清理旧记录

#### callbacks.py
- 执行过程回调
- 与轨迹系统集成
- 支持进度通知
```

## 4. 执行流程

### 4.1 初始化流程
```
1. 加载配置 (Settings)
2. 初始化数据库连接 (DatabaseManager)
3. 初始化 LLM 客户端
4. 创建 Agent 实例
5. 注册所有工具
6. 初始化记忆模块
7. 设置轨迹记录
```

### 4.2 数据库分析阶段（只执行一次）
```
开始任务
    ↓
sequential_thinking（规划执行策略）
    ↓
执行四个分析工具：
├─ extract_schema → 记忆模块
├─ domain_analysis → 记忆模块
├─ field_classification → 记忆模块
└─ er_analysis → 记忆模块
```

### 4.3 批量生成流程
```
scenario_tool（批量生成N个场景）
    ↓
对每个场景循环：
    ├─ operation_selection（选择SQL操作）
    ├─ question_generation（生成问题）
    ├─ sql_generation（生成SQL）
    ├─ sql_validation（验证语法）
    ├─ sql_execution（执行测试）
    └─ sql_reflection（反思评估）
         ↓
    需要修正？
    ├─ 否 → 保存数据，下一个场景
    └─ 是 → sequential_thinking（分析问题）
            ↓
       定位问题源头：
       ├─ 数据库分析有误 → 重新执行相应分析工具 → 更新记忆
       ├─ 问题生成有误 → 重新执行 question_generation
       └─ SQL生成有误 → 重新执行 sql_generation
```

### 4.4 ReAct 执行模式
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



## 5. 核心特性

### 5.1 记忆模块
- 存储数据库分析结果供后续使用
- 支持动态更新（根据反思结果）
- 跨工具共享上下文

### 5.2 反思-修正循环
- 自动评估生成质量
- 精确定位问题源头
- 只重新执行出错步骤
- 支持分析工具重新执行

### 5.3 执行轨迹
- 记录完整的执行历史
- 支持调试和分析
- JSON格式持久化

### 5.4 工具设计原则
- 单一职责：每个工具只做一件事
- 标准接口：统一的输入输出格式
- 错误处理：优雅的错误处理机制
- 可组合性：工具间可以灵活组合



## 6. 部署和运行

### 6.1 环境准备
```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 设置数据库和LLM连接信息
```

### 6.2 命令行使用
```bash
# 生成训练数据
python cli.py generate --count 100 --output data.json

# 单次SQL生成
python cli.py query --question "查询所有订单的总金额"

# 查看执行轨迹
python cli.py trajectory --latest
```

### 6.3 API使用
```python
from semanticsql_agent import SQLAgent
from config import Settings, DatabaseConfig

# 初始化
settings = Settings()
db_config = DatabaseConfig.from_env()
agent = SQLAgent(settings)

# 生成训练数据
result = agent.generate_training_data(
    count=100,
    output_file="training_data.json"
)

# 单次查询
response = agent.query("查询最近一周的销售额")
print(response.sql)
```

## 7. 最佳实践

### 7.1 Agent设计原则
- **提示词驱动**：通过提示词引导行为，避免硬编码流程
- **自主决策**：让Agent根据上下文自主选择工具
- **记忆机制**：利用记忆模块在工具间共享上下文
- **反思循环**：执行后评估质量，必要时自动修正

### 7.2 工具开发指南
- **单一职责**：每个工具专注一个任务
- **标准接口**：统一的输入输出格式
- **错误处理**：提供清晰的错误信息
- **可测试性**：便于单元测试和集成测试

### 7.3 性能优化
- **批量处理**：场景批量生成，减少LLM调用
- **记忆复用**：数据库分析结果缓存复用
- **并行执行**：独立的SQL可并行验证
- **增量生成**：支持断点续传和增量生成



