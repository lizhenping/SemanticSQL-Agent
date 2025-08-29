# SemanticSQL Agent 实现指南

## 1. 快速开始

### 1.1 环境准备

#### 系统要求
- Python 3.8 或更高版本
- 支持的操作系统：Linux、macOS、Windows
- 至少 4GB 内存
- 网络连接（用于 LLM API 调用）

#### 安装依赖
```bash
# 激活 conda 环境
source activate alphasql

# 安装核心依赖
pip install click pyyaml sqlalchemy openai
pip install aiomysql aiosqlite asyncpg  # 异步数据库驱动
pip install rich tabulate  # CLI 美化输出
```

### 1.2 配置初始化

#### 生成配置文件
```bash
# 使用命令行初始化配置
python main.py init \
    --database-type mysql \
    --host 192.168.200.216 \
    --port 13306 \
    --database testdb \
    --user testuser \
    --password testpass \
    --model Qwen3-14B \
    --base-url http://192.168.200.216:9009/v1 \
    --api-key not-needed
```

#### 配置文件结构 (trae_config.yaml)
```yaml
app:
  name: "SemanticSQL Agent"
  version: "1.0.0"
  environment: "development"
  debug: false

database:
  type: "mysql"
  host: "192.168.200.216"
  port: 13306
  database: "testdb"
  username: "testuser"
  password: "testpass"
  connection_timeout: 30
  pool_size: 5
  max_overflow: 10
  echo: false  # 是否打印SQL语句

llm:
  model: "Qwen3-14B"
  base_url: "http://192.168.200.216:9009/v1"
  api_key: "not-needed"
  temperature: 0.1
  max_tokens: 20000
  timeout: 30
  retry_count: 3
  retry_delay: 1

agent:
  max_steps: 10
  thinking_mode: "sequential"
  enable_reflection: true
  verbose: false
```

### 1.3 基本使用

#### 测试数据库连接
```bash
python main.py test --config trae_config.yaml
```

#### 查看数据库结构
```bash
python main.py schema --config trae_config.yaml
```

#### 执行单次查询
```bash
python main.py run "查询所有用户的数量" --config trae_config.yaml --verbose
```

#### 交互模式
```bash
python main.py interactive --config trae_config.yaml
```

## 2. 核心组件实现

### 2.1 实现自定义 Agent

#### 基础 Agent 实现
```python
from agent.base_agent import BaseAgent, AgentExecution
from typing import List, Dict, Any

class MyCustomAgent(BaseAgent):
    """自定义 Agent 实现"""
    
    def __init__(self, config: TraeConfig):
        super().__init__(config)
        # 初始化自定义属性
        self.custom_tools = []
        
    def _init_tools(self) -> List[Any]:
        """初始化工具链"""
        tools = [
            SyncSchemaExtractionTool(self.database_manager),
            SyncSQLGenerationTool(self.llm_client),
            SyncSQLExecutionTool(self.database_manager),
            # 添加自定义工具
        ]
        return tools
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return """你是一个专业的数据库查询助手。
        使用 ReAct 模式处理用户请求：
        1. Thought: 分析用户需求
        2. Action: 调用合适的工具
        3. Observation: 观察工具结果
        4. 重复以上步骤直到完成任务
        """
    
    def execute_sync(self, task: str) -> AgentExecution:
        """同步执行任务"""
        execution = AgentExecution(task=task, steps=[])
        
        try:
            # 执行 ReAct 循环
            result = self._run_react_loop(task, execution)
            execution.final_result = result
            execution.success = True
        except Exception as e:
            execution.error = str(e)
            execution.success = False
            
        return execution
```

#### 高级 Agent 功能
```python
class SmartSQLAgent(BaseAgent):
    """智能 SQL Agent，支持多步推理"""
    
    def _should_continue(self, execution: AgentExecution) -> bool:
        """判断是否继续执行"""
        if len(execution.steps) >= self.config.agent.max_steps:
            return False
            
        # 检查是否已经得到满意的结果
        last_step = execution.steps[-1] if execution.steps else None
        if last_step and last_step.tool_name == "sql_execution":
            return False
            
        return True
    
    def _handle_error(self, error: Exception, execution: AgentExecution):
        """错误处理和恢复"""
        error_msg = str(error)
        
        if "syntax error" in error_msg.lower():
            # SQL 语法错误，尝试重新生成
            self._add_thought(execution, f"SQL语法错误，需要重新生成: {error_msg}")
            return self._regenerate_sql(execution)
        elif "connection" in error_msg.lower():
            # 连接错误，尝试重连
            self._reconnect_database()
            return self._retry_last_action(execution)
        else:
            # 其他错误，记录并结束
            execution.error = error_msg
            execution.success = False
```

