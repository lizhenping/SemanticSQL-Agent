# SemanticSQL-Agent 核心组件设计规范

## 1. 类型定义规范

### 1.1 基础类型定义

```python
# agent/agent_basics.py
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

class AgentState(Enum):
    """智能体执行状态"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"

class AgentStepState(Enum):
    """步骤执行状态 - 体现 TAO 循环"""
    THINKING = "thinking"      # Thought 阶段
    CALLING_TOOL = "calling_tool"  # Action 阶段
    REFLECTING = "reflecting"   # 增强的 Observation
    COMPLETED = "completed"
    ERROR = "error"

@dataclass
class AgentStep:
    """单个执行步骤"""
    step_number: int
    state: AgentStepState
    llm_response: Optional['LLMResponse'] = None
    tool_calls: Optional[List['ToolCall']] = None
    tool_results: Optional[List['ToolResult']] = None
    reflection: Optional[str] = None
    error: Optional[str] = None
    
@dataclass
class AgentExecution:
    """完整的执行记录"""
    task: str
    steps: List[AgentStep]
    agent_state: AgentState = AgentState.IDLE
    final_result: Optional[str] = None
    success: bool = False
    total_tokens: Optional[int] = None
    execution_time: Optional[float] = None
```

### 1.2 LLM 相关类型

```python
# utils/llm_clients/llm_basics.py
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

@dataclass
class LLMMessage:
    """LLM 消息"""
    role: str  # system, user, assistant
    content: str
    tool_result: Optional['ToolResult'] = None
    
@dataclass
class ToolCall:
    """工具调用请求"""
    id: str
    name: str
    arguments: Dict[str, Any]
    
@dataclass
class LLMResponse:
    """LLM 响应"""
    content: str
    tool_calls: Optional[List[ToolCall]] = None
    usage: Optional[Dict[str, int]] = None
    model: Optional[str] = None
```

### 1.3 工具相关类型

```python
# tools/base.py
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

@dataclass
class ToolParameter:
    """工具参数定义"""
    name: str
    type: str  # string, integer, object, array
    description: str
    required: bool = True
    default: Any = None
    
@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    tool_name: Optional[str] = None
    execution_time: Optional[float] = None
```

## 2. 接口规范

### 2.1 工具接口

```python
# tools/base.py
from abc import ABC, abstractmethod

class Tool(ABC):
    """所有工具必须实现的接口"""
    
    def __init__(self, model_provider: str = "openai"):
        self.model_provider = model_provider
    
    @abstractmethod
    def get_name(self) -> str:
        """返回工具名称（唯一标识）"""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """返回工具描述（供 LLM 理解）"""
        pass
    
    @abstractmethod
    def get_parameters(self) -> List[ToolParameter]:
        """返回工具参数定义"""
        pass
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """执行工具逻辑"""
        pass
    
    def to_openai_function(self) -> Dict[str, Any]:
        """转换为 OpenAI function calling 格式"""
        return {
            "name": self.get_name(),
            "description": self.get_description(),
            "parameters": self._parameters_to_json_schema()
        }
    
    def _parameters_to_json_schema(self) -> Dict[str, Any]:
        """将参数转换为 JSON Schema"""
        properties = {}
        required = []
        
        for param in self.get_parameters():
            properties[param.name] = {
                "type": param.type,
                "description": param.description
            }
            if param.required:
                required.append(param.name)
                
        return {
            "type": "object",
            "properties": properties,
            "required": required
        }
```

### 2.2 LLM 客户端接口

```python
# utils/llm_clients/base_client.py
from abc import ABC, abstractmethod

class BaseLLMClient(ABC):
    """LLM 客户端基类"""
    
    @abstractmethod
    async def chat(
        self,
        messages: List[LLMMessage],
        model: str,
        temperature: float = 0.0,
        tools: Optional[List[Tool]] = None
    ) -> LLMResponse:
        """发送聊天请求"""
        pass
    
    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """计算 token 数量"""
        pass
```

### 2.3 数据库连接器接口

```python
# utils/database_connector.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class TableSchema:
    """表结构定义"""
    name: str
    columns: List[Dict[str, Any]]
    primary_key: Optional[str]
    foreign_keys: List[Dict[str, Any]]
    indexes: List[Dict[str, Any]]

@dataclass
class DatabaseSchema:
    """数据库结构"""
    tables: List[TableSchema]
    relationships: List[Dict[str, Any]]

class DatabaseConnector(ABC):
    """数据库连接器接口"""
    
    @abstractmethod
    async def connect(self, connection_string: str) -> None:
        """建立数据库连接"""
        pass
    
    @abstractmethod
    async def extract_schema(self) -> DatabaseSchema:
        """提取数据库结构"""
        pass
    
    @abstractmethod
    async def execute_query(self, sql: str) -> List[Dict[str, Any]]:
        """执行查询（用于验证）"""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """关闭连接"""
        pass
```

