# SemanticSQL Agent V2

基于 trae_agent 设计优化的自然语言到 SQL 查询智能体。

## 主要优化

1. **模块化设计**：采用 trae_agent 的模块化架构，工具通过注册表管理
2. **配置管理**：支持层级化配置，兼容旧版本配置格式
3. **CLI 增强**：提供丰富的命令行功能，支持交互式和批处理模式
4. **工具注册表**：所有工具通过统一的注册表管理，易于扩展

## 安装

```bash
# 克隆仓库
git clone <repository-url>
cd semanticsql-agent

# 安装依赖
pip install -r requirements.txt
```

## 配置

配置文件支持 YAML 和 JSON 格式，推荐使用 YAML。

### 新版配置格式（推荐）

```yaml
agent:
  # 模型配置
  model:
    model: "Qwen/Qwen2.5-32B-Instruct"
    base_url: "http://localhost:8000/v1"
    api_key: "your-api-key"
    temperature: 0.1
    max_tokens: 2000
  
  # 数据库配置
  database:
    type: "mysql"
    host: "localhost"
    port: 3306
    database: "your_database"
    username: "your_username"
    password: "your_password"
  
  # 工具配置
  tools:
    - "schema_extraction"
    - "domain_analysis"
    - "sql_generation"
    - "sql_validation"
    - "sql_execution"
```

## 使用方法

### 1. 命令行查询

```bash
# 基本查询
python cli_v2.py query "查询所有订单的总金额"

# 指定配置文件
python cli_v2.py query "查询最近一个月的销售数据" --config examples/config.yaml

# 只生成 SQL，不执行
python cli_v2.py query "查询用户表结构" --no-execute

# 输出为 JSON 格式
python cli_v2.py query "统计每个产品的销售量" --format json --output result.json

# 从文件读取查询
python cli_v2.py query --file query.txt

# 详细输出模式
python cli_v2.py query "复杂查询" --verbose
```

### 2. 交互式模式

```bash
# 启动交互式模式
python cli_v2.py interactive

# 使用指定配置
python cli_v2.py interactive --config examples/config_postgres.yaml

# 单行输入模式
python cli_v2.py interactive --mode single
```

### 3. 验证配置

```bash
# 验证配置文件
python cli_v2.py validate --config examples/config.yaml
```

### 4. 查看可用工具

```bash
# 列出所有可用工具
python cli_v2.py list-tools
```

### 5. Python API 使用

```python
from agent.sql_agent_v2 import SQLAgentV2
from utils.config import Config

# 加载配置
config = Config.from_yaml("config.yaml")
sql_config = config.to_sql_agent_config()

# 创建智能体
agent = SQLAgentV2(sql_config)

# 执行查询
result = agent.query("查询所有客户的订单统计")

# 处理结果
if result.success:
    print(f"SQL: {result.sql}")
    print(f"回答: {result.answer}")
else:
    print(f"错误: {result.error}")
```

## 工具说明

### 核心工具

- **schema_extraction**: 提取数据库结构信息
- **domain_analysis**: 分析业务领域和语义
- **field_classification**: 对表字段进行分类
- **er_analysis**: 分析实体关系
- **sql_generation**: 生成 SQL 查询
- **sql_validation**: 验证 SQL 语法
- **sql_execution**: 执行 SQL 查询
- **sequential_thinking**: 深度思考和推理

### 自定义工具

可以通过继承 `Tool` 基类并注册到 `tools_registry` 来添加新工具：

```python
from tools.base import Tool
from tools import tools_registry

class MyCustomTool(Tool):
    name = "my_custom_tool"
    description = "我的自定义工具"
    
    def execute(self, **kwargs):
        # 实现工具逻辑
        pass

# 注册工具
tools_registry["my_custom_tool"] = MyCustomTool
```

## 环境变量

支持通过环境变量配置敏感信息：

```bash
export LLM_API_KEY="your-api-key"
export DB_PASSWORD="your-db-password"
```

在配置文件中使用：

```yaml
model:
  api_key: "${LLM_API_KEY}"

database:
  password: "${DB_PASSWORD}"
```

## 高级功能

### 查询缓存

启用查询缓存可以提高重复查询的性能：

```yaml
agent:
  enable_query_cache: true
  cache_ttl: 3600  # 缓存时间（秒）
```

### 自定义提示模板

可以通过修改提示模板来定制智能体行为。提示模板位于 `prompts/` 目录。

### 轨迹记录

启用轨迹记录可以保存查询执行过程：

```yaml
agent:
  save_trajectory: true
```

## 故障排除

1. **数据库连接失败**：检查数据库配置和网络连接
2. **LLM API 错误**：验证 API key 和 endpoint
3. **工具执行失败**：查看详细日志，使用 `--verbose` 选项

## 性能优化建议

1. 合理配置 `max_steps` 避免过多迭代
2. 精简工具列表，只启用需要的工具
3. 使用查询缓存避免重复计算
4. 调整模型温度参数获得更稳定的结果

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License