# SemanticSQL-Agent 架构设计文档（基于 LangChain & LangGraph）

## 1. 项目概述

SemanticSQL-Agent 是一个基于 LangChain 和 LangGraph 的自然语言到SQL转换系统，采用智能体架构和图工作流设计。

### 1.1 核心特性
- 基于 LangGraph 的状态图工作流
- LangChain 工具和提示词管理
- 格式化的输入输出（参考 nl2sql_pipeline）
- 支持本地模型（通过 vLLM）

### 1.2 技术栈
- **LangChain**: 工具、提示词模板、输出解析器
- **LangGraph**: 状态管理、工作流编排
- **LangChain SQL**: MySQL 数据库工具
- **Pydantic**: 数据验证和格式化

## 2. 架构层次设计

```
semanticsql-agent/
│
├── 配置层 (Configuration Layer)
│   └── config/
│       ├── __init__.py
│       ├── settings.py              # 全局配置
│       └── database.py              # 数据库配置
│
├── 模型层 (Models Layer) 
│   └── models/
│       ├── __init__.py
│       ├── states.py                # LangGraph 状态定义 (TypedDict/Pydantic)
│       ├── schemas.py               # 输入输出模式定义
│       └── database.py              # 数据库模型
│
├── 工具层 (Tools Layer)
│   └── tools/
│       ├── __init__.py
│       ├── base.py                  # LangChain Tool 基类
│       ├── database_tools.py        # 数据库相关工具
│       ├── analysis_tools.py        # 分析工具
│       └── generation_tools.py      # SQL生成工具
│
├── 提示词层 (Prompts Layer)
│   └── prompts/
│       ├── __init__.py
│       ├── templates/               # Jinja2 模板
│       │   ├── analysis/
│       │   └── generation/
│       └── prompt_manager.py        # LangChain PromptTemplate 管理
│
├── 智能体层 (Agent Layer)
│   └── agent/
│       ├── __init__.py
│       ├── graph.py                 # LangGraph 工作流定义
│       ├── nodes.py                 # 图节点实现
│       └── nl2sql_agent.py          # 主智能体类
│
├── 工具函数层 (Utils Layer)
│   └── utils/
│       ├── __init__.py
│       ├── database_connector.py    # 数据库连接管理
│       ├── llm_client.py           # LLM 客户端（支持 vLLM）
│       └── output_parser.py         # LangChain 输出解析器
│
└── 接口层 (Interface Layer)
    ├── cli.py                       # 命令行接口
    └── api.py                       # API 接口（可选）
```

## 3. 核心组件设计

### 3.1 状态定义（LangGraph）

```python
# models/states.py
from typing import TypedDict, List, Dict, Any, Optional
from pydantic import BaseModel

class NL2SQLState(TypedDict):
    """LangGraph 状态定义"""
    # 输入
    query: str
    database_config: Dict[str, Any]
    
    # 中间状态
    schema_info: Optional[Dict[str, Any]]
    domain_analysis: Optional[Dict[str, Any]]
    field_classification: Optional[Dict[str, Any]]
    table_descriptions: Optional[Dict[str, Any]]
    column_descriptions: Optional[Dict[str, Any]]
    er_analysis: Optional[Dict[str, Any]]
    scenario: Optional[Dict[str, Any]]
    
    # 输出
    generated_sql: Optional[str]
    confidence_score: Optional[float]
    execution_steps: List[Dict[str, Any]]
    error: Optional[str]

# 使用 Pydantic 定义格式化的输入输出
class QueryInput(BaseModel):
    """格式化的查询输入"""
    query: str
    database: str
    options: Dict[str, Any] = {}

class SQLOutput(BaseModel):
    """格式化的SQL输出"""
    sql: str
    confidence: float
    explanation: str
    tables_used: List[str]
    execution_plan: List[Dict[str, Any]]
```

### 3.2 LangChain 工具定义

```python
# tools/database_tools.py
from langchain.tools import BaseTool
from langchain.sql_database import SQLDatabase
from pydantic import Field

class SchemaExtractionTool(BaseTool):
    """数据库结构提取工具"""
    name = "schema_extraction"
    description = "提取数据库的表结构信息"
    
    db: SQLDatabase = Field(exclude=True)
    
    def _run(self, database_name: str) -> Dict[str, Any]:
        """同步执行"""
        return self.extract_schema()
    
    def extract_schema(self) -> Dict[str, Any]:
        """提取并格式化 schema 信息"""
        # 使用 LangChain SQLDatabase 功能
        table_info = self.db.get_table_info()
        tables = self.db.get_usable_table_names()
        
        return {
            "tables": tables,
            "schema": table_info,
            "formatted_output": self.format_schema(tables, table_info)
        }
```

### 3.3 提示词模板管理