## 3. 工具实现规范

### 3.1 分析工具示例

```python
# tools/schema_extraction_tool.py
class SchemaExtractionTool(Tool):
    """数据库结构提取工具"""
    
    def __init__(self, db_connector: DatabaseConnector, model_provider: str = "openai"):
        super().__init__(model_provider)
        self.db_connector = db_connector
        
    def get_name(self) -> str:
        return "extract_database_schema"
        
    def get_description(self) -> str:
        return (
            "Extract the complete database schema including tables, columns, "
            "data types, primary keys, foreign keys, and relationships. "
            "Use this tool first to understand the database structure."
        )
        
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="include_indexes",
                type="boolean",
                description="Whether to include index information",
                required=False,
                default=False
            )
        ]
        
    async def execute(self, **kwargs) -> ToolResult:
        try:
            include_indexes = kwargs.get('include_indexes', False)
            
            # 提取 schema
            schema = await self.db_connector.extract_schema()
            
            # 格式化输出
            result_data = {
                "tables": [self._format_table(t) for t in schema.tables],
                "relationships": schema.relationships,
                "summary": {
                    "total_tables": len(schema.tables),
                    "total_columns": sum(len(t.columns) for t in schema.tables),
                    "total_relationships": len(schema.relationships)
                }
            }
            
            if not include_indexes:
                # 移除索引信息以减少输出
                for table in result_data["tables"]:
                    table.pop("indexes", None)
                    
            return ToolResult(
                success=True,
                data=result_data,
                tool_name=self.get_name()
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to extract schema: {str(e)}",
                tool_name=self.get_name()
            )
    
    def _format_table(self, table: TableSchema) -> Dict[str, Any]:
        """格式化表信息"""
        return {
            "name": table.name,
            "columns": table.columns,
            "primary_key": table.primary_key,
            "foreign_keys": table.foreign_keys,
            "indexes": table.indexes
        }
```

### 3.2 生成工具示例

```python
# tools/sql_generation_tool.py
class SQLGenerationTool(Tool):
    """SQL 生成工具"""
    
    def get_name(self) -> str:
        return "generate_sql_query"
        
    def get_description(self) -> str:
        return (
            "Generate SQL query based on natural language request and database schema. "
            "Provide the user query, relevant schema information, and any domain context."
        )
        
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="user_query",
                type="string",
                description="The natural language query from user"
            ),
            ToolParameter(
                name="schema_context",
                type="object",
                description="Relevant database schema information"
            ),
            ToolParameter(
                name="domain_context",
                type="object",
                description="Business domain understanding",
                required=False
            )
        ]
        
    async def execute(self, **kwargs) -> ToolResult:
        try:
            user_query = kwargs['user_query']
            schema_context = kwargs['schema_context']
            domain_context = kwargs.get('domain_context', {})
            
            # 构建 prompt
            prompt = self._build_generation_prompt(
                user_query, schema_context, domain_context
            )
            
            # 调用 LLM 生成 SQL
            sql = await self._generate_sql(prompt)
            
            # 基础验证
            validation = self._validate_sql(sql, schema_context)
            
            return ToolResult(
                success=True,
                data={
                    "sql": sql,
                    "validation": validation,
                    "confidence": validation.get("confidence", 0.8)
                },
                tool_name=self.get_name()
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"SQL generation failed: {str(e)}",
                tool_name=self.get_name()
            )
```

## 4. 配置规范

### 4.1 配置类定义

```python
# utils/config.py
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

@dataclass
class ModelConfig:
    """模型配置"""
    provider: str  # openai, anthropic, etc.
    model: str     # gpt-4, claude-3, etc.
    temperature: float = 0.1
    max_tokens: Optional[int] = None
    
@dataclass
class DatabaseConfig:
    """数据库配置"""
    connection_string: str
    pool_size: int = 5
    timeout: int = 30
    
@dataclass
class AgentConfig:
    """智能体配置"""
    model: ModelConfig
    database: DatabaseConfig
    max_steps: int = 15
    tools: List[str] = None
    enable_trajectory: bool = True
    
    @classmethod
    def from_yaml(cls, path: str) -> 'AgentConfig':
        """从 YAML 文件加载配置"""
        import yaml
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        return cls._from_dict(data)
```

### 4.2 配置文件格式

```yaml
# semanticsql_config.yaml
model:
  provider: openai
  model: gpt-4
  temperature: 0.1
  
database:
  connection_string: postgresql://user:pass@localhost/db
  pool_size: 5
  timeout: 30
  
agent:
  max_steps: 15
  tools:
    - extract_database_schema
    - analyze_domain
    - generate_sql_query
    - sequential_thinking
    - task_done
  enable_trajectory: true
  
logging:
  level: INFO
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: logs/semanticsql.log
```

