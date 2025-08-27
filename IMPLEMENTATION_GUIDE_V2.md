# SemanticSQL-Agent 实现指南（简化版）

## 1. 项目结构

参考 nl2sql_pipeline 的项目结构：

```
semanticsql-agent/
├── setup.py
├── requirements.txt
├── README.md
├── semanticsql_config.yaml.example
│
├── semanticsql/
│   ├── __init__.py
│   ├── cli.py                    # 命令行入口
│   │
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── agent_basics.py       # 基础类型定义
│   │   ├── base_agent.py         # 基础智能体
│   │   └── nl2sql_agent.py       # NL2SQL智能体
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py               # 工具基类
│   │   ├── schema_extraction_tool.py
│   │   ├── initial_domain_analysis_tool.py
│   │   ├── field_classification_tool.py
│   │   ├── table_description_tool.py
│   │   ├── column_description_tool.py
│   │   ├── er_analysis_tool.py
│   │   ├── scenario_generation_tool.py
│   │   ├── sql_generation_tool.py
│   │   ├── sequential_thinking_tool.py
│   │   └── task_done_tool.py
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   └── database.py           # 数据库配置
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── database_service.py   # 数据库服务基类
│   │   └── mysql_database_service.py
│   │
│   ├── utils/
│   │   └── llm_clients/
│   │       ├── __init__.py
│   │       ├── llm_basics.py
│   │       ├── base_client.py
│   │       └── openai_client.py
│   │
│   └── prompt/
│       ├── __init__.py
│       └── agent_prompt.py
│
└── examples/
    └── basic_usage.py
```

## 2. 核心实现步骤

### 2.1 基础类型定义

```python
# semanticsql/agent/agent_basics.py
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

@dataclass
class ToolResult:
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    tool_name: Optional[str] = None

@dataclass
class AgentStep:
    step_number: int
    state: AgentStepState
    tool_calls: Optional[List] = None
    tool_results: Optional[List[ToolResult]] = None
    reflection: Optional[str] = None

@dataclass
class AgentExecution:
    task: str
    steps: List[AgentStep]
    agent_state: AgentState = AgentState.IDLE
    final_result: Optional[str] = None
    success: bool = False
```

### 2.2 数据库配置（参考 nl2sql_pipeline）

```python
# semanticsql/config/database.py
from typing import Dict, Any, Optional

class DatabaseConfig:
    """数据库配置管理器"""
    
    DEFAULT_PORT = 3306
    
    def __init__(self, 
                 host: Optional[str] = None,
                 port: Optional[int] = None,
                 user: Optional[str] = None,
                 password: Optional[str] = None,
                 database: Optional[str] = None):
        self.host = host
        self.port = port or self.DEFAULT_PORT
        self.user = user
        self.password = password
        self.database = database
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'host': self.host,
            'port': self.port,
            'user': self.user,
            'password': self.password,
            'database': self.database
        }
    
    def validate(self) -> bool:
        required_fields = ['host', 'user', 'password', 'database']
        return all(getattr(self, field) is not None for field in required_fields)
```

### 2.3 数据库服务（参考 nl2sql_pipeline）

```python
# semanticsql/services/mysql_database_service.py
import pymysql
from typing import List, Dict, Any
from .database_service import DatabaseService

class MySQLDatabaseService(DatabaseService):
    
    def __init__(self):
        self.connection = None
        self.cursor = None
        
    def connect(self, config: Dict[str, Any]):
        """建立数据库连接"""
        self.connection = pymysql.connect(
            host=config['host'],
            port=config.get('port', 3306),
            user=config['user'],
            password=config['password'],
            database=config['database'],
            charset='utf8mb4'
        )
        self.cursor = self.connection.cursor(pymysql.cursors.DictCursor)
        
    def disconnect(self):
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
            
    def get_tables(self) -> List[Dict[str, Any]]:
        """获取所有表信息"""
        query = """
            SELECT 
                TABLE_NAME as name,
                TABLE_COMMENT as comment
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
        """
        self.cursor.execute(query)
        return self.cursor.fetchall()
```

### 2.4 LLM 客户端（简化版）

```python
# semanticsql/utils/llm_clients/openai_client.py
import openai
from typing import List, Dict, Any
from .base_client import BaseLLMClient

class OpenAIClient(BaseLLMClient):
    
    def __init__(self, api_key: str):
        self.client = openai.OpenAI(api_key=api_key)
        
    def chat(self, messages: List[Dict], model: str, tools: List = None) -> Dict:
        """同步调用 OpenAI API"""
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            temperature=0.1
        )
        
        return {
            "content": response.choices[0].message.content,
            "tool_calls": response.choices[0].message.tool_calls
        }
```

### 2.5 工具实现示例

