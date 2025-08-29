# SemanticSQL Agent 项目结构设计

## 1. 完整项目结构

```
semanticsql-agent/
├── README.md                    # 项目说明文档
├── setup.py                     # 安装配置
├── requirements.txt             # 依赖列表
├── .env.example                # 环境变量示例
├── .gitignore                  # Git忽略文件
│
├── config/                     # 配置模块
│   ├── __init__.py
│   ├── settings.py             # 全局配置管理
│   ├── database.py             # 数据库配置
│   └── example.yaml            # 配置示例文件
│
├── core/                       # 核心模块
│   ├── __init__.py
│   ├── models.py               # Pydantic数据模型
│   ├── exceptions.py           # 自定义异常
│   └── constants.py            # 常量定义
│
├── agent/                      # 智能体模块
│   ├── __init__.py
│   ├── base_agent.py           # 基础Agent类（ReAct实现）
│   ├── smart_sql_agent.py      # SQL智能体
│   ├── executor.py             # 执行器（含轨迹记录）
│   └── context.py              # 执行上下文管理
│
├── tools/                      # 工具模块
│   ├── __init__.py
│   ├── base.py                 # 工具基类
│   │
│   ├── analysis/               # 分析工具
│   │   ├── __init__.py
│   │   ├── schema_analyzer.py         # 数据库结构分析
│   │   ├── domain_analyzer.py         # 领域识别
│   │   ├── field_classifier.py        # 字段分类
│   │   └── relationship_analyzer.py   # 关系分析
│   │
│   ├── generation/             # 生成工具
│   │   ├── __init__.py
│   │   ├── scenario_generator.py      # 场景生成（基于规则）
│   │   ├── question_generator.py      # 问题生成
│   │   └── sql_generator.py          # SQL生成（一步完成）
│   │
│   ├── sql/                    # SQL操作工具
│   │   ├── __init__.py
│   │   ├── sql_executor.py            # SQL执行
│   │   ├── sql_validator.py           # SQL验证
│   │   └── sql_optimizer.py           # SQL优化建议
│   │
│   └── reflection/             # 反思工具
│       ├── __init__.py
│       ├── execution_analyzer.py      # 执行结果分析
│       └── quality_improver.py        # 质量改进建议
│
├── prompts/                    # 提示词管理
│   ├── __init__.py
│   ├── system.yaml             # 系统级提示词
│   ├── tools.yaml              # 工具提示词配置
│   ├── templates/              # 提示词模板
│   │   ├── __init__.py
│   │   ├── react/              # ReAct相关模板
│   │   │   ├── thought.j2
│   │   │   └── action.j2
│   │   ├── analysis/           # 分析类模板
│   │   │   ├── domain.j2
│   │   │   └── schema.j2
│   │   ├── generation/         # 生成类模板
│   │   │   ├── scenario.j2
│   │   │   ├── question.j2
│   │   │   └── sql.j2
│   │   └── reflection/         # 反思类模板
│   │       ├── execution.j2
│   │       └── quality.j2
│   └── loader.py               # 提示词加载器
│
├── utils/                      # 工具模块
│   ├── __init__.py
│   ├── database.py             # 数据库连接管理
│   ├── llm_client.py           # LLM客户端封装
│   ├── logger.py               # 日志工具
│   ├── validators.py           # 数据验证工具
│   └── helpers.py              # 辅助函数
│
├── output/                     # 输出处理
│   ├── __init__.py
│   ├── formatter.py            # 结果格式化
│   ├── exporter.py             # 导出器（JSON/CSV/SQL）
│   └── adapters/               # 导出适配器
│       ├── __init__.py
│       ├── huggingface.py      # HuggingFace格式
│       └── jsonl.py            # JSONL格式
│
├── cli/                        # 命令行接口
│   ├── __init__.py
│   ├── cli.py                  # 主CLI入口
│   ├── commands/               # CLI命令
│   │   ├── __init__.py
│   │   ├── analyze.py          # smart-analyze命令
│   │   ├── test.py             # 测试相关命令
│   │   └── config.py           # 配置相关命令
│   └── utils.py                # CLI工具函数
│
├── tests/                      # 测试模块
│   ├── __init__.py
│   ├── conftest.py             # pytest配置
│   ├── unit/                   # 单元测试
│   │   ├── __init__.py
│   │   ├── test_tools/         # 工具测试
│   │   ├── test_agent/         # 智能体测试
│   │   └── test_models.py      # 模型测试
│   ├── integration/            # 集成测试
│   │   ├── __init__.py
│   │   └── test_workflow.py    # 工作流测试
│   └── fixtures/               # 测试数据
│       ├── __init__.py
│       └── sample_data.py
│
├── examples/                   # 示例代码
│   ├── __init__.py
│   ├── basic_usage.py          # 基础使用示例
│   ├── custom_tool.py          # 自定义工具示例
│   └── advanced_agent.py       # 高级智能体示例
│
├── scripts/                    # 脚本
│   ├── setup_dev.sh           # 开发环境设置
│   ├── run_tests.sh           # 运行测试
│   └── build_docker.sh        # 构建Docker镜像
│
└── docs/                      # 文档
    ├── api/                   # API文档
    ├── tutorials/             # 教程
    └── deployment/            # 部署文档
```

