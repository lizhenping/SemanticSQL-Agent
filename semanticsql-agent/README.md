# SemanticSQL Agent 🤖

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

专注MySQL的智能NL2SQL查询系统，基于ReAct（Reasoning + Acting）模式，将自然语言转换为SQL查询并执行。

## ✨ 特性

- 🧠 **智能体驱动**：基于 ReAct 模式的自主推理和执行
- 🔧 **标准化工具系统**：结构分析、SQL生成、验证执行、反思优化
- 📊 **完整执行追踪**：详细记录推理过程，支持调试分析
- 🎯 **MySQL专用优化**：针对MySQL数据库优化的连接和查询处理
- 🔄 **自动验证**：SQL语法检查、安全性验证、执行测试
- 🤖 **本地LLM集成**：支持本地部署的Qwen等大模型

## 🚀 快速开始

### 环境准备

```bash
# 激活conda环境
source activate alphasql

# 进入项目目录
cd /root/autodl-tmp/nl2sql/NL2SQL/trae-agent/semanticsql-agent

# 安装依赖
pip install pydantic sqlalchemy openai pymysql
```

### 基础使用

```bash
# 1. 测试MySQL数据库连接
python main.py test

# 2. 查看数据库结构
python main.py schema

# 3. 运行自然语言查询
python main.py run "查询aid_info表的记录数量"

# 4. 交互模式
python main.py interactive
```

## 📋 命令参考

### 核心功能命令

#### 数据库测试
```bash
# 测试MySQL连接
python main.py test

# 显示数据库信息
python main.py schema
```

#### 查询执行
```bash
# 基础查询
python main.py run "查询用户数量"

# 复杂查询
python main.py run "查询每个类别的平均金额"

# 带超时的查询
timeout 30 python main.py run "统计所有表的记录数"
```

#### 交互模式
```bash
# 进入交互式查询模式
python main.py interactive
```

## 🔧 配置说明

### 默认配置
系统使用内置默认配置，专门为您的MySQL环境优化：

```python
# MySQL数据库配置
host: "192.168.200.216"
port: 13306
database: "testdb"
username: "testuser"
password: "testpass"

# LLM配置（需要您提供正确的模型名称）
model: "Qwen3-14B"  # 请根据您的实际模型名称调整
base_url: "http://127.0.0.1:9991/v1"
api_key: "not-needed"
```

### 环境变量配置（可选）
```bash
export LLM_MODEL="您的模型名称"
export DB_HOST="192.168.200.216"
export DB_PORT="13306"
export DB_NAME="testdb"
export DB_USER="testuser"
export DB_PASSWORD="testpass"
```

## 📁 项目结构

```
semanticsql-agent/
├── agent/              # ReAct智能体实现
│   ├── base_agent.py   # 基础智能体类
│   └── smart_sql_agent.py # SQL智能体
├── config/             # 配置系统
│   ├── settings.py     # 全局设置
│   └── database.py     # MySQL数据库配置
├── tools/              # 标准化工具系统
│   ├── analysis_tools/ # 数据库结构分析
│   ├── generation_tools/ # SQL生成
│   ├── validation_tools/ # SQL验证执行
│   ├── reflection_tools/ # 结果反思
│   └── thinking_tools/ # 推理思考
├── models/             # 数据模型
│   ├── schemas.py      # Pydantic数据模型
│   └── exceptions.py   # 异常定义
├── utils/              # 工具函数
│   └── database.py     # 数据库管理器
├── tests/              # 单元测试
├── main.py             # 主入口程序
└── simple_test.py      # 简单功能测试
```

## 🔧 架构设计

### ReAct 执行模式
```
观察(Observation) → 思考(Thought) → 行动(Action) → 观察(Observation)
```

### MySQL查询流程
```
1. 提取数据库结构 → MySQL表和字段信息
2. 生成SQL查询 → 基于自然语言生成SQL
3. 验证SQL语法 → 语法检查和安全验证
4. 执行查询 → 安全执行并返回结果
5. 反思优化 → 分析结果质量并提供建议
```

## 📊 查询结果示例

```json
{
  "success": true,
  "question": "查询aid_info表的记录数量",
  "sql": "SELECT COUNT(*) as count FROM aid_info;",
  "answer": "共有1250条记录",
  "data": [{"count": 1250}],
  "execution_time": 0.05,
  "steps": 4
}
```

## ⚠️ 常见问题

### LLM模型名称错误
```bash
# 问题：模型不存在错误
# 解决：请告知正确的模型名称，我会更新config/settings.py中的llm_model配置
```

### 数据库连接问题
```bash
# 测试连接
python main.py test
```

## 🚀 快速验证

```bash
# 完整功能验证
source activate alphasql && \
python main.py test && \
python main.py schema && \
python main.py run "查询aid_info表的记录数量"
```

---

## 💡 使用提示

1. **模型配置**: 请根据您的本地模型服务提供正确的模型名称
2. **MySQL专用**: 系统已针对MySQL数据库优化，包括字符集和连接配置
3. **安全查询**: 系统只允许SELECT查询，确保数据库安全
4. **本地服务**: LLM API已配置为本地127.0.0.1调用

## 📝 更新日志

**v2.0.0 (当前版本)**
- ✅ 重构为MySQL专用架构
- ✅ 简化配置系统（Pydantic）
- ✅ 标准化工具接口
- ✅ ReAct模式智能体
- ✅ 完整单元测试覆盖

---

本项目专注于MySQL环境的NL2SQL查询功能，基于ReAct智能体架构实现。