```python
# semanticsql/tools/schema_extraction_tool.py
from typing import Dict, Any
from .base import Tool, ToolResult

class SchemaExtractionTool(Tool):
    """数据库结构提取工具"""
    
    def __init__(self, db_service):
        self.db_service = db_service
        
    def get_name(self) -> str:
        return "extract_database_schema"
        
    def get_description(self) -> str:
        return "提取数据库的表结构信息，包括表名、列名、数据类型等"
        
    def execute(self, **kwargs) -> ToolResult:
        try:
            # 获取所有表
            tables = self.db_service.get_tables()
            
            # 获取每个表的详细信息
            schema_info = []
            for table in tables:
                table_info = {
                    "name": table["name"],
                    "comment": table.get("comment", ""),
                    "columns": self.db_service.get_columns(table["name"])
                }
                schema_info.append(table_info)
            
            return ToolResult(
                success=True,
                data={
                    "tables": schema_info,
                    "table_count": len(tables)
                },
                tool_name=self.get_name()
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                tool_name=self.get_name()
            )
```

### 2.6 智能体实现

```python
# semanticsql/agent/nl2sql_agent.py
from typing import List
from .base_agent import BaseAgent
from ..tools import *
from ..services import MySQLDatabaseService

class NL2SQLAgent(BaseAgent):
    """NL2SQL 智能体"""
    
    def __init__(self, db_config):
        super().__init__()
        
        # 初始化数据库服务
        self.db_service = MySQLDatabaseService()
        self.db_service.connect(db_config.to_dict())
        
        # 初始化工具
        self._initialize_tools()
        
    def _initialize_tools(self):
        """初始化工具集"""
        self._tools = [
            SchemaExtractionTool(self.db_service),
            InitialDomainAnalysisTool(),
            FieldClassificationTool(self.db_service),
            TableDescriptionTool(),
            ColumnDescriptionTool(),
            ERAnalysisTool(),
            ScenarioGenerationTool(),
            SQLGenerationTool(),
            SequentialThinkingTool(),
            TaskDoneTool()
        ]
        
    def execute_nl2sql(self, query: str) -> Dict[str, Any]:
        """执行 NL2SQL 转换"""
        self._task = query
        self._initial_messages = [
            {
                "role": "system",
                "content": "你是一个SQL专家，请根据用户的自然语言查询生成对应的SQL语句。"
            },
            {
                "role": "user", 
                "content": f"请为以下查询生成SQL: {query}"
            }
        ]
        
        # 执行任务
        execution = self.execute_task()
        
        # 返回结果
        return {
            "success": execution.success,
            "sql": execution.final_result,
            "steps": len(execution.steps)
        }
```

## 3. 使用示例

```python
# examples/basic_usage.py
from semanticsql import NL2SQLAgent, DatabaseConfig

def main():
    # 数据库配置
    db_config = DatabaseConfig(
        host="localhost",
        user="root",
        password="password",
        database="test_db"
    )
    
    # 验证配置
    if not db_config.validate():
        print("数据库配置不完整")
        return
        
    # 创建智能体
    agent = NL2SQLAgent(db_config)
    
    # 测试查询
    queries = [
        "查询所有员工的信息",
        "统计每个部门的平均工资",
        "找出工资最高的前10名员工"
    ]
    
    for query in queries:
        print(f"\n查询: {query}")
        result = agent.execute_nl2sql(query)
        
        if result["success"]:
            print(f"生成的SQL: {result['sql']}")
            print(f"执行步骤数: {result['steps']}")
        else:
            print("SQL生成失败")

if __name__ == "__main__":
    main()
```

## 4. 配置文件

```yaml
# semanticsql_config.yaml.example
# OpenAI 配置
openai:
  api_key: "your-api-key"
  model: "gpt-4"

# 数据库配置
database:
  host: localhost
  port: 3306
  user: root
  password: password
  database: test_db

# 智能体配置
agent:
  max_steps: 15
```

## 5. 安装依赖

```txt
# requirements.txt
openai>=1.0.0
pymysql>=1.0.0
pyyaml>=6.0
rich>=13.0.0
pydantic>=2.0.0
```

## 6. 命令行接口

```python
# semanticsql/cli.py
import argparse
from .agent import NL2SQLAgent
from .config import DatabaseConfig

def main():
    parser = argparse.ArgumentParser(description='NL2SQL 命令行工具')
    parser.add_argument('query', help='自然语言查询')
    parser.add_argument('--host', default='localhost', help='数据库主机')
    parser.add_argument('--user', required=True, help='数据库用户')
    parser.add_argument('--password', required=True, help='数据库密码')
    parser.add_argument('--database', required=True, help='数据库名')
    
    args = parser.parse_args()
    
    # 创建配置
    db_config = DatabaseConfig(
        host=args.host,
        user=args.user,
        password=args.password,
        database=args.database
    )
    
    # 执行查询
    agent = NL2SQLAgent(db_config)
    result = agent.execute_nl2sql(args.query)
    
    if result["success"]:
        print(f"SQL: {result['sql']}")
    else:
        print("生成失败")

if __name__ == "__main__":
    main()
```

## 7. 注意事项

1. **数据库连接**：确保 MySQL 服务正在运行
2. **API Key**：需要有效的 OpenAI API Key
3. **Python 版本**：需要 Python 3.11 或更高版本
4. **编码**：数据库和表使用 UTF-8 编码

## 8. 联系方式

如有问题，请联系：lizhenping18@mails.ucas.ac.cn