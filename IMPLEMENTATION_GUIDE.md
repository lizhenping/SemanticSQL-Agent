# SemanticSQL-Agent 实现指南

## 1. 快速开始

### 1.1 项目初始化

```bash
# 创建项目目录
mkdir semanticsql-agent
cd semanticsql-agent

# 初始化 Python 项目
uv init
# 或使用 poetry
poetry init

# 创建基础目录结构
mkdir -p semanticsql/{agent,tools,utils/{llm_clients,cli},prompt}
mkdir -p tests/{unit,integration}
mkdir -p docs examples benchmarks
```

### 1.2 依赖安装

```toml
# pyproject.toml
[project]
name = "semanticsql-agent"
version = "0.1.0"
description = "AI-powered Natural Language to SQL Agent"
requires-python = ">=3.11"

dependencies = [
    "openai>=1.0.0",
    "sqlalchemy>=2.0.0",
    "asyncpg>=0.29.0",  # PostgreSQL
    "aiomysql>=0.2.0",  # MySQL
    "pydantic>=2.0.0",
    "pyyaml>=6.0",
    "rich>=13.0.0",     # CLI 美化
    "httpx>=0.25.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0.0",
    "mypy>=1.0.0",
    "ruff>=0.1.0",
    "black>=23.0.0",
]
```

## 2. 核心组件实现步骤

### 2.1 Step 1: 基础类型和工具框架

首先实现基础的类型定义和工具框架：

```python
# semanticsql/agent/agent_basics.py
"""基础类型定义 - 参考 TRAEAgent"""
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

class AgentState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"

class AgentStepState(Enum):
    THINKING = "thinking"
    CALLING_TOOL = "calling_tool"
    REFLECTING = "reflecting"
    COMPLETED = "completed"
    ERROR = "error"

# ... 其他类型定义
```

```python
# semanticsql/tools/base.py
"""工具基类实现"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class ToolResult:
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    tool_name: Optional[str] = None

class Tool(ABC):
    """工具基类"""
    
    @abstractmethod
    def get_name(self) -> str:
        pass
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        pass
```

### 2.2 Step 2: LLM 客户端

实现 LLM 客户端，支持多个提供商：

```python
# semanticsql/utils/llm_clients/base_client.py
"""LLM 客户端基类"""
from abc import ABC, abstractmethod
from typing import List, Optional

class BaseLLMClient(ABC):
    
    @abstractmethod
    async def chat(
        self,
        messages: List[LLMMessage],
        model: str,
        tools: Optional[List[Tool]] = None
    ) -> LLMResponse:
        pass

# semanticsql/utils/llm_clients/openai_client.py
"""OpenAI 客户端实现"""
import openai
from typing import List, Optional

class OpenAIClient(BaseLLMClient):
    
    def __init__(self, api_key: str):
        self.client = openai.AsyncOpenAI(api_key=api_key)
        
    async def chat(
        self,
        messages: List[LLMMessage],
        model: str,
        tools: Optional[List[Tool]] = None
    ) -> LLMResponse:
        # 转换消息格式
        openai_messages = self._convert_messages(messages)
        
        # 转换工具定义
        functions = None
        if tools:
            functions = [tool.to_openai_function() for tool in tools]
            
        # 调用 API
        response = await self.client.chat.completions.create(
            model=model,
            messages=openai_messages,
            functions=functions,
            temperature=0.1
        )
        
        # 转换响应
        return self._convert_response(response)
```

### 2.3 Step 3: 数据库连接器

实现数据库连接和 schema 提取：

