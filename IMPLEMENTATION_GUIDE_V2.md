# SemanticSQL-Agent 实现指南（LangChain & LangGraph 版本）

## 1. 项目初始化

### 1.1 项目结构

```bash
semanticsql-agent/
├── setup.py
├── requirements.txt
├── .env.example
├── README.md
│
├── config/
│   ├── __init__.py
│   ├── settings.py
│   └── database.py
│
├── models/
│   ├── __init__.py
│   ├── states.py           # LangGraph 状态
│   ├── schemas.py          # Pydantic 模型
│   └── database.py         # 数据库模型
│
├── tools/
│   ├── __init__.py
│   ├── base.py
│   ├── database_tools.py
│   ├── analysis_tools.py
│   └── generation_tools.py
│
├── prompts/
│   ├── __init__.py
│   ├── templates/
│   │   ├── schema_analysis_system.txt
│   │   ├── domain_analysis_system.txt
│   │   └── sql_generation_system.txt
│   ├── examples.yaml
│   └── prompt_manager.py
│
├── agent/
│   ├── __init__.py
│   ├── graph.py           # LangGraph 定义
│   ├── nodes.py           # 节点实现
│   ├── memory.py          # 内存管理
│   └── nl2sql_agent.py    # 主智能体
│
├── utils/
│   ├── __init__.py
│   ├── database_connector.py
│   ├── llm_client.py
│   ├── output_parser.py
│   └── sql_parser.py
│
├── cli.py                  # 命令行接口
└── examples/
    └── basic_usage.py
```

### 1.2 依赖安装

```txt
# requirements.txt
langchain>=0.1.0
langgraph>=0.0.20
langchain-openai>=0.0.5
langchain-community>=0.0.10
pydantic>=2.0.0
sqlalchemy>=2.0.0
pymysql>=1.0.0
python-dotenv>=1.0.0
pyyaml>=6.0
jinja2>=3.0.0
rich>=13.0.0
```

### 1.3 环境配置

```bash
# .env.example
# LLM 配置
MODEL_NAME=Qwen3-14B
API_KEY=not-needed
BASE_URL=http://192.168.200.216:9009/v1

# 数据库配置
DB_HOST=192.168.200.216
DB_PORT=13306
DB_USER=testuser
DB_PASSWORD=testpass
DB_DATABASE=testdb

# Agent 配置
MAX_STEPS=15
TEMPERATURE=0.1
```

## 2. 核心实现

### 2.1 配置管理

```python
# config/settings.py
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """全局配置"""
    # LLM 配置
    model_name: str = "Qwen3-14B"
    api_key: str = "not-needed"
    base_url: str = "http://localhost:8000/v1"
    temperature: float = 0.1
    
    # 数据库配置
    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_database: str = "test"
    
    # Agent 配置
    max_steps: int = 15
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# 全局配置实例
settings = Settings()
```

### 2.2 状态定义

```python
# models/states.py
from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime

class NL2SQLState(TypedDict):
    """LangGraph 工作流状态"""
    # 输入
    query: str
    database_name: str
    
    # 数据库连接
    db: Any  # SQLDatabase 实例
    
    # Schema 信息
    schema_info: Optional[Dict[str, Any]]
    table_count: Optional[int]
    
    # 分析结果
    domain_analysis: Optional[Dict[str, Any]]
    field_classification: Optional[Dict[str, Any]]
    table_descriptions: Optional[Dict[str, Any]]
    column_descriptions: Optional[Dict[str, Any]]
    er_relations: Optional[List[Dict[str, Any]]]
    
    # 生成结果
    scenario: Optional[Dict[str, Any]]
    generated_sql: Optional[str]
    sql_explanation: Optional[str]
    
    # 执行追踪
    current_step: str
    execution_steps: List[Dict[str, Any]]
    errors: List[str]
```

### 2.3 Pydantic 模型

