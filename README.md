# SemanticSQL-Agent

基于 LangChain 和 TRAEAgent 设计理念的自然语言到 SQL 转换系统。

## 特性

- 🤖 基于 LangChain 的 ReAct Agent
- 🔍 完整的数据库结构分析
- 💡 智能的业务领域理解
- ✅ SQL 语法验证和执行
- 📝 Jinja2 提示词模板管理
- 🎯 专注于 NL2SQL 核心功能

## 快速开始

### 安装

```bash
pip install langchain>=0.1.0 langchain-openai>=0.0.5 langchain-community>=0.0.10
pip install pymysql sqlalchemy pydantic>=2.0 jinja2 pyyaml
```

### 配置

创建 `config.yaml`:

```yaml
model:
  name: "Qwen3-14B"
  provider: "openai"
  base_url: "http://192.168.200.216:9009/v1"
  api_key: "not-needed"
  temperature: 0.1

database:
  host: "192.168.200.216"
  port: 13306
  user: "testuser"
  password: "testpass"
  database: "testdb"

agent:
  max_iterations: 15
  enable_thinking: true
```

### 使用

```python
from agent.sql_agent import SemanticSQLAgent
import yaml

# 加载配置
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# 创建 agent
agent = SemanticSQLAgent(config)

# 执行查询
result = agent.query("查询每个部门的平均工资")
print(f"SQL: {result['sql']}")
print(f"结果: {result['answer']}")
```

### 命令行

```bash
# 交互模式
python cli.py

# 单次查询
python cli.py -q "查询所有客户信息"
```

## 架构设计

采用模块化设计，核心组件包括：

- **Agent**: 基于 LangChain 的智能体协调器
- **Tools**: 独立的功能工具（分析、生成、验证）
- **Prompts**: Jinja2 模板管理
- **Models**: Pydantic 数据模型

## 工具链

1. **分析工具**
   - `extract_database_schema`: 提取数据库结构
   - `analyze_business_domain`: 分析业务领域
   - `classify_table_fields`: 字段类型分类

2. **生成工具**
   - `generate_sql`: 生成 SQL 查询

3. **验证工具**
   - `validate_sql`: 验证 SQL 语法
   - `execute_sql`: 执行 SQL 并返回结果

## 开发者

- 邮箱: lizhenping18@mails.ucas.ac.cn

## 许可证

MIT License