```python
# semanticsql/utils/database_connector.py
"""数据库连接器实现"""
import asyncpg
import aiomysql
from sqlalchemy import create_engine, inspect
from urllib.parse import urlparse

class DatabaseConnector:
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.db_type = self._parse_db_type(connection_string)
        
    async def extract_schema(self) -> DatabaseSchema:
        if self.db_type == "postgresql":
            return await self._extract_postgres_schema()
        elif self.db_type == "mysql":
            return await self._extract_mysql_schema()
        else:
            raise NotImplementedError(f"Database type {self.db_type} not supported")
            
    async def _extract_postgres_schema(self) -> DatabaseSchema:
        conn = await asyncpg.connect(self.connection_string)
        try:
            # 获取所有表
            tables_query = """
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """
            tables = await conn.fetch(tables_query)
            
            # 获取每个表的详细信息
            table_schemas = []
            for table in tables:
                table_name = table['table_name']
                
                # 获取列信息
                columns_query = """
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = $1
                """
                columns = await conn.fetch(columns_query, table_name)
                
                # 获取主键
                pk_query = """
                    SELECT column_name
                    FROM information_schema.key_column_usage
                    WHERE table_name = $1 AND constraint_name LIKE '%_pkey'
                """
                pk = await conn.fetchval(pk_query, table_name)
                
                table_schemas.append(TableSchema(
                    name=table_name,
                    columns=[dict(c) for c in columns],
                    primary_key=pk,
                    foreign_keys=[],  # TODO: 实现外键提取
                    indexes=[]        # TODO: 实现索引提取
                ))
                
            return DatabaseSchema(tables=table_schemas, relationships=[])
            
        finally:
            await conn.close()
```

### 2.4 Step 4: 基础智能体实现

实现 BaseAgent 类：

```python
# semanticsql/agent/base_agent.py
"""基础智能体类 - 参考 TRAEAgent 的设计"""
from abc import ABC, abstractmethod
import time

class BaseAgent(ABC):
    
    def __init__(self, config: AgentConfig):
        self._llm_client = self._create_llm_client(config.model)
        self._tools: List[Tool] = []
        self._max_steps = config.max_steps
        self._trajectory_recorder = None
        
    async def execute_task(self) -> AgentExecution:
        """执行任务 - 实现 TAO 循环"""
        start_time = time.time()
        execution = AgentExecution(task=self._task, steps=[])
        messages = self._initial_messages
        
        try:
            execution.agent_state = AgentState.RUNNING
            
            for step_number in range(1, self._max_steps + 1):
                step = AgentStep(step_number=step_number)
                
                # Thought 阶段
                step.state = AgentStepState.THINKING
                llm_response = await self._llm_client.chat(messages, self._tools)
                step.llm_response = llm_response
                
                # 检查是否完成
                if self._is_task_completed(llm_response):
                    execution.agent_state = AgentState.COMPLETED
                    execution.final_result = llm_response.content
                    execution.success = True
                    break
                    
                # Action 阶段
                if llm_response.tool_calls:
                    step.state = AgentStepState.CALLING_TOOL
                    tool_results = await self._execute_tools(llm_response.tool_calls)
                    step.tool_results = tool_results
                    
                    # Observation 阶段
                    for result in tool_results:
                        messages.append(LLMMessage(
                            role="user",
                            tool_result=result
                        ))
                    
                    # 简单反思
                    reflection = self.reflect_on_result(tool_results)
                    if reflection:
                        step.state = AgentStepState.REFLECTING
                        step.reflection = reflection
                        messages.append(LLMMessage(
                            role="assistant",
                            content=reflection
                        ))
                        
                execution.steps.append(step)
                
        except Exception as e:
            execution.agent_state = AgentState.ERROR
            execution.final_result = f"Error: {str(e)}"
            
        execution.execution_time = time.time() - start_time
        return execution
        
    def reflect_on_result(self, tool_results: List[ToolResult]) -> str | None:
        """简单的反思机制"""
        failed_results = [r for r in tool_results if not r.success]
        if not failed_results:
            return None
            
        reflections = []
        for result in failed_results:
            reflections.append(
                f"Tool {result.tool_name} failed: {result.error}. "
                "Please try a different approach."
            )
        return "\n".join(reflections)
```

### 2.5 Step 5: NL2SQL 智能体

实现具体的 NL2SQL 智能体：