```python
# models/schemas.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

class TableInfo(BaseModel):
    """表信息"""
    name: str
    comment: Optional[str] = None
    columns: List[Dict[str, Any]] = []
    row_count: Optional[int] = None
    
class DomainAnalysisResult(BaseModel):
    """领域分析结果"""
    domain: str = Field(description="业务领域")
    description: str = Field(description="领域描述")
    key_entities: List[str] = Field(description="关键实体")
    business_rules: List[str] = Field(description="业务规则")
    
class FieldClassificationResult(BaseModel):
    """字段分类结果"""
    dimensions: Dict[str, List[str]] = Field(description="维度字段")
    measures: Dict[str, List[str]] = Field(description="度量字段")
    identifiers: Dict[str, List[str]] = Field(description="标识字段")
    timestamps: Dict[str, List[str]] = Field(description="时间字段")

class SQLResult(BaseModel):
    """SQL 生成结果"""
    sql: str
    confidence: float = Field(ge=0, le=1)
    tables_used: List[str]
    explanation: str
    complexity: str = Field(pattern="^(simple|medium|complex)$")
```

### 2.4 工具实现

```python
# tools/database_tools.py
from langchain.tools import BaseTool
from langchain.sql_database import SQLDatabase
from pydantic import BaseModel, Field
from typing import Type, Dict, Any
from models.schemas import TableInfo

class SchemaExtractionTool(BaseTool):
    """数据库 Schema 提取工具"""
    
    name = "extract_database_schema"
    description = "提取数据库的表结构信息，包括表名、列信息、主键、外键等"
    
    class InputSchema(BaseModel):
        database_name: str = Field(description="数据库名称")
    
    args_schema: Type[BaseModel] = InputSchema
    
    db: SQLDatabase = Field(exclude=True)
    
    def _run(self, database_name: str) -> Dict[str, Any]:
        """执行 Schema 提取"""
        try:
            # 获取所有表
            tables = self.db.get_usable_table_names()
            
            # 获取表信息
            table_info_list = []
            for table in tables:
                # 获取表的 DDL
                table_info = self.db.get_table_info_no_throw([table])
                
                # 构建表信息
                table_data = {
                    "name": table,
                    "ddl": table_info,
                    "columns": self._get_columns(table)
                }
                table_info_list.append(table_data)
            
            return {
                "success": True,
                "database": database_name,
                "table_count": len(tables),
                "tables": table_info_list,
                "formatted_schema": self._format_schema(table_info_list)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _get_columns(self, table_name: str) -> List[Dict[str, Any]]:
        """获取表的列信息"""
        # 使用 SQL 查询获取列信息
        query = f"""
        SELECT 
            COLUMN_NAME,
            DATA_TYPE,
            IS_NULLABLE,
            COLUMN_DEFAULT,
            COLUMN_COMMENT
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = '{table_name}'
        ORDER BY ORDINAL_POSITION
        """
        
        result = self.db.run_no_throw(query)
        
        # 解析结果
        columns = []
        if result:
            lines = result.strip().split('\n')[1:]  # 跳过标题行
            for line in lines:
                parts = line.split('\t')
                if len(parts) >= 5:
                    columns.append({
                        "name": parts[0],
                        "type": parts[1],
                        "nullable": parts[2] == 'YES',
                        "default": parts[3] if parts[3] != 'NULL' else None,
                        "comment": parts[4] if len(parts) > 4 else None
                    })
        
        return columns
    
    def _format_schema(self, tables: List[Dict[str, Any]]) -> str:
        """格式化 Schema 信息"""
        lines = []
        for table in tables:
            lines.append(f"Table: {table['name']}")
            for col in table['columns']:
                nullable = "NULL" if col['nullable'] else "NOT NULL"
                lines.append(f"  - {col['name']}: {col['type']} {nullable}")
            lines.append("")
        
        return "\n".join(lines)
```

### 2.5 LangGraph 工作流

