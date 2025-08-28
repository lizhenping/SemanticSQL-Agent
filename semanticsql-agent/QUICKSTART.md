# SemanticSQL Agent V2 快速开始指南

## 1. 快速安装

```bash
# 进入项目目录
cd semanticsql-agent

# 安装依赖
pip install -r requirements.txt
```

## 2. 配置数据库

编辑 `examples/config.yaml` 文件，修改数据库连接信息：

```yaml
agent:
  database:
    type: "mysql"          # 或 "postgresql"
    host: "localhost"      # 你的数据库主机
    port: 3306            # 你的数据库端口
    database: "your_db"   # 你的数据库名
    username: "your_user" # 你的用户名
    password: "your_pass" # 你的密码
```

## 3. 运行命令

### 方式一：使用 Shell 脚本（推荐）

```bash
# 查看帮助
./run_agent.sh

# 执行查询
./run_agent.sh query "查询所有表的结构"

# 进入交互模式
./run_agent.sh interactive

# 验证配置
./run_agent.sh validate
```

### 方式二：使用 Python 脚本

```bash
# 查看帮助
python run_agent.py --help

# 执行查询
python run_agent.py query "查询所有用户"

# 使用自定义配置
python run_agent.py query "统计订单数量" --config myconfig.yaml

# 只生成 SQL 不执行
python run_agent.py query "查询产品信息" --no-execute

# 输出为 JSON
python run_agent.py query "查询销售数据" --format json --output result.json
```

### 方式三：直接运行 CLI

```bash
# 进入项目目录后
python cli_v2.py query "你的查询"
```

## 4. 示例查询

以下是一些常见的查询示例：

```bash
# 数据库结构查询
./run_agent.sh query "显示所有表的结构"
./run_agent.sh query "查询用户表有哪些字段"

# 数据统计查询
./run_agent.sh query "统计每个表的记录数"
./run_agent.sh query "计算订单总金额"
./run_agent.sh query "查询最近30天的新增用户数"

# 复杂查询
./run_agent.sh query "找出购买次数最多的前10个客户"
./run_agent.sh query "统计每个产品类别的月度销售趋势"
```

## 5. 交互模式使用

```bash
# 启动交互模式
./run_agent.sh interactive

# 在交互模式中：
# - 直接输入查询，按 Enter 执行
# - 输入 'help' 查看帮助
# - 输入 'exit' 或 'quit' 退出
```

## 6. 高级配置

### 使用环境变量

创建 `.env` 文件：

```bash
LLM_API_KEY=your-api-key
DB_PASSWORD=your-password
```

### 自定义工具集

在配置文件中指定要使用的工具：

```yaml
agent:
  tools:
    - "schema_extraction"    # 必需：提取数据库结构
    - "sql_generation"       # 必需：生成 SQL
    - "sql_validation"       # 可选：验证 SQL
    - "sql_execution"        # 可选：执行 SQL
```

## 7. 常见问题

**Q: 如何只生成 SQL 而不执行？**
A: 使用 `--no-execute` 参数，或在配置中移除 `sql_execution` 工具。

**Q: 如何查看详细的执行过程？**
A: 使用 `--verbose` 或 `-v` 参数。

**Q: 支持哪些数据库？**
A: 目前支持 MySQL 和 PostgreSQL。

**Q: 如何自定义 LLM 模型？**
A: 在配置文件中修改 `model` 部分，支持 OpenAI、Anthropic、Google 等。

## 8. 下一步

- 查看完整文档：`README_V2.md`
- 查看配置示例：`examples/` 目录
- 运行测试脚本：`python examples/test_queries.py`