```python
# semanticsql/agent/nl2sql_agent.py
"""NL2SQL 智能体实现"""
from typing import List

class NL2SQLAgent(BaseAgent):
    
    def __init__(self, config: NL2SQLConfig):
        super().__init__(config)
        self.db_connector = DatabaseConnector(config.database.connection_string)
        self._initialize_tools()
        
    def _initialize_tools(self):
        """初始化工具集"""
        self._tools = [
            SchemaExtractionTool(self.db_connector),
            DomainAnalysisTool(),
            SQLGenerationTool(),
            SequentialThinkingTool(),
            TaskDoneTool(),
        ]
        
    def new_task(self, query: str, database_url: str):
        """创建新任务"""
        self._task = query
        self._initial_messages = [
            LLMMessage(
                role="system",
                content=NL2SQL_SYSTEM_PROMPT
            ),
            LLMMessage(
                role="user",
                content=f"Database: {database_url}\nQuery: {query}"
            )
        ]
        
    def reflect_on_result(self, tool_results: List[ToolResult]) -> str | None:
        """NL2SQL 特定的反思"""
        failed_results = [r for r in tool_results if not r.success]
        if not failed_results:
            return None
            
        reflections = []
        for result in failed_results:
            if "schema" in result.tool_name.lower():
                reflections.append(
                    f"Schema extraction failed: {result.error}. "
                    "Check database connection and permissions."
                )
            elif "sql" in result.tool_name.lower():
                reflections.append(
                    f"SQL generation failed: {result.error}. "
                    "The query might be ambiguous."
                )
            else:
                reflections.append(f"{result.tool_name} failed: {result.error}")
                
        return "\n".join(reflections) if reflections else None
```

### 2.6 Step 6: 实现核心工具

```python
# semanticsql/tools/schema_extraction_tool.py
"""Schema 提取工具"""
class SchemaExtractionTool(Tool):
    
    def __init__(self, db_connector: DatabaseConnector, model_provider: str = "openai"):
        super().__init__(model_provider)
        self.db_connector = db_connector
        
    def get_name(self) -> str:
        return "extract_database_schema"
        
    def get_description(self) -> str:
        return "Extract database schema including tables, columns, and relationships"
        
    async def execute(self, **kwargs) -> ToolResult:
        try:
            schema = await self.db_connector.extract_schema()
            
            # 格式化输出，便于 LLM 理解
            formatted_schema = self._format_schema(schema)
            
            return ToolResult(
                success=True,
                data={
                    "schema": formatted_schema,
                    "summary": f"Found {len(schema.tables)} tables"
                },
                tool_name=self.get_name()
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                tool_name=self.get_name()
            )
            
    def _format_schema(self, schema: DatabaseSchema) -> str:
        """格式化 schema 为易读的文本"""
        lines = []
        for table in schema.tables:
            lines.append(f"Table: {table.name}")
            for col in table.columns:
                nullable = "NULL" if col["is_nullable"] else "NOT NULL"
                lines.append(f"  - {col['column_name']}: {col['data_type']} {nullable}")
            if table.primary_key:
                lines.append(f"  Primary Key: {table.primary_key}")
            lines.append("")
        return "\n".join(lines)
```

## 3. 使用示例

### 3.1 基础使用

```python
# examples/basic_usage.py
import asyncio
from semanticsql.agent import NL2SQLAgent
from semanticsql.utils.config import NL2SQLConfig

async def main():
    # 创建配置
    config = NL2SQLConfig(
        model=ModelConfig(provider="openai", model="gpt-4"),
        database=DatabaseConfig(
            connection_string="postgresql://user:pass@localhost/mydb"
        ),
        max_steps=10
    )
    
    # 创建智能体
    agent = NL2SQLAgent(config)
    
    # 设置任务
    agent.new_task(
        query="Show me total sales by region for last month",
        database_url=config.database.connection_string
    )
    
    # 执行任务
    execution = await agent.execute_task()
    
    # 输出结果
    if execution.success:
        print(f"Generated SQL: {execution.final_result}")
    else:
        print(f"Failed: {execution.final_result}")
        
    # 输出执行步骤
    for step in execution.steps:
        print(f"Step {step.step_number}: {step.state.value}")
        if step.tool_results:
            for result in step.tool_results:
                print(f"  Tool: {result.tool_name} - Success: {result.success}")

if __name__ == "__main__":
    asyncio.run(main())
```

### 3.2 CLI 使用

