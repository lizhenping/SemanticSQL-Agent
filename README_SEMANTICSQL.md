# SemanticSQL-Agent

基于智能体架构的自然语言到SQL转换系统。

## 特性

- 基于 ReAct (Thought-Action-Observation) 模式
- 工具驱动的渐进式数据库理解
- 参考 TRAEAgent 的成熟架构
- 借鉴 nl2sql_pipeline 的实现

## 快速开始

### 安装

```bash
git clone https://github.com/yourusername/semanticsql-agent.git
cd semanticsql-agent
pip install -r requirements.txt
```

### 基础使用

```python
from semanticsql import NL2SQLAgent, DatabaseConfig

# 配置数据库
db_config = DatabaseConfig(
    host="localhost",
    user="root",
    password="password",
    database="test_db"
)

# 创建智能体
agent = NL2SQLAgent(db_config)

# 执行查询
result = agent.execute_nl2sql("查询每个部门的平均工资")
print(result["sql"])
```

### 命令行使用

```bash
python -m semanticsql.cli "查询所有订单" --user root --password pass --database mydb
```

## 配置

创建 `semanticsql_config.yaml`:

```yaml
openai:
  api_key: "your-api-key"
  model: "gpt-4"

database:
  host: localhost
  port: 3306
  user: root
  password: password
  database: test_db
```

## 支持的数据库

- MySQL 5.7+

## 工具列表

1. **schema_extraction** - 提取数据库结构
2. **initial_domain_analysis** - 初始领域分析
3. **field_classification** - 字段分类
4. **table_description** - 表描述生成
5. **column_description** - 列描述生成
6. **er_analysis** - 实体关系分析
7. **scenario_generation** - 场景生成
8. **sql_generation** - SQL生成
9. **sequential_thinking** - 深度思考（可选）
10. **task_done** - 任务完成标记

## 项目结构

```
semanticsql-agent/
├── semanticsql/
│   ├── agent/          # 智能体核心
│   ├── tools/          # 工具实现
│   ├── config/         # 配置管理
│   ├── services/       # 数据库服务
│   └── utils/          # 工具函数
├── examples/           # 使用示例
└── tests/             # 测试用例
```

## 开发

### 添加新工具

1. 在 `tools/` 目录创建新文件
2. 继承 `Tool` 基类
3. 实现 `get_name()`, `get_description()`, `execute()` 方法
4. 在智能体中注册工具

### 运行测试

```bash
pytest tests/
```

## 依赖

- Python 3.11+
- OpenAI API
- PyMySQL
- PyYAML
- Rich (CLI美化)

## 作者

李振平 - lizhenping18@mails.ucas.ac.cn

## 许可证

MIT License