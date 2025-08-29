# SemanticSQL Agent 实现指南

## 1. 快速开始

### 1.1 环境准备

#### 基本要求
- Python 3.8+
- 支持的数据库之一（MySQL、PostgreSQL、SQLite）
- Qwen 模型服务（本地或远程）

#### 安装步骤
```bash
# 1. 克隆项目
git clone <repository-url>
cd semanticsql-agent

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -r requirements.txt
```

### 1.2 配置 Qwen 模型

#### 本地部署 Qwen
```bash
# 使用 vLLM 或其他推理框架部署 Qwen
# 示例：使用 vLLM
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen3-14B \
    --port 9009 \
    --api-key not-needed
```

#### 配置文件设置
```yaml
# configs/config.yaml
llm:
  model: "Qwen3-14B"
  base_url: "http://localhost:9009/v1"  # OpenAI 兼容端点
  api_key: "not-needed"  # 本地部署通常不需要
  temperature: 0.1  # 降低随机性，提高 SQL 准确性
  max_tokens: 2000
```

### 1.3 数据库配置

#### MySQL 配置示例
```yaml
database:
  type: "mysql"
  host: "localhost"
  port: 3306
  database: "testdb"
  username: "root"
  password: "password"
```

#### 快速初始化
```bash
# 生成配置文件
python main.py init \
    --database-type mysql \
    --host localhost \
    --port 3306 \
    --database testdb \
    --username root \
    --password password \
    --model Qwen3-14B \
    --base-url http://localhost:9009/v1

# 测试连接
python main.py test

# 查看数据库结构
python main.py schema
```

## 2. 基本使用

### 2.1 命令行模式

#### 单次查询
```bash
# 基本查询
python main.py run "查询所有用户的数量"

# 带详细输出
python main.py run "统计每个部门的员工数" --verbose

# 指定配置文件
python main.py run "查找工资最高的10个员工" --config my_config.yaml
```

#### 交互模式
```bash
# 启动交互模式
python main.py interactive

# 交互示例
SemanticSQL> 查询所有订单的总金额
正在分析您的查询...
生成的SQL: SELECT SUM(amount) as total_amount FROM orders
执行结果:
┌──────────────┐
│ total_amount │
├──────────────┤
│   1234567.89 │
└──────────────┘

SemanticSQL> 统计每个月的销售额
...

SemanticSQL> exit
再见！
```

### 2.2 Python API 使用

#### 基础示例
```python
from agent.smart_sql_agent import SmartSQLAgent
from config.trae_config import TraeConfig

# 加载配置
config = TraeConfig.from_yaml("configs/config.yaml")

# 创建 Agent
agent = SmartSQLAgent(config)

# 执行查询
result = agent.query("查询最近7天的订单数量")

# 处理结果
if result.success:
    print(f"SQL: {result.sql}")
    print(f"结果: {result.data}")
else:
    print(f"查询失败: {result.error}")
```

#### 批量查询
```python
queries = [
    "统计每个产品类别的销售额",
    "查找库存不足的商品",
    "计算本月的营收增长率"
]

for query in queries:
    result = agent.query(query)
    print(f"\n查询: {query}")
    print(f"SQL: {result.sql}")
    print(f"行数: {result.row_count}")
```

## 3. 工具开发

### 3.1 创建自定义工具

#### 工具模板
```python
from tools.trae_base_tool import TraeBaseTool, ToolParameter
from typing import List, Dict, Any

class DataAnalysisTool(TraeBaseTool):
    """数据分析工具"""
    
    def __init__(self, database_manager):
        super().__init__(
            name="analyze_data",
            description="对查询结果进行统计分析"
        )
        self.db_manager = database_manager
    
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="sql",
                type="string",
                description="要分析的SQL查询",
                required=True
            ),
            ToolParameter(
                name="analysis_type",
                type="string",
                description="分析类型：summary/trend/distribution",
                required=False
            )
        ]
    
    def run(self, **kwargs) -> Dict[str, Any]:
        sql = kwargs.get("sql")
        analysis_type = kwargs.get("analysis_type", "summary")
        
        try:
            # 执行查询
            results = self.db_manager.execute_query(sql)
            
            # 执行分析
            if analysis_type == "summary":
                analysis = self._summary_analysis(results)
            elif analysis_type == "trend":
                analysis = self._trend_analysis(results)
            else:
                analysis = self._distribution_analysis(results)
            
            return {
                "success": True,
                "analysis": analysis,
                "row_count": len(results)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
```

#### 注册工具
```python
# 在 tools/__init__.py 中添加
from .data_analysis_tool import DataAnalysisTool

# 注册到可用工具列表
AVAILABLE_TOOLS = [
    # ... 现有工具
    DataAnalysisTool,
]
```

