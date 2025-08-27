# SemanticSQL-Agent

基于 LangChain 和 LangGraph 的智能 SQL 生成系统。

## 特性

- 🔗 **LangGraph 工作流**：清晰的状态管理和流程控制
- 🛠️ **LangChain 工具**：模块化的分析和生成工具
- 📝 **格式化输出**：使用 Pydantic 确保输入输出格式
- 🤖 **本地模型支持**：通过 vLLM 支持本地大模型
- 💾 **MySQL 支持**：专注于 MySQL 数据库

## 快速开始

### 安装

```bash
git clone https://github.com/yourusername/semanticsql-agent.git
cd semanticsql-agent
pip install -r requirements.txt
```

### 配置

创建 `.env` 文件：

```bash
# LLM 配置
MODEL_NAME=Qwen3-14B
API_KEY=not-needed
BASE_URL=http://192.168.200.216:9009/v1

# 数据库配置
DB_HOST=192.168.200.216
DB_PORT=13306
DB_USER=testuser
DB_PASSWORD=testpass
DB_DATABASE=testdb
```

### 使用

```python
from agent.nl2sql_agent import NL2SQLAgent

# 创建智能体
agent = NL2SQLAgent()

# 生成 SQL
result = agent.generate_sql("查询每个部门的平均工资")

print(f"SQL: {result.sql}")
print(f"置信度: {result.confidence}")
print(f"使用的表: {result.tables_used}")
```

### 命令行

```bash
# 基础使用
python -m cli "查询所有订单信息"

# 指定参数
python -m cli "统计每月销售额" \
  --model Qwen3-14B \
  --base-url http://192.168.200.216:9009/v1 \
  --host 192.168.200.216 \
  --port 13306 \
  --user testuser \
  --password testpass \
  --database testdb
```

## 架构

```
智能体执行流程:
┌─────────────┐
│   用户查询   │
└──────┬──────┘
       ▼
┌─────────────┐
│ Schema提取   │ ← LangChain SQL Tools
└──────┬──────┘
       ▼
┌─────────────┐
│ 领域分析     │ ← LLM + PromptTemplate
└──────┬──────┘
       ▼
┌─────────────┐
│ 字段分类     │ ← 格式化输出 (Pydantic)
└──────┬──────┘
       ▼
┌─────────────┐
│ 关系分析     │ ← ER 关系识别
└──────┬──────┘
       ▼
┌─────────────┐
│ SQL生成      │ ← 结构化生成
└──────┬──────┘
       ▼
┌─────────────┐
│ 格式化输出   │ ← SQLResult
└─────────────┘
```

## 工具列表

| 工具名称 | 功能描述 | 输入 | 输出 |
|---------|---------|------|------|
| SchemaExtractionTool | 提取数据库结构 | database_name | 表结构信息 |
| InitialDomainAnalysisTool | 分析业务领域 | schema, query | 领域描述 |
| FieldClassificationTool | 字段分类 | tables | 维度/度量分类 |
| TableDescriptionTool | 生成表描述 | tables | 表业务含义 |
| ColumnDescriptionTool | 生成列描述 | columns | 列业务含义 |
| ERAnalysisTool | 实体关系分析 | schema | 关系图谱 |
| ScenarioGenerationTool | 场景识别 | context | 查询场景 |
| SQLGenerationTool | SQL 生成 | all_context | SQL 语句 |

## 配置说明

### LLM 配置
- 支持 OpenAI API 兼容的服务
- 推荐使用 vLLM 部署本地模型
- 温度设置为 0.1 保证稳定输出

### 数据库配置
- 目前仅支持 MySQL
- 需要 INFORMATION_SCHEMA 读取权限
- 建议使用只读账户

## 开发

### 项目结构

```
semanticsql-agent/
├── agent/          # 智能体核心
├── tools/          # LangChain 工具
├── models/         # Pydantic 模型
├── prompts/        # 提示词模板
└── utils/          # 工具函数
```

### 添加新工具

1. 继承 `BaseTool`
2. 定义 `args_schema`
3. 实现 `_run` 方法
4. 在工作流中添加节点

### 测试

```bash
# 运行测试
pytest tests/

# 测试特定工具
pytest tests/test_tools.py::test_schema_extraction
```

## 限制

- 仅支持 MySQL 数据库
- 需要稳定的 LLM 服务
- 复杂查询可能需要多次优化

## 贡献

欢迎提交 Issue 和 Pull Request！

## 作者

李振平 - lizhenping18@mails.ucas.ac.cn

## License

MIT