# SemanticSQL Agent 项目结构

## 1. 项目目录结构

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
│   ├── settings.py              # 统一配置管理
│   └── config.yaml             # 默认配置文件
│
├── core/                       # 核心模块
│   ├── __init__.py
│   ├── models.py               # 所有数据模型
│   ├── exceptions.py           # 自定义异常
│   └── constants.py            # 常量定义
│
├── agent/                      # 智能体模块
│   ├── __init__.py
│   ├── base_agent.py           # 基础Agent（含执行记录）
│   ├── smart_sql_agent.py      # SQL数据生成Agent
│   └── execution_tracker.py    # 执行轨迹记录器
│
├── tools/                      # 工具模块
│   ├── __init__.py
│   ├── base_tool.py            # 工具基类
│   │
│   ├── analysis/               # 分析工具
│   │   ├── __init__.py
│   │   ├── schema_extraction_tool.py   # 数据库结构提取
│   │   ├── domain_analysis_tool.py     # 领域分析
│   │   ├── field_classification_tool.py # 字段分类
│   │   └── er_analysis_tool.py         # 关系分析
│   │
│   ├── generation/             # 生成工具
│   │   ├── __init__.py
│   │   ├── scenario_tool.py           # 场景生成
│   │   ├── operation_selection_tool.py # 操作选择
│   │   ├── question_generation_tool.py # 问题生成
│   │   └── sql_generation_tool.py     # SQL生成
│   │
│   ├── validation/             # 验证执行工具
│   │   ├── __init__.py
│   │   ├── sql_validation_tool.py     # SQL语法验证
│   │   └── sql_execution_tool.py      # SQL执行测试
│   │
│   └── reflection/             # 反思优化工具
│       ├── __init__.py
│       └── sql_reflection_tool.py      # SQL执行反思与优化
│
├── prompts/                    # 提示词管理
│   ├── __init__.py
│   ├── system_prompt.yaml      # 系统提示词
│   ├── tool_prompts.yaml       # 工具提示词
│   └── prompt_manager.py       # 提示词管理器
│
├── utils/                      # 工具模块
│   ├── __init__.py
│   ├── database.py             # 数据库连接工具
│   ├── llm_client.py           # LLM客户端（支持Qwen）
│   ├── logger.py               # 日志配置
│   ├── output_handler.py       # 输出处理
│   └── helpers.py              # 辅助函数
│
├── cli/                        # 命令行接口
│   ├── __init__.py
│   └── cli.py                  # 命令行接口
│
├── output/                     # 输出目录（运行时生成）
│   └── .gitkeep
│
├── tests/                      # 测试模块
│   ├── __init__.py
│   ├── conftest.py             # pytest配置
│   ├── test_tools/             # 工具测试
│   │   ├── __init__.py
│   │   ├── test_scenario_tool.py
│   │   └── test_sql_tools.py
│   ├── test_agent/             # 智能体测试
│   │   ├── __init__.py
│   │   └── test_smart_sql_agent.py
│   └── test_integration.py     # 集成测试
│
├── examples/                   # 示例代码
│   ├── __init__.py
│   ├── basic_usage.py          # 基础示例
│   ├── custom_tool.py          # 自定义工具示例
│   └── batch_generation.py     # 批量生成示例
│
├── scripts/                    # 脚本
│   ├── setup_dev.sh           # 开发环境设置
│   ├── run_tests.sh           # 运行测试
│   └── build_docker.sh        # 构建Docker镜像
│
└── docs/                      # 文档
    ├── API.md                 # API文档
    ├── CONTRIBUTING.md        # 贡献指南
    └── CHANGELOG.md           # 变更日志
```

## 2. 模块说明

### 2.1 核心模块 (core/)

#### models.py - 数据模型定义
- `AgentStep`: 执行步骤模型
- `AgentExecution`: 执行记录模型
- `QueryScenario`: 查询场景模型
- `GeneratedExample`: 生成样本模型
- 其他业务相关模型

#### exceptions.py - 自定义异常
```python
class SemanticSQLError(Exception):
    """基础异常类"""
    pass

class ConfigurationError(SemanticSQLError):
    """配置错误"""
    pass

class ToolExecutionError(SemanticSQLError):
    """工具执行错误"""
    pass

class DatabaseConnectionError(SemanticSQLError):
    """数据库连接错误"""
    pass
```

#### constants.py - 常量定义
```python
# 支持的数据库类型
SUPPORTED_DATABASES = ["mysql", "postgresql", "sqlite"]

# 默认配置
DEFAULT_MAX_STEPS = 30
DEFAULT_TEMPERATURE = 0.7