## 5. 错误处理规范

### 5.1 自定义异常

```python
# utils/exceptions.py
class SemanticSQLError(Exception):
    """基础异常类"""
    pass

class DatabaseConnectionError(SemanticSQLError):
    """数据库连接错误"""
    pass

class SchemaExtractionError(SemanticSQLError):
    """Schema 提取错误"""
    pass

class SQLGenerationError(SemanticSQLError):
    """SQL 生成错误"""
    pass

class ToolExecutionError(SemanticSQLError):
    """工具执行错误"""
    def __init__(self, tool_name: str, error: str):
        self.tool_name = tool_name
        super().__init__(f"Tool '{tool_name}' failed: {error}")
```

### 5.2 错误处理模式

```python
# 工具中的错误处理
async def execute(self, **kwargs) -> ToolResult:
    try:
        # 参数验证
        self._validate_parameters(kwargs)
        
        # 执行核心逻辑
        result = await self._core_logic(kwargs)
        
        return ToolResult(success=True, data=result)
        
    except ValidationError as e:
        # 参数验证错误
        return ToolResult(
            success=False,
            error=f"Invalid parameters: {str(e)}",
            tool_name=self.get_name()
        )
    except DatabaseConnectionError as e:
        # 数据库连接错误
        return ToolResult(
            success=False,
            error=f"Database connection failed: {str(e)}",
            tool_name=self.get_name()
        )
    except Exception as e:
        # 未预期的错误
        logger.exception(f"Unexpected error in {self.get_name()}")
        return ToolResult(
            success=False,
            error=f"Unexpected error: {str(e)}",
            tool_name=self.get_name()
        )
```

## 6. 日志规范

```python
# utils/logging.py
import logging
from typing import Dict, Any

class StructuredLogger:
    """结构化日志记录器"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        
    def log_tool_execution(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        result: ToolResult,
        duration: float
    ):
        """记录工具执行"""
        self.logger.info(
            "tool_execution",
            extra={
                "tool_name": tool_name,
                "parameters": parameters,
                "success": result.success,
                "duration": duration,
                "error": result.error
            }
        )
        
    def log_agent_step(self, step: AgentStep, execution_id: str):
        """记录智能体步骤"""
        self.logger.info(
            "agent_step",
            extra={
                "execution_id": execution_id,
                "step_number": step.step_number,
                "state": step.state.value,
                "has_reflection": step.reflection is not None
            }
        )
```

## 7. 测试规范

### 7.1 单元测试模板

```python
# tests/tools/test_schema_extraction.py
import pytest
from unittest.mock import Mock, AsyncMock

class TestSchemaExtractionTool:
    
    @pytest.fixture
    def mock_db_connector(self):
        connector = Mock(spec=DatabaseConnector)
        connector.extract_schema = AsyncMock()
        return connector
        
    @pytest.fixture
    def tool(self, mock_db_connector):
        return SchemaExtractionTool(mock_db_connector)
        
    @pytest.mark.asyncio
    async def test_successful_extraction(self, tool, mock_db_connector):
        # Arrange
        mock_schema = DatabaseSchema(
            tables=[...],
            relationships=[...]
        )
        mock_db_connector.extract_schema.return_value = mock_schema
        
        # Act
        result = await tool.execute(include_indexes=True)
        
        # Assert
        assert result.success
        assert "tables" in result.data
        assert result.error is None
        
    @pytest.mark.asyncio
    async def test_extraction_failure(self, tool, mock_db_connector):
        # Arrange
        mock_db_connector.extract_schema.side_effect = Exception("Connection lost")
        
        # Act
        result = await tool.execute()
        
        # Assert
        assert not result.success
        assert "Connection lost" in result.error
```

### 7.2 集成测试模板

```python
# tests/test_nl2sql_integration.py
@pytest.mark.integration
class TestNL2SQLIntegration:
    
    @pytest.mark.asyncio
    async def test_end_to_end_flow(self, test_database):
        # 设置测试数据库
        await setup_test_database(test_database)
        
        # 创建智能体
        config = AgentConfig(
            model=ModelConfig(provider="openai", model="gpt-4"),
            database=DatabaseConfig(connection_string=test_database.url),
            max_steps=10
        )
        agent = NL2SQLAgent(config)
        
        # 执行查询
        agent.new_task(
            query="Show me total sales by region",
            database_url=test_database.url
        )
        execution = await agent.execute_task()
        
        # 验证结果
        assert execution.success
        assert "SELECT" in execution.final_result
        assert execution.agent_state == AgentState.COMPLETED
```