### 2.2 实现自定义工具

#### 工具基类使用
```python
from tools.trae_base_tool import TraeBaseTool, ToolParameter
from typing import List, Any, Dict

class MyCustomTool(TraeBaseTool):
    """自定义工具实现"""
    
    def __init__(self):
        super().__init__(
            name="my_custom_tool",
            description="执行自定义操作的工具"
        )
        
    def get_parameters(self) -> List[ToolParameter]:
        """定义工具参数"""
        return [
            ToolParameter(
                name="input_text",
                type="string",
                description="输入文本",
                required=True
            ),
            ToolParameter(
                name="options",
                type="object",
                description="额外选项",
                required=False
            )
        ]
    
    def run(self, **kwargs) -> Dict[str, Any]:
        """执行工具逻辑"""
        input_text = kwargs.get("input_text")
        options = kwargs.get("options", {})
        
        try:
            # 执行自定义逻辑
            result = self._process_input(input_text, options)
            
            return {
                "success": True,
                "result": result,
                "metadata": {
                    "processed_at": datetime.now().isoformat(),
                    "input_length": len(input_text)
                }
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _process_input(self, text: str, options: Dict) -> Any:
        """处理输入的具体逻辑"""
        # 实现自定义处理逻辑
        pass
```

#### 数据库分析工具示例
```python
class DatabaseAnalysisTool(TraeBaseTool):
    """数据库深度分析工具"""
    
    def __init__(self, database_manager):
        super().__init__(
            name="database_analysis",
            description="分析数据库结构和数据分布"
        )
        self.db_manager = database_manager
        
    def run(self, **kwargs) -> Dict[str, Any]:
        """执行数据库分析"""
        analysis_type = kwargs.get("analysis_type", "basic")
        
        if analysis_type == "basic":
            return self._basic_analysis()
        elif analysis_type == "statistics":
            return self._statistical_analysis()
        elif analysis_type == "relationships":
            return self._relationship_analysis()
            
    def _basic_analysis(self) -> Dict[str, Any]:
        """基础分析：表数量、字段统计等"""
        with self.db_manager.get_connection() as conn:
            # 获取所有表
            tables = conn.execute("SHOW TABLES").fetchall()
            
            analysis = {
                "table_count": len(tables),
                "tables": []
            }
            
            for table in tables:
                table_name = table[0]
                # 获取表结构
                columns = conn.execute(f"DESCRIBE {table_name}").fetchall()
                
                analysis["tables"].append({
                    "name": table_name,
                    "column_count": len(columns),
                    "columns": [col[0] for col in columns]
                })
                
            return analysis
```

### 2.3 配置管理实现

#### 环境变量支持
```python
# config/trae_config.py 扩展

import os
from typing import Optional

class ConfigLoader:
    """配置加载器，支持多源配置"""
    
    @staticmethod
    def load_from_env() -> Dict[str, Any]:
        """从环境变量加载配置"""
        env_config = {}
        
        # LLM 配置
        if model := os.getenv("LLM_MODEL"):
            env_config.setdefault("llm", {})["model"] = model
        if base_url := os.getenv("LLM_BASE_URL"):
            env_config.setdefault("llm", {})["base_url"] = base_url
        if api_key := os.getenv("LLM_API_KEY"):
            env_config.setdefault("llm", {})["api_key"] = api_key
            
        # 数据库配置
        if db_type := os.getenv("DB_TYPE"):
            env_config.setdefault("database", {})["type"] = db_type
        if db_host := os.getenv("DB_HOST"):
            env_config.setdefault("database", {})["host"] = db_host
        if db_port := os.getenv("DB_PORT"):
            env_config.setdefault("database", {})["port"] = int(db_port)
            
        return env_config
    
    @staticmethod
    def merge_configs(*configs: Dict[str, Any]) -> Dict[str, Any]:
        """合并多个配置源"""
        result = {}
        for config in configs:
            result = deep_merge(result, config)
        return result
```