```python
# agent/graph.py
from langgraph.graph import StateGraph, END
from typing import Dict, Any
from models.states import NL2SQLState
from agent.nodes import *

def create_nl2sql_graph() -> StateGraph:
    """创建 NL2SQL 工作流图"""
    
    # 创建状态图
    workflow = StateGraph(NL2SQLState)
    
    # 添加节点
    workflow.add_node("extract_schema", extract_schema_node)
    workflow.add_node("analyze_domain", analyze_domain_node)
    workflow.add_node("classify_fields", classify_fields_node)
    workflow.add_node("describe_tables", describe_tables_node)
    workflow.add_node("describe_columns", describe_columns_node)
    workflow.add_node("analyze_er", analyze_er_node)
    workflow.add_node("generate_scenario", generate_scenario_node)
    workflow.add_node("generate_sql", generate_sql_node)
    workflow.add_node("validate_sql", validate_sql_node)
    
    # 设置入口
    workflow.set_entry_point("extract_schema")
    
    # 添加边（顺序执行）
    workflow.add_edge("extract_schema", "analyze_domain")
    workflow.add_edge("analyze_domain", "classify_fields")
    workflow.add_edge("classify_fields", "describe_tables")
    workflow.add_edge("describe_tables", "describe_columns")
    workflow.add_edge("describe_columns", "analyze_er")
    workflow.add_edge("analyze_er", "generate_scenario")
    workflow.add_edge("generate_scenario", "generate_sql")
    workflow.add_edge("generate_sql", "validate_sql")
    workflow.add_edge("validate_sql", END)
    
    # 编译图
    return workflow.compile()
```

### 2.6 节点实现

```python
# agent/nodes.py
from typing import Dict, Any
from datetime import datetime
from tools.database_tools import SchemaExtractionTool
from utils.llm_client import get_llm
from utils.output_parser import StructuredOutputParser
from prompts.prompt_manager import PromptManager
from models.schemas import *

# 初始化提示词管理器
prompt_manager = PromptManager(Path("prompts/templates"))

def extract_schema_node(state: NL2SQLState) -> Dict[str, Any]:
    """提取数据库 Schema"""
    print(f"[{datetime.now()}] 正在提取数据库结构...")
    
    # 创建工具
    tool = SchemaExtractionTool(db=state["db"])
    
    # 执行提取
    result = tool._run(database_name=state["database_name"])
    
    if result["success"]:
        return {
            "schema_info": result,
            "table_count": result["table_count"],
            "current_step": "analyze_domain",
            "execution_steps": state["execution_steps"] + [{
                "step": "extract_schema",
                "status": "completed",
                "result": f"提取了 {result['table_count']} 个表"
            }]
        }
    else:
        return {
            "errors": state["errors"] + [result["error"]],
            "current_step": "error"
        }

def analyze_domain_node(state: NL2SQLState) -> Dict[str, Any]:
    """分析业务领域"""
    print(f"[{datetime.now()}] 正在分析业务领域...")
    
    # 构建提示词
    prompt = prompt_manager.get_chat_prompt(
        "domain_analysis",
        schema=state["schema_info"]["formatted_schema"],
        query=state["query"]
    )
    
    # 调用 LLM
    llm = get_llm()
    response = llm.invoke(prompt.format_messages())
    
    # 解析结果
    parser = StructuredOutputParser(DomainAnalysisResult, llm)
    result = parser.parse(response.content)
    
    return {
        "domain_analysis": result.dict(),
        "current_step": "classify_fields",
        "execution_steps": state["execution_steps"] + [{
            "step": "analyze_domain",
            "status": "completed",
            "result": f"识别领域: {result.domain}"
        }]
    }

def generate_sql_node(state: NL2SQLState) -> Dict[str, Any]:
    """生成 SQL"""
    print(f"[{datetime.now()}] 正在生成 SQL...")
    
    # 构建上下文
    context = {
        "query": state["query"],
        "schema": state["schema_info"]["formatted_schema"],
        "domain": state["domain_analysis"],
        "field_classification": state["field_classification"],
        "er_relations": state["er_relations"],
        "scenario": state["scenario"]
    }
    
    # 构建提示词
    prompt = prompt_manager.get_chat_prompt("sql_generation", **context)
    
    # 调用 LLM
    llm = get_llm()
    response = llm.invoke(prompt.format_messages())
    
    # 解析 SQL
    from utils.sql_parser import SQLOutputParser
    parser = SQLOutputParser(llm)
    result = parser.parse(response.content)
    
    return {
        "generated_sql": result.sql,
        "sql_explanation": result.explanation,
        "current_step": "validate_sql",
        "execution_steps": state["execution_steps"] + [{
            "step": "generate_sql",
            "status": "completed",
            "result": result.sql
        }]
    }
```

