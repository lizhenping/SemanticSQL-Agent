# SemanticSQL Agent

基于LangChain的智能SQL训练数据生成系统。通过ReAct模式，Agent自主分析数据库、生成问题、创建SQL、执行验证并反思优化。

## 核心特性

- 🧠 **智能数据库分析**：自动提取和理解数据库结构、业务领域、表关系
- 🔄 **Memory链机制**：每个分析步骤的结果保存在memory中，后续步骤自动使用
- 🎯 **场景化生成**：基于预定义场景模板生成多样化的问题和SQL
- ✅ **自动验证**：执行SQL验证正确性，通过反思机制优化质量
- 📦 **标准化输出**：生成符合训练标准的JSON/JSONL格式数据集

## 系统架构

```
├── agent/              # 智能体核心
│   ├── base_agent.py   # 基础Agent，管理工具和memory
│   └── sql_agent.py    # SQL生成Agent
├── tools/              # 工具集
│   ├── analysis_tools/ # 分析工具（按执行顺序）
│   │   ├── schema_extraction_tool.py    # 1. 提取数据库结构
│   │   ├── domain_analysis_tool.py      # 2. 分析业务领域
│   │   ├── field_classification_tool.py # 3. 字段分类
│   │   ├── column_meaning_tool.py       # 4. 列含义分析
│   │   ├── table_meaning_tool.py        # 5. 表含义分析
│   │   └── er_analysis_tool.py          # 6. 关系分析
│   ├── generation_tools/    # 生成工具
│   ├── validation_tools/    # 验证工具
│   ├── reflection_tools/    # 反思工具
│   └── thinking_tools/      # 思考工具
├── prompts/            # 提示词管理
│   └── templates/      # Jinja2模板
├── utils/              # 工具类
│   ├── memory.py       # Memory管理
│   └── database.py     # 数据库连接
└── config/             # 配置管理
```

## Memory Chain

每个工具执行后将结果保存到memory，后续工具可以访问：

```
schema_extraction → memory["schema_info"]
        ↓
domain_analysis → memory["domain_info"]
        ↓
field_classification → memory["field_classification"]
        ↓
column_meaning → memory["column_meanings"]
        ↓
table_meaning → memory["table_meanings"]
        ↓
er_analysis → memory["er_relations"]
```

## 快速开始

### 1. 环境准备
```bash
pip install -r requirements.txt
```

### 2. 配置数据库
```bash
cp config/.env.example config/.env
# 编辑 .env 文件，设置数据库连接信息
```

### 3. 生成训练数据
```bash
# 生成50条训练数据
python cli.py generate -n 50 -o training_data.jsonl

# 指定数据库
python cli.py generate -n 100 -d mydb -o output.json
```

## 文档

- [架构设计](.doc/semanticsql-agent_ARCHITECTURE.md) - 详细的系统架构说明
- [设计规范](.doc/semanticsql-agent_DESIGN_SPEC.md) - 设计原则和规范
- [命令行指令](.doc/命令行指令.md) - CLI使用说明

## 许可证

MIT License