#### 配置验证
```python
from dataclasses import dataclass
from typing import Optional
import validators

@dataclass
class ConfigValidator:
    """配置验证器"""
    
    @staticmethod
    def validate_database_config(config: DatabaseConfig) -> List[str]:
        """验证数据库配置"""
        errors = []
        
        # 验证数据库类型
        if config.type not in ["mysql", "postgresql", "sqlite"]:
            errors.append(f"不支持的数据库类型: {config.type}")
            
        # 验证连接参数
        if config.type != "sqlite":
            if not config.host:
                errors.append("数据库主机地址不能为空")
            if not (1 <= config.port <= 65535):
                errors.append(f"无效的端口号: {config.port}")
                
        # 验证连接池参数
        if config.pool_size < 1:
            errors.append("连接池大小必须大于0")
            
        return errors
    
    @staticmethod
    def validate_llm_config(config: LLMConfig) -> List[str]:
        """验证 LLM 配置"""
        errors = []
        
        # 验证模型名称
        if not config.model:
            errors.append("模型名称不能为空")
            
        # 验证 API 地址
        if config.base_url and not validators.url(config.base_url):
            errors.append(f"无效的 API 地址: {config.base_url}")
            
        # 验证参数范围
        if not (0 <= config.temperature <= 2):
            errors.append(f"温度参数必须在 0-2 之间: {config.temperature}")
            
        return errors
```

## 3. 高级实现技巧

### 3.1 性能优化

#### 数据库查询优化
```python
class OptimizedSQLExecutor:
    """优化的 SQL 执行器"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.query_cache = {}  # 查询缓存
        
    def execute_with_cache(self, sql: str, cache_ttl: int = 300) -> Any:
        """带缓存的查询执行"""
        cache_key = hashlib.md5(sql.encode()).hexdigest()
        
        # 检查缓存
        if cache_key in self.query_cache:
            cached_result, timestamp = self.query_cache[cache_key]
            if time.time() - timestamp < cache_ttl:
                return cached_result
                
        # 执行查询
        result = self.db_manager.execute_query(sql)
        
        # 更新缓存
        self.query_cache[cache_key] = (result, time.time())
        
        return result
    
    def execute_batch(self, queries: List[str]) -> List[Any]:
        """批量执行查询"""
        results = []
        
        with self.db_manager.get_connection() as conn:
            for query in queries:
                try:
                    result = conn.execute(query).fetchall()
                    results.append({
                        "success": True,
                        "data": result
                    })
                except Exception as e:
                    results.append({
                        "success": False,
                        "error": str(e)
                    })
                    
        return results
```

#### LLM 调用优化
```python
class OptimizedLLMClient:
    """优化的 LLM 客户端"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.response_cache = {}
        self.token_usage = {"prompt": 0, "completion": 0}
        
    async def call_with_retry(self, messages: List[Dict], **kwargs) -> str:
        """带重试的 LLM 调用"""
        retry_count = kwargs.get("retry_count", 3)
        retry_delay = kwargs.get("retry_delay", 1)
        
        for attempt in range(retry_count):
            try:
                response = await self._call_llm(messages, **kwargs)
                self._update_token_usage(response)
                return response.content
                
            except Exception as e:
                if attempt < retry_count - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                else:
                    raise e
                    
    def get_token_usage_report(self) -> Dict[str, Any]:
        """获取 Token 使用报告"""
        total_tokens = self.token_usage["prompt"] + self.token_usage["completion"]
        
        return {
            "prompt_tokens": self.token_usage["prompt"],
            "completion_tokens": self.token_usage["completion"],
            "total_tokens": total_tokens,
            "estimated_cost": self._estimate_cost(total_tokens)
        }
```

### 3.2 错误处理最佳实践

#### 统一错误处理
```python
class ErrorHandler:
    """统一的错误处理器"""
    
    @staticmethod
    def handle_database_error(error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
        """处理数据库错误"""
        error_type = type(error).__name__
        error_msg = str(error)
        
        if "OperationalError" in error_type:
            if "Lost connection" in error_msg:
                return {
                    "error_type": "connection_lost",
                    "message": "数据库连接丢失，请检查网络",
                    "retry_able": True,
                    "context": context
                }
            elif "Access denied" in error_msg:
                return {
                    "error_type": "access_denied",
                    "message": "数据库访问被拒绝，请检查用户名密码",
                    "retry_able": False,
                    "context": context
                }
                
        return {
            "error_type": "unknown_database_error",
            "message": error_msg,
            "retry_able": False,
            "context": context
        }
    
    @staticmethod
    def handle_llm_error(error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
        """处理 LLM 错误"""
        if isinstance(error, openai.error.RateLimitError):
            return {
                "error_type": "rate_limit",
                "message": "API 调用频率限制",
                "retry_able": True,
                "retry_after": 60,
                "context": context
            }
        elif isinstance(error, openai.error.APIConnectionError):
            return {
                "error_type": "connection_error",
                "message": "无法连接到 LLM API",
                "retry_able": True,
                "context": context
            }
            
        return {
            "error_type": "unknown_llm_error",
            "message": str(error),
            "retry_able": False,
            "context": context
        }
```