```python
# semanticsql/cli.py
"""命令行接口"""
import click
import asyncio
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

@click.command()
@click.option('--query', '-q', required=True, help='Natural language query')
@click.option('--database', '-d', required=True, help='Database connection string')
@click.option('--config', '-c', help='Config file path')
def nl2sql(query: str, database: str, config: str):
    """Convert natural language to SQL"""
    asyncio.run(execute_query(query, database, config))
    
async def execute_query(query: str, database: str, config_path: str):
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Analyzing query...", total=None)
        
        # 加载配置
        if config_path:
            config = NL2SQLConfig.from_yaml(config_path)
            config.database.connection_string = database
        else:
            config = create_default_config(database)
            
        # 创建智能体
        agent = NL2SQLAgent(config)
        agent.new_task(query, database)
        
        # 执行
        progress.update(task, description="Generating SQL...")
        execution = await agent.execute_task()
        
        progress.stop()
        
        # 显示结果
        if execution.success:
            console.print("\n[green]✓ Generated SQL:[/green]")
            console.print(execution.final_result, style="bright_blue")
        else:
            console.print(f"\n[red]✗ Failed:[/red] {execution.final_result}")

if __name__ == "__main__":
    nl2sql()
```

## 4. 测试策略

### 4.1 单元测试

```python
# tests/unit/test_tools.py
import pytest
from unittest.mock import AsyncMock, Mock

@pytest.mark.asyncio
async def test_schema_extraction_tool():
    # Mock 数据库连接器
    mock_connector = Mock(spec=DatabaseConnector)
    mock_connector.extract_schema = AsyncMock(
        return_value=DatabaseSchema(
            tables=[
                TableSchema(
                    name="users",
                    columns=[
                        {"column_name": "id", "data_type": "integer", "is_nullable": False},
                        {"column_name": "name", "data_type": "varchar", "is_nullable": True}
                    ],
                    primary_key="id",
                    foreign_keys=[],
                    indexes=[]
                )
            ],
            relationships=[]
        )
    )
    
    # 创建工具
    tool = SchemaExtractionTool(mock_connector)
    
    # 执行
    result = await tool.execute()
    
    # 验证
    assert result.success
    assert "users" in result.data["schema"]
    assert "Found 1 tables" in result.data["summary"]
```

### 4.2 集成测试

```python
# tests/integration/test_nl2sql_flow.py
import pytest
import asyncio

@pytest.mark.integration
async def test_simple_query(test_database):
    """测试简单查询"""
    # 准备测试数据
    await setup_test_data(test_database)
    
    # 创建智能体
    config = create_test_config(test_database.url)
    agent = NL2SQLAgent(config)
    
    # 执行查询
    agent.new_task("Show all users", test_database.url)
    execution = await agent.execute_task()
    
    # 验证
    assert execution.success
    assert "SELECT" in execution.final_result
    assert "FROM users" in execution.final_result.lower()
```

## 5. 部署建议

### 5.1 Docker 部署

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY pyproject.toml .
RUN pip install -e .

# 复制代码
COPY semanticsql/ semanticsql/

# 运行
CMD ["python", "-m", "semanticsql.cli"]
```

### 5.2 API 服务

```python
# semanticsql/api.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class QueryRequest(BaseModel):
    query: str
    database_url: str

@app.post("/nl2sql")
async def convert_nl2sql(request: QueryRequest):
    try:
        config = create_default_config(request.database_url)
        agent = NL2SQLAgent(config)
        agent.new_task(request.query, request.database_url)
        
        execution = await agent.execute_task()
        
        if execution.success:
            return {
                "sql": execution.final_result,
                "steps": len(execution.steps),
                "execution_time": execution.execution_time
            }
        else:
            raise HTTPException(status_code=400, detail=execution.final_result)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

## 6. 性能优化

### 6.1 Schema 缓存

```python
# semanticsql/utils/cache.py
from functools import lru_cache
import hashlib

class SchemaCache:
    def __init__(self):
        self._cache = {}
        
    def get_cache_key(self, connection_string: str) -> str:
        return hashlib.md5(connection_string.encode()).hexdigest()
        
    async def get_or_extract(self, connector: DatabaseConnector) -> DatabaseSchema:
        key = self.get_cache_key(connector.connection_string)
        
        if key not in self._cache:
            self._cache[key] = await connector.extract_schema()
            
        return self._cache[key]
```

