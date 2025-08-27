# SemanticSQL-Agent

> 🤖 基于智能体架构的自然语言到SQL转换系统

## 概述

SemanticSQL-Agent 是一个先进的 NL2SQL（自然语言到SQL）转换系统，采用基于 ReAct（Reasoning and Acting）模式的智能体架构。系统通过工具化的方式实现对数据库的深度理解，生成高质量的SQL查询语句。

### 核心特性

- 🧠 **智能体架构**: 基于 ReAct 的 Thought-Action-Observation 循环
- 🔧 **工具驱动**: 模块化的工具设计，易于扩展
- 📊 **深度理解**: 渐进式的数据库结构和语义理解
- 🔄 **简单反思**: 错误情况下的智能反思和纠正
- 🚀 **高性能**: 异步执行，支持并行工具调用
- 📝 **完整追踪**: 详细的执行轨迹记录

## 快速开始

### 安装

```bash
# 使用 pip
pip install semanticsql-agent

# 或从源码安装
git clone https://github.com/yourusername/semanticsql-agent.git
cd semanticsql-agent
pip install -e .
```

### 基础使用

```python
from semanticsql import NL2SQLAgent, NL2SQLConfig

# 配置
config = NL2SQLConfig(
    model_provider="openai",
    model_name="gpt-4",
    database_url="postgresql://user:pass@localhost/mydb"
)

# 创建智能体
agent = NL2SQLAgent(config)

# 执行查询
result = await agent.execute_nl2sql(
    "Show me total sales by region for last month"
)

print(f"Generated SQL: {result.sql}")
```

### CLI 使用

```bash
# 基础查询
semanticsql -q "Show all active users" -d "postgresql://localhost/mydb"

# 使用配置文件
semanticsql -q "Complex analysis query" -c config.yaml

# 详细输出
semanticsql -q "Sales report" -d "mysql://localhost/sales" --verbose
```

## 架构设计

SemanticSQL-Agent 采用分层架构设计：

```
├── 智能体层 (Agent Layer)
│   ├── BaseAgent - 通用智能体框架
│   └── NL2SQLAgent - SQL生成特化实现
│
├── 工具层 (Tools Layer)
│   ├── 分析工具 - Schema提取、领域分析
│   ├── 生成工具 - SQL生成、验证
│   └── 思考工具 - 深度推理（可选）
│
└── 基础设施层 (Infrastructure Layer)
    ├── LLM客户端 - 多模型支持
    ├── 数据库连接 - 多数据库支持
    └── 配置管理 - 灵活配置
```

### TAO 循环实现

每个执行步骤都遵循 ReAct 模式：

1. **Thought (思考)**: LLM 分析当前状态，决定下一步行动
2. **Action (行动)**: 调用相应工具执行具体任务
3. **Observation (观察)**: 获取工具执行结果，必要时进行反思

## 支持的数据库

- ✅ PostgreSQL
- ✅ MySQL
- 🚧 Oracle (计划中)
- 🚧 SQL Server (计划中)
- 🚧 SQLite (计划中)

## 配置

### 配置文件示例

```yaml
# semanticsql_config.yaml
model:
  provider: openai
  name: gpt-4
  temperature: 0.1

database:
  connection_string: postgresql://user:pass@localhost/db
  pool_size: 5
  
agent:
  max_steps: 15
  tools:
    - extract_database_schema
    - analyze_domain
    - generate_sql_query
    - sequential_thinking
    - task_done
```

### 环境变量

```bash
export OPENAI_API_KEY="your-api-key"
export SEMANTICSQL_DATABASE_URL="postgresql://localhost/mydb"
export SEMANTICSQL_LOG_LEVEL="INFO"
```

## 高级功能

### 自定义工具

```python
from semanticsql.tools import Tool, ToolResult

class CustomAnalysisTool(Tool):
    def get_name(self) -> str:
        return "custom_analysis"
        
    async def execute(self, **kwargs) -> ToolResult:
        # 实现自定义逻辑
        return ToolResult(success=True, data={...})

# 注册工具
agent.register_tool(CustomAnalysisTool())
```

### 深度思考

对于复杂查询，系统会自动启用 Sequential Thinking Tool：

```python
# 自动处理复杂查询
result = await agent.execute_nl2sql(
    "Find customers who placed orders in the last 3 months but not in the previous 3 months, grouped by region with their average order value"
)
```

## 性能优化

- **Schema 缓存**: 自动缓存数据库结构信息
- **并行执行**: 支持多工具并行调用
- **连接池**: 数据库连接池管理
- **Token 优化**: 智能的上下文管理

## 开发

### 环境设置

```bash
# 克隆仓库
git clone https://github.com/yourusername/semanticsql-agent.git
cd semanticsql-agent

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# 安装开发依赖
pip install -e ".[dev]"
```

### 运行测试

```bash
# 单元测试
pytest tests/unit

# 集成测试
pytest tests/integration

# 覆盖率报告
pytest --cov=semanticsql tests/
```

### 代码质量

```bash
# 类型检查
mypy semanticsql

# 代码格式化
black semanticsql
ruff check semanticsql
```

## 贡献指南

我们欢迎各种形式的贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解详情。

## 路线图

- [ ] v0.1.0 - MVP 版本
- [ ] v0.2.0 - 多数据库支持
- [ ] v0.3.0 - Web UI
- [ ] v1.0.0 - 企业级特性

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

## 致谢

- 感谢 [TRAEAgent](https://github.com/ByteDance/trae-agent) 项目提供的架构灵感
- 基于 ReAct 论文的智能体设计模式

## 联系方式

- 问题反馈: [GitHub Issues](https://github.com/yourusername/semanticsql-agent/issues)
- 讨论: [GitHub Discussions](https://github.com/yourusername/semanticsql-agent/discussions)
- 邮件: semanticsql@example.com

---

<p align="center">
  Made with ❤️ by the SemanticSQL Team
</p>