### 3.3 测试实现

#### 单元测试示例
```python
# tests/test_agent.py
import pytest
from unittest.mock import Mock, patch
from agent.smart_sql_agent import SmartSQLAgent

class TestSmartSQLAgent:
    """SmartSQLAgent 单元测试"""
    
    @pytest.fixture
    def mock_config(self):
        """模拟配置"""
        config = Mock()
        config.database.type = "mysql"
        config.llm.model = "test-model"
        config.agent.max_steps = 5
        return config
    
    @pytest.fixture
    def agent(self, mock_config):
        """创建测试 Agent"""
        with patch('agent.smart_sql_agent.DatabaseManager'):
            with patch('agent.smart_sql_agent.LLMClient'):
                return SmartSQLAgent(mock_config)
    
    def test_execute_simple_query(self, agent):
        """测试简单查询执行"""
        # 模拟工具返回
        agent.tools['schema_extraction'].run = Mock(
            return_value={"tables": ["users", "orders"]}
        )
        agent.tools['sql_generation'].run = Mock(
            return_value={"sql": "SELECT COUNT(*) FROM users"}
        )
        agent.tools['sql_execution'].run = Mock(
            return_value={"result": [(10,)], "success": True}
        )
        
        # 执行查询
        result = agent.execute_sync("查询用户数量")
        
        # 验证结果
        assert result.success
        assert result.final_result["sql"] == "SELECT COUNT(*) FROM users"
        assert result.final_result["result"] == [(10,)]
    
    def test_error_recovery(self, agent):
        """测试错误恢复机制"""
        # 第一次生成错误的 SQL
        agent.tools['sql_generation'].run = Mock(
            side_effect=[
                {"sql": "SELECT * FORM users"},  # 语法错误
                {"sql": "SELECT * FROM users"}   # 修正后的 SQL
            ]
        )
        
        # 执行应该能从错误中恢复
        result = agent.execute_sync("查询所有用户")
        
        assert result.success
        assert agent.tools['sql_generation'].run.call_count == 2
```

#### 集成测试示例
```python
# tests/test_integration.py
import pytest
from pathlib import Path
from cli.cli import cli
from click.testing import CliRunner

class TestCLIIntegration:
    """CLI 集成测试"""
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    @pytest.fixture
    def test_config(self, tmp_path):
        """创建测试配置文件"""
        config_path = tmp_path / "test_config.yaml"
        config_path.write_text("""
        database:
          type: sqlite
          database: ":memory:"
        llm:
          model: test-model
          base_url: http://localhost:8000
          api_key: test-key
        """)
        return str(config_path)
    
    def test_init_command(self, runner):
        """测试初始化命令"""
        result = runner.invoke(cli, [
            'init',
            '--database-type', 'mysql',
            '--host', 'localhost',
            '--port', '3306',
            '--database', 'test',
            '--model', 'test-model'
        ])
        
        assert result.exit_code == 0
        assert "配置文件已生成" in result.output
    
    def test_schema_command(self, runner, test_config):
        """测试查看模式命令"""
        with patch('database.connection_manager.DatabaseManager'):
            result = runner.invoke(cli, [
                'schema',
                '--config', test_config
            ])
            
            assert result.exit_code == 0
```

## 4. 部署和运维

### 4.1 生产环境配置

#### 生产配置示例
```yaml
# config/production.yaml
app:
  name: "SemanticSQL Agent"
  version: "1.0.0"
  environment: "production"
  debug: false
  log_level: "INFO"

database:
  type: "mysql"
  host: "${DB_HOST}"  # 从环境变量读取
  port: ${DB_PORT}
  database: "${DB_NAME}"
  username: "${DB_USER}"
  password: "${DB_PASSWORD}"
  # 生产环境连接池配置
  pool_size: 20
  max_overflow: 30
  pool_timeout: 30
  pool_pre_ping: true
  pool_recycle: 3600

llm:
  model: "${LLM_MODEL}"
  base_url: "${LLM_BASE_URL}"
  api_key: "${LLM_API_KEY}"
  # 生产环境参数
  temperature: 0.0  # 更稳定的输出
  max_tokens: 10000
  timeout: 60
  retry_count: 5
  retry_delay: 2

agent:
  max_steps: 15
  thinking_mode: "careful"
  enable_reflection: true
  verbose: false
  
monitoring:
  enable_metrics: true
  metrics_port: 9090
  enable_tracing: true
  jaeger_endpoint: "http://jaeger:14268/api/traces"
```

