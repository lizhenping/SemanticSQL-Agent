# SemanticSQL-Agent

基于 LangChain 和 TRAEAgent 设计理念的自然语言到 SQL 转换系统。

## ✨ 特性

- 🤖 基于 LangChain 的 ReAct Agent 架构
- 🔍 完整的数据库结构分析和业务理解
- 💡 智能的 SQL 生成和验证
- 📝 Jinja2 提示词模板管理
- 🎯 专注于 NL2SQL 核心功能
- 📊 详细的执行轨迹记录

## 🚀 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置

1. 生成配置文件模板：

```bash
python cli.py init --output config.yaml
```

2. 修改配置文件中的数据库和模型设置。

### 基本使用

#### 命令行模式

```bash
# 单次查询
python cli.py run "查询所有客户信息"

# 从文件读取查询
python cli.py run --file query.txt

# 使用自定义配置
python cli.py run "查询本月销售额" --config custom_config.yaml

# 保存执行轨迹
python cli.py run "统计每个部门的平均工资" --save-trajectory trajectory.json

# 交互式模式
python cli.py interactive

# 生成配置文件模板
python cli.py init --output my_config.yaml
```

#### Python API

```python
from agent import SemanticSQLAgent

# 创建智能体
agent = SemanticSQLAgent()

# 执行查询
result = agent.query("查询销售额最高的10个产品")

if result.success:
    print(f"SQL: {result.sql}")
    print(f"结果: {result.answer}")
else:
    print(f"错误: {result.error}")
```

## 📁 项目结构

```
semanticsql-agent/
├── agent/                # 智能体核心
│   ├── sql_agent.py     # 主智能体实现
│   └── callbacks.py     # 轨迹记录
├── tools/               # 工具集
│   ├── analysis_tools/  # 分析工具
│   ├── generation_tools/# 生成工具
│   └── validation_tools/# 验证工具
├── prompts/            # 提示词模板
├── config/             # 配置管理
├── models/             # 数据模型
└── utils/              # 工具函数
```

## 🛠️ 工具链

### 分析工具
- `extract_database_schema`: 提取数据库结构
- `analyze_business_domain`: 分析业务领域
- `classify_table_fields`: 字段类型分类
- `analyze_entity_relationships`: 实体关系分析

### 生成工具
- `generate_sql`: 生成 SQL 查询

### 验证工具
- `validate_sql`: 验证 SQL 语法
- `execute_sql`: 执行 SQL 并返回结果

### 思考工具（可选）
- `deep_thinking`: 深度分析复杂问题

## ⚙️ 配置说明

### 模型配置

支持多种 LLM：
- OpenAI GPT 系列
- 本地 vLLM 服务
- 其他 LangChain 支持的模型

### 数据库配置

目前支持 MySQL，配置示例：

```yaml
database:
  host: "localhost"
  port: 3306
  user: "root"
  password: "password"
  database: "test_db"
```

## 📊 轨迹分析

分析执行轨迹：

```bash
# 查看轨迹摘要
python cli.py analyze trajectory.json

# 导出时间线
python cli.py analyze trajectory.json -e timeline.txt
```

## 🔧 高级用法

### 自定义工具

创建新工具：

```python
from tools.base import BaseSemanticSQLTool

class CustomTool(BaseSemanticSQLTool):
    name = "custom_tool"
    description = "自定义工具描述"
    
    def execute(self, **kwargs):
        # 实现工具逻辑
        pass
```

### 自定义提示词

在 `prompts/templates/` 目录下创建 Jinja2 模板。

## 📝 示例查询

- 简单查询：`显示所有表`
- 聚合查询：`统计每个部门的平均工资`
- 复杂查询：`找出上个月销售额最高的10个产品及其类别`
- 多表查询：`查询每个客户的订单总金额，按金额降序排列`

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 👥 开发者

- 邮箱: lizhenping18@mails.ucas.ac.cn