```python
# prompts/prompt_manager.py
from langchain.prompts import PromptTemplate, ChatPromptTemplate
from langchain.prompts.prompt import PromptTemplate
from jinja2 import Environment, FileSystemLoader

class PromptManager:
    """统一的提示词模板管理"""
    
    def __init__(self, template_dir: str):
        self.jinja_env = Environment(loader=FileSystemLoader(template_dir))
        self.templates = {}
        
    def get_prompt(self, name: str, **kwargs) -> ChatPromptTemplate:
        """获取格式化的提示词模板"""
        if name not in self.templates:
            self.templates[name] = self._load_template(name)
        
        return self.templates[name].partial(**kwargs)
    
    def _load_template(self, name: str) -> ChatPromptTemplate:
        """加载 Jinja2 模板并转换为 LangChain 模板"""
        jinja_template = self.jinja_env.get_template(f"{name}.j2")
        template_str = jinja_template.render()
        
        return ChatPromptTemplate.from_template(template_str)
```

### 3.4 LangGraph 工作流定义

```python
# agent/graph.py
from langgraph.graph import StateGraph, END
from typing import Dict, Any

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
    workflow.add_node("format_output", format_output_node)
    
    # 定义边
    workflow.set_entry_point("extract_schema")
    workflow.add_edge("extract_schema", "analyze_domain")
    workflow.add_edge("analyze_domain", "classify_fields")
    workflow.add_edge("classify_fields", "describe_tables")
    workflow.add_edge("describe_tables", "describe_columns")
    workflow.add_edge("describe_columns", "analyze_er")
    workflow.add_edge("analyze_er", "generate_scenario")
    workflow.add_edge("generate_scenario", "generate_sql")
    workflow.add_edge("generate_sql", "format_output")
    workflow.add_edge("format_output", END)
    
    return workflow.compile()
```

## 4. 配置管理

```python
# config/settings.py
from pydantic import BaseSettings

class Settings(BaseSettings):
    """全局配置"""
    # LLM 配置
    model_name: str = "Qwen3-14B"
    api_key: str = "not-needed"
    base_url: str = "http://192.168.200.216:9009/v1"
    
    # 数据库配置
    db_host: str = "192.168.200.216"
    db_port: int = 13306
    db_user: str = "testuser"
    db_password: str = "testpass"
    db_database: str = "testdb"
    
    # Agent 配置
    max_steps: int = 15
    temperature: float = 0.1
    
    class Config:
        env_file = ".env"
```

## 5. 数据库连接器

```python
# utils/database_connector.py
from langchain.sql_database import SQLDatabase
from sqlalchemy import create_engine

class DatabaseConnector:
    """多数据库支持的连接器"""
    
    @staticmethod
    def create_connection(config: Dict[str, Any]) -> SQLDatabase:
        """创建数据库连接"""
        # 目前只支持 MySQL
        connection_string = (
            f"mysql+pymysql://{config['user']}:{config['password']}@"
            f"{config['host']}:{config['port']}/{config['database']}"
        )
        
        engine = create_engine(connection_string)
        return SQLDatabase(engine)
```

## 6. 输出解析器

```python
# utils/output_parser.py
from langchain.output_parsers import PydanticOutputParser
from langchain.schema import OutputParserException

class SQLOutputParser(PydanticOutputParser):
    """SQL 输出解析器"""
    
    pydantic_object = SQLOutput
    
    def parse(self, text: str) -> SQLOutput:
        """解析 LLM 输出为结构化数据"""
        try:
            # 提取 SQL
            sql = self.extract_sql(text)
            # 提取其他信息
            confidence = self.extract_confidence(text)
            explanation = self.extract_explanation(text)
            
            return SQLOutput(
                sql=sql,
                confidence=confidence,
                explanation=explanation,
                tables_used=self.extract_tables(sql),
                execution_plan=[]
            )
        except Exception as e:
            raise OutputParserException(f"解析失败: {str(e)}")
```

## 7. 主智能体实现

```python
# agent/nl2sql_agent.py
from langgraph.graph import StateGraph
from langchain.memory import ConversationBufferMemory

class NL2SQLAgent:
    """基于 LangGraph 的 NL2SQL 智能体"""
    
    def __init__(self, config: Settings):
        self.config = config
        self.graph = create_nl2sql_graph()
        self.memory = ConversationBufferMemory()
        self.db = DatabaseConnector.create_connection(config.dict())
        
    def run(self, query: str) -> SQLOutput:
        """执行 NL2SQL 转换"""
        # 初始化状态
        initial_state = {
            "query": query,
            "database_config": self.config.dict(),
            "execution_steps": []
        }
        
        # 运行工作流
        result = self.graph.invoke(initial_state)
        
        # 解析输出
        parser = SQLOutputParser()
        return parser.parse(result["generated_sql"])
```

## 8. 使用示例

```python
# 创建智能体
agent = NL2SQLAgent(Settings())

# 执行查询
result = agent.run("查询每个部门的平均工资")

# 格式化输出
print(f"SQL: {result.sql}")
print(f"置信度: {result.confidence}")
print(f"使用的表: {result.tables_used}")
```

## 9. 联系方式

作者：李振平 (lizhenping18@mails.ucas.ac.cn)