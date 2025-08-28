# SemanticSQL Agent CLI 使用指南

## 🚀 快速开始

SemanticSQL Agent 提供了一个简单易用的命令行工具，可以将自然语言查询转换为 SQL。

### 安装依赖（可选）

```bash
# 基础运行不需要任何依赖
# 如需完整功能，安装：
pip install click pyyaml rich openai pymysql
```

### 基础使用

```bash
# 1. 查看帮助
python3 run_semanticsql.py

# 2. 执行查询
python3 run_semanticsql.py query "查询用户总数"

# 3. 生成配置
python3 run_semanticsql.py config generate --output config.yaml

# 4. 测试系统
python3 run_semanticsql.py test
```

## 📋 可用命令

### 1. query - 执行自然语言查询

将自然语言转换为 SQL 查询。

```bash
# 基本用法
python3 run_semanticsql.py query "查询销售额最高的10个产品"

# 使用详细模式
python3 run_semanticsql.py query "统计每月用户增长" --verbose

# 使用自定义配置
python3 run_semanticsql.py query "分析产品销售" --config myconfig.yaml
```

**支持的查询模式：**
- 销售相关：`销售额最高的产品`、`今年的销售总额`
- 用户相关：`用户总数`、`每月用户增长`、`最活跃的用户`
- 产品相关：`产品类别销售分布`

### 2. config generate - 生成配置模板

生成配置文件模板。

```bash
# 生成 YAML 格式（默认）
python3 run_semanticsql.py config generate

# 生成并保存到文件
python3 run_semanticsql.py config generate --output config.yaml

# 生成 JSON 格式
python3 run_semanticsql.py config generate --format json --output config.json
```

### 3. test - 测试系统

检查系统状态和配置。

```bash
# 使用默认配置测试
python3 run_semanticsql.py test

# 使用指定配置测试
python3 run_semanticsql.py test --config myconfig.yaml
```

### 4. examples - 显示使用示例

```bash
python3 run_semanticsql.py examples
```

### 5. version - 显示版本

```bash
python3 run_semanticsql.py version
```

## ⚙️ 配置文件

### YAML 格式 (config.yaml)

```yaml
# LLM 配置
llm:
  model: "Qwen3-14B"
  base_url: "http://192.168.200.216:9009/v1"
  temperature: 0.1
  max_tokens: 2000

# 数据库配置
database:
  type: "mysql"
  host: "localhost"
  port: 3306
  user: "root"
  password: "your_password"
  database: "your_database"

# 智能体配置
agent:
  max_steps: 10
  enable_thinking: true
  verbose: false
```

### JSON 格式 (config.json)

```json
{
  "llm": {
    "model": "Qwen3-14B",
    "base_url": "http://192.168.200.216:9009/v1",
    "temperature": 0.1,
    "max_tokens": 2000
  },
  "database": {
    "type": "mysql",
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "your_password",
    "database": "your_database"
  },
  "agent": {
    "max_steps": 10,
    "enable_thinking": true,
    "verbose": false
  }
}
```

## 💡 使用技巧

### 1. 批量查询

创建查询文件 `queries.txt`：
```
查询用户总数
统计今年的销售额
找出最活跃的10个用户
```

然后使用脚本批量执行：
```bash
while IFS= read -r query; do
    echo "执行: $query"
    python3 run_semanticsql.py query "$query"
    echo ""
done < queries.txt
```

### 2. 保存查询结果

```bash
# 重定向输出到文件
python3 run_semanticsql.py query "查询销售数据" > result.sql

# 追加到日志文件
python3 run_semanticsql.py query "用户分析" >> queries.log
```

### 3. 使用别名简化命令

在 `.bashrc` 或 `.zshrc` 中添加：
```bash
alias sql="python3 /path/to/run_semanticsql.py query"
```

然后可以直接使用：
```bash
sql "查询用户总数"
```

## 🔧 高级用法

### 使用完整版 CLI（需要依赖）

如果安装了必要的依赖，可以使用功能更丰富的 `cli.py`：

```bash
# 安装依赖
pip install -r requirements.txt

# 使用 Click CLI
python3 cli.py query "查询销售数据" --rich

# 使用工作版
python3 cli_working.py query "分析用户行为" --verbose
```

### 集成到其他项目

```python
# 导入并使用
from run_semanticsql import execute_query, load_config

config = load_config("config.yaml")
execute_query("查询今年销售额", config, verbose=True)
```

## ❓ 常见问题

### 1. 配置文件找不到
- 使用 `python3 run_semanticsql.py config generate` 生成默认配置
- 或者程序会自动使用内置的默认配置

### 2. 查询没有匹配到模板
- 检查查询是否包含关键词（如"销售"、"用户"、"产品"）
- 使用 `--verbose` 查看详细信息
- 生成的 SQL 会包含 TODO 注释，需要手动调整

### 3. 需要连接真实数据库
- 当前版本是模拟模式，不会真正连接数据库
- 如需真实执行，请使用完整版并配置正确的数据库连接

## 📝 示例查询

```bash
# 销售分析
python3 run_semanticsql.py query "查询本月销售额最高的10个产品"
python3 run_semanticsql.py query "统计各产品类别的销售占比"

# 用户分析
python3 run_semanticsql.py query "查询最近30天活跃用户数"
python3 run_semanticsql.py query "分析用户注册增长趋势"

# 业务指标
python3 run_semanticsql.py query "计算平均订单金额"
python3 run_semanticsql.py query "查找复购率最高的客户"
```

## 🎯 最佳实践

1. **清晰的查询描述**：使用明确的动词（查询、统计、分析、计算）
2. **指定时间范围**：如"本月"、"今年"、"最近30天"
3. **明确数量限制**：如"前10个"、"最高的5个"
4. **使用业务术语**：系统会识别"销售额"、"活跃用户"等常见术语

---

现在您可以开始使用 SemanticSQL Agent 了！🚀