### 4.2 Docker 部署

#### Dockerfile
```dockerfile
FROM python:3.8-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    libmariadb-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建非 root 用户
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# 启动命令
ENTRYPOINT ["python", "main.py"]
CMD ["--help"]
```

#### docker-compose.yaml
```yaml
version: '3.8'

services:
  semanticsql-agent:
    build: .
    image: semanticsql-agent:latest
    container_name: semanticsql-agent
    environment:
      - DB_HOST=mysql
      - DB_PORT=3306
      - DB_NAME=semantic_db
      - DB_USER=semantic_user
      - DB_PASSWORD=${DB_PASSWORD}
      - LLM_MODEL=Qwen3-14B
      - LLM_BASE_URL=http://llm-service:8000/v1
      - LLM_API_KEY=${LLM_API_KEY}
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs
    depends_on:
      - mysql
    networks:
      - semantic-network
    restart: unless-stopped

  mysql:
    image: mysql:8.0
    container_name: semantic-mysql
    environment:
      - MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD}
      - MYSQL_DATABASE=semantic_db
      - MYSQL_USER=semantic_user
      - MYSQL_PASSWORD=${DB_PASSWORD}
    volumes:
      - mysql-data:/var/lib/mysql
    ports:
      - "3306:3306"
    networks:
      - semantic-network
    restart: unless-stopped

volumes:
  mysql-data:

networks:
  semantic-network:
    driver: bridge
```

### 4.3 监控和日志

#### 日志配置
```python
# utils/logger.py
import logging
import logging.handlers
from pathlib import Path

def setup_logging(config: Dict[str, Any]):
    """配置日志系统"""
    log_level = config.get("log_level", "INFO")
    log_dir = Path(config.get("log_dir", "logs"))
    log_dir.mkdir(exist_ok=True)
    
    # 配置根日志器
    logger = logging.getLogger()
    logger.setLevel(log_level)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter(
            '[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s'
        )
    )
    logger.addHandler(console_handler)
    
    # 文件处理器（按日期轮转）
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_dir / "semanticsql.log",
        when="midnight",
        interval=1,
        backupCount=30
    )
    file_handler.setFormatter(
        logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    )
    logger.addHandler(file_handler)
    
    # 错误日志单独记录
    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / "error.log",
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(
        logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s\n%(exc_info)s'
        )
    )
    logger.addHandler(error_handler)
```

#### 性能监控
```python
# utils/monitoring.py
import time
from functools import wraps
from typing import Callable
import prometheus_client as prom

# 定义指标
query_counter = prom.Counter(
    'semanticsql_queries_total',
    'Total number of queries processed',
    ['status', 'query_type']
)

query_duration = prom.Histogram(
    'semanticsql_query_duration_seconds',
    'Query processing duration',
    ['query_type']
)

llm_calls = prom.Counter(
    'semanticsql_llm_calls_total',
    'Total number of LLM API calls',
    ['model', 'status']
)

def monitor_performance(metric_name: str):
    """性能监控装饰器"""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                query_counter.labels(
                    status='success',
                    query_type=metric_name
                ).inc()
                return result
                
            except Exception as e:
                query_counter.labels(
                    status='error',
                    query_type=metric_name
                ).inc()
                raise e
                
            finally:
                duration = time.time() - start_time
                query_duration.labels(
                    query_type=metric_name
                ).observe(duration)
                
        return wrapper
    return decorator
```

## 5. 故障排查指南

### 5.1 常见问题

#### 数据库连接问题
```bash
# 检查数据库连接
python main.py test --config config.yaml --verbose

# 常见错误和解决方案：
# 1. Access denied: 检查用户名密码
# 2. Unknown database: 确认数据库存在
# 3. Can't connect: 检查网络和防火墙
# 4. Too many connections: 调整连接池大小
```