### 2.7 主智能体

```python
# agent/nl2sql_agent.py
from typing import Dict, Any
from langgraph.graph import StateGraph
from agent.graph import create_nl2sql_graph
from utils.database_connector import DatabaseConnector
from models.schemas import SQLResult, QueryRequest
from config.settings import settings

class NL2SQLAgent:
    """NL2SQL 智能体"""
    
    def __init__(self, db_config: Dict[str, Any] = None):
        """初始化智能体"""
        # 使用提供的配置或默认配置
        if db_config is None:
            db_config = {
                "host": settings.db_host,
                "port": settings.db_port,
                "user": settings.db_user,
                "password": settings.db_password,
                "database": settings.db_database
            }
        
        # 创建数据库连接
        self.db = DatabaseConnector.get_connection(db_config)
        
        # 创建工作流
        self.graph = create_nl2sql_graph()
    
    def generate_sql(self, query: str) -> SQLResult:
        """生成 SQL"""
        # 初始化状态
        initial_state = {
            "query": query,
            "database_name": self.db._engine.url.database,
            "db": self.db,
            "schema_info": None,
            "table_count": None,
            "domain_analysis": None,
            "field_classification": None,
            "table_descriptions": None,
            "column_descriptions": None,
            "er_relations": None,
            "scenario": None,
            "generated_sql": None,
            "sql_explanation": None,
            "current_step": "extract_schema",
            "execution_steps": [],
            "errors": []
        }
        
        # 运行工作流
        final_state = self.graph.invoke(initial_state)
        
        # 检查错误
        if final_state["errors"]:
            raise Exception(f"生成失败: {', '.join(final_state['errors'])}")
        
        # 构建结果
        return SQLResult(
            sql=final_state["generated_sql"],
            confidence=0.95,  # 可以根据实际情况计算
            tables_used=self._extract_tables(final_state["generated_sql"]),
            explanation=final_state["sql_explanation"],
            complexity=self._analyze_complexity(final_state["generated_sql"])
        )
    
    def _extract_tables(self, sql: str) -> List[str]:
        """从 SQL 中提取表名"""
        # 简单实现，实际可以使用 SQL 解析器
        import re
        pattern = r'FROM\s+(\w+)|JOIN\s+(\w+)'
        matches = re.findall(pattern, sql, re.IGNORECASE)
        tables = set()
        for match in matches:
            tables.update([t for t in match if t])
        return list(tables)
    
    def _analyze_complexity(self, sql: str) -> str:
        """分析 SQL 复杂度"""
        sql_upper = sql.upper()
        
        # 简单的复杂度判断
        if 'JOIN' in sql_upper:
            if sql_upper.count('JOIN') > 2:
                return "complex"
            return "medium"
        
        if any(keyword in sql_upper for keyword in ['GROUP BY', 'HAVING', 'UNION']):
            return "medium"
        
        return "simple"
```

### 2.8 命令行接口