### 3.2 实现 Function Calling 工具

#### 工具定义
```python
def get_function_definition(self) -> Dict[str, Any]:
    """获取 OpenAI Function Calling 格式的工具定义"""
    return {
        "type": "function",
        "function": {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    param.name: {
                        "type": param.type,
                        "description": param.description
                    }
                    for param in self.get_parameters()
                },
                "required": [
                    param.name 
                    for param in self.get_parameters() 
                    if param.required
                ]
            }
        }
    }
```

#### 在 Agent 中使用
```python
class SmartSQLAgent(BaseAgent):
    
    def _call_llm_with_tools(self, messages: List[Dict]) -> Any:
        """调用 LLM 并处理 Function Calling"""
        
        # 获取所有工具定义
        tools = [tool.get_function_definition() for tool in self.tools]
        
        # 调用 LLM
        response = self.llm_client.chat.completions.create(
            model=self.config.llm.model,
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )
        
        # 处理响应
        message = response.choices[0].message
        
        if message.tool_calls:
            # 执行工具调用
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                
                # 执行工具
                result = self._execute_tool(tool_name, tool_args)
                
                # 将结果添加到消息历史
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result)
                })
        
        return response
```

## 4. 高级功能

### 4.1 提示词优化

#### 系统提示词模板
```python
SYSTEM_PROMPT = """你是一个专业的数据库查询助手，精通 SQL 语言。

数据库类型：{database_type}
可用的表：
{table_schemas}

你的任务：
1. 理解用户的中文查询需求
2. 生成准确的 SQL 语句
3. 只生成 SELECT 查询，不允许修改数据
4. 考虑查询性能，必要时添加 LIMIT

回答格式要求：
- 使用 Thought/Action/Observation 格式
- SQL 语句要格式化，便于阅读
- 解释查询逻辑
"""

def build_system_prompt(self, database_info: Dict) -> str:
    """构建系统提示词"""
    table_schemas = self._format_table_schemas(database_info)
    
    return SYSTEM_PROMPT.format(
        database_type=self.config.database.type,
        table_schemas=table_schemas
    )
```

#### Few-shot 示例
```python
FEW_SHOT_EXAMPLES = [
    {
        "question": "查询所有用户的数量",
        "thought": "需要统计 users 表的总行数",
        "sql": "SELECT COUNT(*) as user_count FROM users",
    },
    {
        "question": "查找最近7天注册的用户",
        "thought": "需要使用 created_at 字段筛选最近7天的记录",
        "sql": """
        SELECT * FROM users 
        WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
        ORDER BY created_at DESC
        """
    }
]
```

### 4.2 查询优化

#### SQL 优化建议
```python
class QueryOptimizer:
    """查询优化器"""
    
    def optimize_query(self, sql: str, schema: Dict) -> Dict[str, Any]:
        """分析并优化 SQL 查询"""
        suggestions = []
        
        # 检查是否有 LIMIT
        if "limit" not in sql.lower() and "count" not in sql.lower():
            suggestions.append("建议添加 LIMIT 限制结果集大小")
        
        # 检查是否使用索引
        tables_used = self._extract_tables(sql)
        for table in tables_used:
            indexed_columns = schema.get(table, {}).get("indexes", [])
            where_columns = self._extract_where_columns(sql)
            
            missing_indexes = set(where_columns) - set(indexed_columns)
            if missing_indexes:
                suggestions.append(
                    f"表 {table} 的列 {missing_indexes} 可能需要索引"
                )
        
        return {
            "original_sql": sql,
            "suggestions": suggestions,
            "optimized": len(suggestions) == 0
        }
```

### 4.3 结果后处理

#### 数据格式化
```python
def format_result(self, data: List[Dict], format_type: str = "table") -> str:
    """格式化查询结果"""
    
    if format_type == "table":
        # 表格格式
        from tabulate import tabulate
        if not data:
            return "查询结果为空"
        headers = list(data[0].keys())
        rows = [list(row.values()) for row in data]
        return tabulate(rows, headers=headers, tablefmt="grid")
        
    elif format_type == "json":
        # JSON 格式
        return json.dumps(data, ensure_ascii=False, indent=2)
        
    elif format_type == "csv":
        # CSV 格式
        import csv
        import io
        output = io.StringIO()
        if data:
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        return output.getvalue()
```

## 5. 配置详解