## 2. 核心模块详细说明

### 2.1 配置模块 (config/)
- **settings.py**: 统一的配置管理，支持YAML文件和环境变量
- **database.py**: 数据库相关配置类
- **example.yaml**: 配置文件示例，供用户参考

### 2.2 核心模块 (core/)
- **models.py**: 所有Pydantic数据模型定义，包括：
  - 输入模型（TaskRequest）
  - 分析模型（SchemaAnalysis, DomainAnalysis等）
  - 生成模型（QueryScenario, GeneratedQuestion, GeneratedSQL）
  - 执行模型（AgentStep, AgentExecution）
  - 输出模型（TrainingExample, TrainingDataset）
- **exceptions.py**: 自定义异常类
- **constants.py**: 系统常量定义

### 2.3 智能体模块 (agent/)
- **base_agent.py**: 实现ReAct模式的基础Agent类
- **smart_sql_agent.py**: 专门用于NL2SQL数据生成的智能体
- **executor.py**: 任务执行器，负责执行管理和轨迹记录
- **context.py**: 执行上下文管理

### 2.4 工具模块 (tools/)
工具按功能分为四大类：

#### 分析工具 (analysis/)
- **schema_analyzer.py**: 分析数据库表结构
- **domain_analyzer.py**: 识别业务领域
- **field_classifier.py**: 对字段进行分类
- **relationship_analyzer.py**: 分析表之间的关系

#### 生成工具 (generation/)
- **scenario_generator.py**: 基于规则生成业务场景
- **question_generator.py**: 生成自然语言问题
- **sql_generator.py**: 一步生成对应的SQL查询

#### SQL工具 (sql/)
- **sql_executor.py**: 执行SQL查询
- **sql_validator.py**: 验证SQL语法
- **sql_optimizer.py**: 提供SQL优化建议

#### 反思工具 (reflection/)
- **execution_analyzer.py**: 分析SQL执行结果
- **quality_improver.py**: 提供质量改进建议

### 2.5 提示词管理 (prompts/)
- **system.yaml**: 系统级提示词配置
- **tools.yaml**: 各工具的提示词配置
- **templates/**: Jinja2模板文件
- **loader.py**: 提示词加载和管理器

### 2.6 工具函数 (utils/)
- **database.py**: 数据库连接和操作工具
- **llm_client.py**: LLM客户端封装（支持Qwen）
- **logger.py**: 日志配置和管理
- **validators.py**: 数据验证函数
- **helpers.py**: 通用辅助函数

### 2.7 输出处理 (output/)
- **formatter.py**: 格式化输出结果
- **exporter.py**: 导出为不同格式
- **adapters/**: 特定格式的适配器

### 2.8 CLI接口 (cli/)
- **cli.py**: 主命令行入口
- **commands/**: 具体的命令实现
- **utils.py**: CLI相关的工具函数

### 2.9 测试 (tests/)
- **unit/**: 单元测试
- **integration/**: 集成测试
- **fixtures/**: 测试数据和夹具

## 3. 关键设计特点

### 3.1 基于智能体的架构
- 采用ReAct（Reasoning + Acting）模式
- 智能体自主决定执行步骤
- 工具通过智能体协调工作

### 3.2 模块化设计
- 清晰的模块边界
- 高内聚低耦合
- 易于扩展和维护

### 3.3 配置灵活性
- 支持YAML配置文件
- 支持环境变量
- 配置优先级：命令行 > 环境变量 > 配置文件

### 3.4 工具生态系统
- 统一的工具基类
- 标准化的接口
- 支持Function Calling

### 3.5 完整的数据流
- 从输入到输出的完整数据模型
- 类型安全（使用Pydantic）
- 数据验证和转换

## 4. 开发规范

### 4.1 代码风格
- 遵循PEP 8规范
- 使用Black进行代码格式化
- 使用mypy进行类型检查

### 4.2 测试要求
- 单元测试覆盖率 > 80%
- 所有工具必须有对应的测试
- 集成测试覆盖主要流程

### 4.3 文档规范
- 所有模块和函数必须有docstring
- README文档保持更新
- API文档自动生成

### 4.4 版本控制
- 使用语义化版本号
- 维护CHANGELOG
- 标记重要的release

## 5. 部署考虑

### 5.1 依赖管理
- 使用requirements.txt管理依赖
- 区分开发依赖和生产依赖
- 锁定关键依赖版本

### 5.2 配置管理
- 敏感信息使用环境变量
- 提供配置模板
- 支持多环境配置

### 5.3 日志和监控
- 结构化日志
- 不同级别的日志输出
- 性能指标收集

### 5.4 错误处理
- 优雅的错误处理
- 详细的错误信息
- 错误恢复机制

这个项目结构设计体现了现代Python项目的最佳实践，完全基于智能体架构，具有良好的可扩展性和可维护性。