```python
# cli.py
import argparse
from rich.console import Console
from rich.table import Table
from agent.nl2sql_agent import NL2SQLAgent
from config.settings import settings

console = Console()

def main():
    parser = argparse.ArgumentParser(description='NL2SQL 命令行工具')
    parser.add_argument('query', help='自然语言查询')
    parser.add_argument('--model', default=settings.model_name, help='模型名称')
    parser.add_argument('--api-key', default=settings.api_key, help='API Key')
    parser.add_argument('--base-url', default=settings.base_url, help='API Base URL')
    parser.add_argument('--host', default=settings.db_host, help='数据库主机')
    parser.add_argument('--port', type=int, default=settings.db_port, help='数据库端口')
    parser.add_argument('--user', default=settings.db_user, help='数据库用户')
    parser.add_argument('--password', default=settings.db_password, help='数据库密码')
    parser.add_argument('--database', default=settings.db_database, help='数据库名')
    
    args = parser.parse_args()
    
    # 更新配置
    settings.model_name = args.model
    settings.api_key = args.api_key
    settings.base_url = args.base_url
    
    # 数据库配置
    db_config = {
        "host": args.host,
        "port": args.port,
        "user": args.user,
        "password": args.password,
        "database": args.database
    }
    
    try:
        # 创建智能体
        console.print("[bold blue]正在初始化智能体...[/bold blue]")
        agent = NL2SQLAgent(db_config)
        
        # 生成 SQL
        console.print(f"\n[bold green]查询:[/bold green] {args.query}")
        result = agent.generate_sql(args.query)
        
        # 显示结果
        console.print(f"\n[bold cyan]生成的 SQL:[/bold cyan]")
        console.print(result.sql, style="yellow")
        
        # 显示详细信息
        table = Table(title="执行详情")
        table.add_column("属性", style="cyan")
        table.add_column("值", style="magenta")
        
        table.add_row("置信度", f"{result.confidence:.2%}")
        table.add_row("复杂度", result.complexity)
        table.add_row("使用的表", ", ".join(result.tables_used))
        
        console.print("\n", table)
        
        if result.explanation:
            console.print(f"\n[bold]解释:[/bold] {result.explanation}")
            
    except Exception as e:
        console.print(f"[bold red]错误:[/bold red] {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
```

## 3. 使用示例

### 3.1 基础使用

```python
# examples/basic_usage.py
from agent.nl2sql_agent import NL2SQLAgent

# 创建智能体
agent = NL2SQLAgent({
    "host": "192.168.200.216",
    "port": 13306,
    "user": "testuser",
    "password": "testpass",
    "database": "testdb"
})

# 生成 SQL
queries = [
    "查询所有员工的信息",
    "统计每个部门的平均工资",
    "找出销售额最高的10个产品"
]

for query in queries:
    print(f"\n查询: {query}")
    result = agent.generate_sql(query)
    print(f"SQL: {result.sql}")
    print(f"置信度: {result.confidence:.2%}")
    print(f"复杂度: {result.complexity}")
```

### 3.2 命令行使用

```bash
# 使用默认配置
python -m cli "查询所有订单信息"

# 指定数据库
python -m cli "统计每月销售额" \
  --host 192.168.200.216 \
  --port 13306 \
  --user testuser \
  --password testpass \
  --database testdb

# 使用 vLLM 服务
python -m cli "查询库存不足的产品" \
  --model Qwen3-14B \
  --api-key not-needed \
  --base-url http://192.168.200.216:9009/v1
```

## 4. 提示词模板示例

```text
# prompts/templates/sql_generation_system.txt
你是一个 MySQL 数据库专家，擅长将自然语言查询转换为高效的 SQL 语句。

数据库 Schema:
{schema}

业务领域信息:
{domain}

字段分类:
{field_classification}

实体关系:
{er_relations}

查询场景:
{scenario}

请根据以下自然语言查询生成 SQL:
{query}

要求:
1. SQL 语句必须符合 MySQL 语法
2. 使用合适的 JOIN 类型
3. 添加必要的 WHERE 条件
4. 考虑性能优化
5. 结果按照业务逻辑排序

输出格式:
```sql
[SQL语句]
```

解释: [简要说明 SQL 的逻辑]
```

## 5. 注意事项

1. **环境变量**：确保正确设置 `.env` 文件
2. **数据库权限**：用户需要有读取 `information_schema` 的权限
3. **模型兼容性**：确保 vLLM 服务正常运行
4. **内存使用**：大型数据库可能需要更多内存

## 6. 调试技巧

```python
# 启用 LangChain 调试
import langchain
langchain.debug = True

# 查看中间状态
from langgraph.graph import StateGraph

# 在节点中添加打印
def debug_node(state):
    print(f"Current state: {state.keys()}")
    return state
```