### 5.1 完整配置示例
```yaml
# configs/production.yaml
app:
  name: "SemanticSQL Agent"
  version: "2.0.0"
  environment: "production"
  debug: false

database:
  type: "mysql"
  host: "${DB_HOST}"  # 支持环境变量
  port: ${DB_PORT:3306}  # 支持默认值
  database: "${DB_NAME}"
  username: "${DB_USER}"
  password: "${DB_PASSWORD}"
  # 连接池设置
  pool_size: 5
  max_overflow: 10
  pool_timeout: 30
  echo: false  # 不打印 SQL 语句

llm:
  model: "Qwen3-14B"
  base_url: "${LLM_BASE_URL:http://localhost:9009/v1}"
  api_key: "${LLM_API_KEY:not-needed}"
  temperature: 0.1  # 低温度for更确定的输出
  max_tokens: 2000
  timeout: 30
  # Function Calling 设置
  tools_enabled: true
  tool_choice: "auto"  # auto/none/required

agent:
  max_steps: 10  # ReAct 最大步数
  enable_thinking: true  # 显示思考过程
  enable_reflection: false  # 关闭反思步骤
  tools:
    - connect_database
    - analyze_schema
    - generate_sql
    - execute_sql
```

### 5.2 环境变量配置
```bash
# .env 文件
# 数据库配置
DB_HOST=localhost
DB_PORT=3306
DB_NAME=production_db
DB_USER=app_user
DB_PASSWORD=secure_password

# LLM 配置
LLM_BASE_URL=http://gpu-server:9009/v1
LLM_API_KEY=your-api-key
LLM_MODEL=Qwen3-14B

# 应用配置
LOG_LEVEL=INFO
MAX_QUERY_ROWS=1000
CACHE_TTL=3600
```

## 6. 部署建议

### 6.1 生产环境部署

#### Docker 部署
```dockerfile
# Dockerfile
FROM python:3.8-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 复制并安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 非 root 用户运行
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# 启动命令
CMD ["python", "main.py", "interactive"]
```

#### Docker Compose
```yaml
version: '3.8'

services:
  semanticsql:
    build: .
    environment:
      - DB_HOST=mysql
      - DB_PORT=3306
      - DB_NAME=semanticsql
      - DB_USER=root
      - DB_PASSWORD=password
      - LLM_BASE_URL=http://llm-server:9009/v1
    depends_on:
      - mysql
    volumes:
      - ./configs:/app/configs
      - ./logs:/app/logs
    restart: unless-stopped

  mysql:
    image: mysql:8.0
    environment:
      - MYSQL_ROOT_PASSWORD=password
      - MYSQL_DATABASE=semanticsql
    volumes:
      - mysql_data:/var/lib/mysql
    ports:
      - "3306:3306"

volumes:
  mysql_data:
```

### 6.2 性能优化

#### 缓存配置
```python
# utils/cache.py
from functools import lru_cache
import hashlib

class QueryCache:
    """查询缓存"""
    
    def __init__(self, max_size=100, ttl=3600):
        self.cache = {}
        self.max_size = max_size
        self.ttl = ttl
    
    def get_cache_key(self, question: str, schema_hash: str) -> str:
        """生成缓存键"""
        content = f"{question}:{schema_hash}"
        return hashlib.md5(content.encode()).hexdigest()
    
    @lru_cache(maxsize=128)
    def get_cached_sql(self, question: str) -> Optional[str]:
        """获取缓存的 SQL"""
        # 实现缓存逻辑
        pass
```

## 7. 故障排查

### 7.1 常见问题

#### 连接问题
```bash
# 测试数据库连接
python main.py test --verbose

# 常见错误：
# - Access denied: 检查用户名密码
# - Unknown database: 确认数据库存在
# - Connection refused: 检查主机和端口
```

#### LLM 调用问题
```python
# 测试 LLM 连接
import openai

client = openai.OpenAI(
    base_url="http://localhost:9009/v1",
    api_key="not-needed"
)

response = client.chat.completions.create(
    model="Qwen3-14B",
    messages=[{"role": "user", "content": "Hello"}]
)
print(response)
```

### 7.2 调试技巧

#### 启用详细日志
```bash
# 设置日志级别
export LOG_LEVEL=DEBUG

# 或在代码中
import logging
logging.basicConfig(level=logging.DEBUG)
```

#### SQL 调试
```python
# 在配置中启用 SQL 日志
database:
  echo: true  # 打印所有 SQL 语句
```

## 8. 最佳实践

### 8.1 查询编写
- 使用清晰、具体的中文描述
- 指明时间范围（如"最近7天"）
- 说明排序和限制需求
- 避免歧义表达

### 8.2 性能建议
- 为常用查询字段建立索引
- 使用连接池管理数据库连接
- 合理设置查询结果限制
- 定期清理缓存

### 8.3 安全建议
- 只授予 SELECT 权限
- 使用独立的查询账号
- 定期审计查询日志
- 限制敏感表访问