# SQL类型
SQL_TYPES = {
    "SELECT": "基础查询",
    "JOIN": "关联查询",
    "GROUP": "聚合查询",
    "SUBQUERY": "子查询",
    "WINDOW": "窗口函数"
}
```

### 2.2 智能体模块 (agent/)

#### base_agent.py
- 实现 ReAct 模式的基础类
- 提供工具注册和调用机制
- 管理执行流程

#### smart_sql_agent.py
- 继承自 BaseAgent
- 专门用于 NL2SQL 数据生成
- 注册所有必需的工具

#### execution_tracker.py
- 记录执行轨迹
- 提供执行摘要
- 支持调试和分析

### 2.3 工具模块 (tools/)

#### 工具命名规范
- 所有工具文件以 `_tool.py` 结尾
- 工具类名以 `Tool` 结尾
- 工具名称使用下划线命名法

#### 工具分类

**分析工具 (analysis/)**
- `schema_extraction_tool.py`: 提取数据库结构信息
- `domain_analysis_tool.py`: 分析业务领域
- `field_classification_tool.py`: 对字段进行分类
- `er_analysis_tool.py`: 分析实体关系

**生成工具 (generation/)**
- `scenario_tool.py`: 基于规则生成业务场景
- `operation_selection_tool.py`: 为场景选择SQL操作
- `question_generation_tool.py`: 生成自然语言问题
- `sql_generation_tool.py`: 生成SQL查询

**验证工具 (validation/)**
- `sql_validation_tool.py`: 验证SQL语法
- `sql_execution_tool.py`: 执行SQL测试

**反思工具 (reflection/)**
- `sql_reflection_tool.py`: 分析执行结果并优化

### 2.4 提示词管理 (prompts/)

#### 文件结构
- `system_prompt.yaml`: 系统级提示词配置
- `tool_prompts.yaml`: 各工具的提示词
- `prompt_manager.py`: 统一的提示词加载和管理

#### 提示词组织
```yaml
# system_prompt.yaml
agent:
  role: "你是一个智能的SQL训练数据生成专家"
  instructions: |
    使用ReAct模式工作：
    - Thought: 分析当前状态
    - Action: 选择工具执行
    - Observation: 观察结果

# tool_prompts.yaml
scenario_generator:
  description: "基于数据库结构生成业务场景"
  prompt_template: |
    分析以下数据库结构：
    {schema}
    生成{count}个业务查询场景
```

### 2.5 工具函数 (utils/)

#### database.py
- 数据库连接管理
- 连接池配置
- 查询执行工具

#### llm_client.py
- LLM客户端封装
- 支持Qwen API
- 错误重试机制

#### logger.py
- 日志配置
- 支持文件和控制台输出
- 结构化日志格式

#### output_handler.py
- 结果格式化
- 支持多种输出格式（JSON、JSONL、CSV）
- 数据转换工具

### 2.6 CLI模块 (cli/)

#### 命令结构
```bash
semanticsql-agent
├── generate        # 生成数据
├── test-connection # 测试连接
├── init           # 初始化配置
└── version        # 显示版本
```

## 3. 配置文件

### 3.1 环境变量 (.env)
```bash
# API配置
DASHSCOPE_API_KEY=your_api_key

# 数据库配置
DB_PASSWORD=your_password

# 日志配置
LOG_LEVEL=INFO
```

### 3.2 配置文件 (config/config.yaml)
```yaml
database:
  type: mysql
  host: localhost
  port: 3306
  username: root
  password: ${DB_PASSWORD}
  database: your_db

llm:
  model: qwen-plus
  base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
  api_key: ${DASHSCOPE_API_KEY}
  
agent:
  max_steps: 30
  enable_reflection: true
```

## 4. 测试结构

### 4.1 单元测试
- 每个工具都有对应的测试文件
- 测试覆盖正常和异常情况
- 使用 Mock 避免外部依赖

### 4.2 集成测试
- 测试完整的数据生成流程
- 验证工具之间的协作
- 检查最终输出质量

### 4.3 测试数据
- 使用 fixtures 提供测试数据
- 支持多种数据库结构
- 包含边界情况

## 5. 开发流程

### 5.1 添加新工具
1. 在适当的工具目录创建 `*_tool.py` 文件
2. 继承 `BaseTool` 类
3. 实现必需的方法和属性
4. 在智能体中注册工具
5. 编写对应的测试

### 5.2 扩展智能体
1. 继承 `BaseAgent` 或 `SmartSQLAgent`
2. 自定义系统提示词
3. 添加特定的工具
4. 实现自定义逻辑

### 5.3 添加新的输出格式
1. 在 `output_handler.py` 添加格式化函数
2. 在 CLI 中添加格式选项
3. 更新文档

## 6. 部署结构

### 6.1 Docker支持
- Dockerfile 用于构建镜像
- docker-compose.yml 用于编排服务
- 支持环境变量配置

### 6.2 脚本工具
- `setup_dev.sh`: 设置开发环境
- `run_tests.sh`: 运行所有测试
- `build_docker.sh`: 构建Docker镜像

## 7. 文档结构

### 7.1 用户文档
- README.md: 项目介绍和快速开始
- docs/API.md: API参考文档

### 7.2 开发文档
- docs/CONTRIBUTING.md: 贡献指南
- 代码中的docstring

### 7.3 变更记录
- docs/CHANGELOG.md: 版本变更历史

这个项目结构设计遵循了Python项目的最佳实践，具有良好的模块化、可扩展性和可维护性。