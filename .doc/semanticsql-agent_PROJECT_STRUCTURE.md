# SemanticSQL Agent 项目结构

```
semanticsql-agent/
├── agent/                      # 智能体核心模块
│   ├── __init__.py
│   ├── base_agent.py          # ReAct模式基础智能体实现
│   └── smart_sql_agent.py     # SQL分析专用智能体
│
├── cli/                       # 命令行接口
│   ├── __init__.py
│   └── cli.py                 # Click命令定义和实现
│
├── config/                    # 配置管理
│   ├── __init__.py
│   └── trae_config.py         # 统一配置系统（支持YAML和环境变量）
│
├── database/                  # 数据库管理
│   ├── __init__.py
│   └── connection_manager.py  # 数据库连接池和管理
│
├── models/                    # 数据模型
│   ├── __init__.py
│   └── sql_result.py          # SQL查询结果模型
│
├── tools/                     # 工具集合
│   ├── __init__.py           # 工具注册和工厂方法
│   ├── trae_base_tool.py     # 工具基类定义
│   ├── agent_tools.py        # Agent辅助工具
│   │   ├── DatabaseConnectionTool    # 数据库连接
│   │   ├── SchemaAnalysisTool       # 模式分析
│   │   ├── QueryGenerationTool      # SQL生成
│   │   ├── QueryExecutionTool       # SQL执行
│   │   ├── DataAnalysisTool         # 数据分析
│   │   └── ReasoningTool            # 推理辅助
│   ├── sql_tools.py          # SQL专用工具
│   │   ├── SyncSchemaExtractionTool # 模式提取
│   │   ├── SyncSQLGenerationTool    # SQL生成
│   │   ├── SyncSQLValidationTool    # SQL验证
│   │   └── SyncSQLExecutionTool     # SQL执行
│   └── analysis_tools.py     # 分析工具
│       ├── SyncDomainAnalysisTool        # 领域分析
│       ├── SyncFieldClassificationTool   # 字段分类
│       ├── SyncERAnalysisTool           # ER关系分析
│       └── SyncSequentialThinkingTool   # 序列思考
│
├── utils/                    # 工具类
│   ├── __init__.py
│   ├── trajectory_recorder.py # 执行轨迹记录
│   └── cli/                  # CLI相关工具
│       ├── __init__.py
│       ├── cli_console.py    # 控制台基类
│       ├── console_factory.py # 控制台工厂
│       ├── rich_console.py   # Rich库控制台
│       └── simple_console.py # 简单控制台
│
├── tests/                    # 测试用例
│   ├── __init__.py
│   └── test_config.py        # 配置测试
│
├── __init__.py              # 包初始化
├── main.py                  # 程序入口
├── CLAUDE.md                # Claude AI使用指南
├── 命令行指令.md             # 命令行使用说明
└── .gitignore               # Git忽略文件
```

## 模块说明

### 1. agent/ - 智能体模块
- **base_agent.py**: 实现ReAct（Reasoning + Acting）模式的基础类
- **smart_sql_agent.py**: 继承BaseAgent，专门用于数据库分析和NL2SQL数据生成

### 2. cli/ - 命令行接口
- **cli.py**: 定义所有CLI命令
  - `init`: 初始化配置
  - `test`: 测试数据库连接
  - `schema`: 查看数据库结构
  - `run`: 执行单次查询
  - `interactive`: 交互模式
  - `smart-analyze`: 智能分析（核心功能）

### 3. config/ - 配置管理
- **trae_config.py**: 统一配置系统
  - DatabaseConfig: 数据库配置
  - LLMConfig: 大模型配置
  - AgentConfig: Agent配置
  - TraeConfig: 总配置类

### 4. tools/ - 工具系统
核心工具分为三类：
- **agent_tools.py**: Agent直接使用的工具
- **sql_tools.py**: SQL相关的同步工具
- **analysis_tools.py**: 深度分析工具

### 5. 执行流程工具
1. DatabaseConnectionTool - 连接数据库
2. DomainAnalysisTool - 分析业务领域
3. FieldClassificationTool - 字段语义分类
4. SchemaAnalysisTool - 表结构分析
5. ERAnalysisTool - 实体关系分析
6. QueryGenerationTool - 生成查询场景（问题+SQL）

### 6. utils/ - 实用工具
- **trajectory_recorder.py**: 记录Agent执行轨迹
- **cli/**: 不同类型的控制台实现