#### LLM 调用问题
```python
# 调试 LLM 调用
import logging
logging.getLogger("openai").setLevel(logging.DEBUG)

# 常见问题：
# 1. Rate limit: 降低调用频率或升级 API 配额
# 2. Timeout: 增加超时时间或优化提示词
# 3. Invalid API key: 检查环境变量和配置
```

### 5.2 性能调优

#### 数据库查询优化
```sql
-- 添加必要的索引
CREATE INDEX idx_table_column ON table_name(column_name);

-- 分析查询性能
EXPLAIN SELECT * FROM users WHERE status = 'active';

-- 优化连接池配置
# config.yaml
database:
  pool_size: 10  # 根据并发量调整
  pool_pre_ping: true  # 连接健康检查
  pool_recycle: 3600  # 连接回收时间
```

#### Agent 执行优化
```python
# 优化 Agent 配置
agent:
  max_steps: 8  # 限制最大步骤数
  thinking_mode: "fast"  # 快速模式
  enable_cache: true  # 启用缓存
  parallel_tools: true  # 并行执行工具
```

## 6. 扩展开发指南

### 6.1 添加新的数据库支持

```python
# database/dialects/oracle.py
from database.base_dialect import BaseDialect

class OracleDialect(BaseDialect):
    """Oracle 数据库方言"""
    
    def get_connection_string(self, config: DatabaseConfig) -> str:
        """构建 Oracle 连接字符串"""
        return f"oracle+cx_oracle://{config.username}:{config.password}@{config.host}:{config.port}/{config.database}"
    
    def get_table_names_query(self) -> str:
        """获取表名的查询"""
        return "SELECT table_name FROM user_tables"
    
    def get_table_schema_query(self, table_name: str) -> str:
        """获取表结构的查询"""
        return f"""
        SELECT 
            column_name,
            data_type,
            nullable,
            data_default
        FROM user_tab_columns
        WHERE table_name = UPPER('{table_name}')
        ORDER BY column_id
        """
```

### 6.2 添加新的 LLM 支持

```python
# utils/llm_clients/claude_client.py
from utils.llm_clients.base_client import BaseLLMClient

class ClaudeClient(BaseLLMClient):
    """Claude API 客户端"""
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.client = anthropic.Client(api_key=config.api_key)
        
    async def call_async(self, messages: List[Dict], **kwargs) -> str:
        """异步调用 Claude API"""
        response = await self.client.messages.create(
            model=self.config.model,
            messages=self._convert_messages(messages),
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            temperature=kwargs.get("temperature", self.config.temperature)
        )
        return response.content[0].text
    
    def _convert_messages(self, messages: List[Dict]) -> List[Dict]:
        """转换消息格式"""
        # Claude 特定的消息格式转换
        return [
            {
                "role": msg["role"],
                "content": msg["content"]
            }
            for msg in messages
        ]
```

### 6.3 自定义提示词模板

```python
# prompts/custom_prompts.py
class CustomPromptTemplates:
    """自定义提示词模板"""
    
    SYSTEM_PROMPT = """你是一个专业的数据库专家，精通 {database_type} 数据库。
    你的任务是帮助用户将自然语言查询转换为准确的 SQL 语句。
    
    数据库信息：
    {schema_info}
    
    请遵循以下原则：
    1. 生成的 SQL 必须语法正确
    2. 考虑查询性能
    3. 使用合适的索引
    4. 避免全表扫描
    """
    
    QUERY_OPTIMIZATION_PROMPT = """
    原始 SQL：
    {original_sql}
    
    执行计划：
    {execution_plan}
    
    请分析这个查询的性能问题，并提供优化建议。
    """
    
    ERROR_RECOVERY_PROMPT = """
    执行以下 SQL 时出错：
    {sql}
    
    错误信息：
    {error_message}
    
    数据库结构：
    {schema}
    
    请分析错误原因并生成正确的 SQL。
    """
```

## 7. 最佳实践总结

### 7.1 代码规范
- 使用类型注解提高代码可读性
- 遵循 PEP 8 编码规范
- 编写完善的文档字符串
- 保持函数简洁，单一职责

### 7.2 安全建议
- 永远不要在代码中硬编码敏感信息
- 使用参数化查询防止 SQL 注入
- 限制数据库用户权限
- 定期更新依赖包

### 7.3 性能建议
- 合理使用缓存减少重复计算
- 批量操作优于单条操作
- 异步处理 I/O 密集型任务
- 监控关键性能指标

### 7.4 运维建议
- 实施完善的日志记录
- 设置告警阈值
- 定期备份配置和数据
- 制定应急响应预案