### 6.2 并行工具执行

```python
# semanticsql/tools/base.py
class ToolExecutor:
    def __init__(self, tools: List[Tool]):
        self.tools = {tool.get_name(): tool for tool in tools}
        
    async def parallel_execute(self, tool_calls: List[ToolCall]) -> List[ToolResult]:
        """并行执行多个工具"""
        tasks = []
        for call in tool_calls:
            tool = self.tools.get(call.name)
            if tool:
                tasks.append(tool.execute(**call.arguments))
                
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(ToolResult(
                    success=False,
                    error=str(result),
                    tool_name=tool_calls[i].name
                ))
            else:
                final_results.append(result)
                
        return final_results
```

## 7. 监控和日志

### 7.1 结构化日志

```python
# semanticsql/utils/logging.py
import structlog

logger = structlog.get_logger()

def log_execution(execution: AgentExecution):
    logger.info(
        "execution_completed",
        execution_id=execution.id,
        task=execution.task,
        success=execution.success,
        steps=len(execution.steps),
        total_tokens=execution.total_tokens,
        execution_time=execution.execution_time,
        final_sql=execution.final_result if execution.success else None
    )
```

### 7.2 Prometheus 指标

```python
# semanticsql/utils/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# 定义指标
query_counter = Counter('nl2sql_queries_total', 'Total number of queries')
success_counter = Counter('nl2sql_success_total', 'Total successful conversions')
execution_time = Histogram('nl2sql_execution_seconds', 'Execution time')
active_executions = Gauge('nl2sql_active_executions', 'Currently active executions')

def record_execution(execution: AgentExecution):
    query_counter.inc()
    if execution.success:
        success_counter.inc()
    execution_time.observe(execution.execution_time)
```

## 8. 常见问题

### 8.1 处理复杂查询

对于复杂查询，可以使用 Sequential Thinking Tool：

```python
# 在系统提示词中强调
NL2SQL_SYSTEM_PROMPT = """
For complex queries involving multiple tables, aggregations, or complex conditions,
use the sequential_thinking tool to break down the problem step by step.
"""
```

### 8.2 处理歧义

```python
class AmbiguityDetectionTool(Tool):
    """检测查询歧义"""
    
    def get_name(self) -> str:
        return "detect_ambiguity"
        
    async def execute(self, query: str, schema: Dict) -> ToolResult:
        # 检测可能的歧义
        ambiguities = []
        
        # 检查表名歧义
        words = query.lower().split()
        for word in words:
            matching_tables = [t for t in schema['tables'] if word in t['name'].lower()]
            if len(matching_tables) > 1:
                ambiguities.append(f"'{word}' could refer to: {matching_tables}")
                
        return ToolResult(
            success=True,
            data={"ambiguities": ambiguities, "has_ambiguity": len(ambiguities) > 0}
        )
```

## 9. 扩展指南

### 9.1 添加新的数据库支持

```python
# semanticsql/utils/database_connector.py
class OracleConnector(DatabaseConnector):
    async def extract_schema(self) -> DatabaseSchema:
        # Oracle 特定的 schema 提取逻辑
        pass
```

### 9.2 添加自定义工具

```python
# semanticsql/tools/custom_tool.py
class DataProfilingTool(Tool):
    """数据分析工具"""
    
    def get_name(self) -> str:
        return "profile_data"
        
    def get_description(self) -> str:
        return "Analyze data distribution and statistics for better query generation"
        
    async def execute(self, table_name: str) -> ToolResult:
        # 实现数据分析逻辑
        pass
```

## 10. 发布检查清单

- [ ] 所有测试通过
- [ ] 类型检查通过 (`mypy`)
- [ ] 代码格式化 (`black`, `ruff`)
- [ ] 文档完整
- [ ] 性能基准测试
- [ ] 安全审查（SQL 注入防护）
- [ ] 配置示例文件
- [ ] Docker 镜像构建
- [ ] CI/CD 配置