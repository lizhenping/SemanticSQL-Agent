# SemanticSQL-Agent 架构设计文档（基于 LangChain SQL Agent）

## 1. 项目概述

SemanticSQL-Agent 是一个基于 LangChain 的 SQL 代理系统，参考 LangChain 官方的 SQL Agent 实现，并结合 nl2sql_pipeline 的分析流程，实现高质量的自然语言到 SQL 转换。

### 1.1 核心特性
- 使用 LangChain 的 `create_react_agent` 构建智能体
- 完整的数据库分析工具链
- 结构化的查询生成流程
- 支持专有名词检索和纠正
- 记忆和会话管理

### 1.2 技术栈
- **LangChain**: 智能体框架和工具系统
- **LangGraph**: 用于带审核的查询流程（可选）
- **SQLAlchemy**: 数据库连接
- **Jinja2**: 提示词模板
- **Pydantic**: 数据验证

## 2. 架构层次设计

```
semanticsql-agent/
│
├── config/
│   ├── __init__.py
│   ├── settings.py              # 全局配置
│   └── database.py              # 数据库配置
│
├── models/
│   ├── __init__.py
│   ├── schemas.py               # Pydantic 模型定义
│   └── states.py                # 状态定义（用于 LangGraph）
│
├── tools/
│   ├── __init__.py
│   ├── base.py                  # 工具基类
│   │
│   ├── sql_tools/               # SQL 相关工具
│   │   ├── __init__.py
│   │   ├── query_tool.py        # 查询执行工具
│   │   ├── schema_tool.py       # Schema 查询工具
│   │   └── info_tool.py         # 数据库信息工具
│   │
│   ├── analysis_tools/          # 分析工具
│   │   ├── __init__.py
│   │   ├── schema_extraction_tool.py    # 数据库结构提取
│   │   ├── domain_analysis_tool.py      # 领域分析
│   │   ├── field_classification_tool.py # 字段分类
│   │   ├── table_description_tool.py    # 表描述
│   │   ├── column_description_tool.py   # 列描述
│   │   └── er_analysis_tool.py          # 实体关系分析
│   │
│   ├── generation_tools/        # 生成工具
│   │   ├── __init__.py
│   │   ├── scenario_generation_tool.py  # 场景生成
│   │   └── sql_generation_tool.py       # SQL 生成
│   │
│   ├── validation_tools/        # 验证工具
│   │   ├── __init__.py
│   │   ├── sql_validation_tool.py       # SQL 验证
│   │   └── semantic_check_tool.py       # 语义检查
│   │
│   ├── retrieval_tools/         # 检索工具
│   │   ├── __init__.py
│   │   └── proper_noun_tool.py          # 专有名词检索
│   │
│   └── thinking_tools/          # 思考工具
│       ├── __init__.py
│       └── sequential_thinking_tool.py   # 深度思考
│
├── prompts/
│   ├── __init__.py
│   ├── templates/               # Jinja2 模板
│   │   ├── system/             # 系统提示词
│   │   ├── tools/              # 工具描述
│   │   └── analysis/           # 分析提示词
│   └── manager.py               # 提示词管理器
│
├── agent/
│   ├── __init__.py
│   ├── sql_agent.py             # 主 SQL Agent
│   ├── query_chain.py           # 查询链（LangGraph）
│   ├── callbacks.py             # 回调处理
│   └── memory.py                # 记忆管理
│
├── utils/
│   ├── __init__.py
│   ├── database.py              # 数据库连接管理
│   ├── embeddings.py            # 嵌入管理
│   ├── trajectory.py            # 轨迹记录
│   └── parser.py                # 输出解析
│
└── cli.py                       # 命令行接口
```

## 3. 核心组件设计

### 3.1 SQL Agent 实现（基于 LangChain 示例）

```python
# agent/sql_agent.py
from langchain.agents import create_react_agent
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_core.prompts import ChatPromptTemplate
from langgraph.checkpoint.memory import MemorySaver
from typing import List, Dict, Any

class SemanticSQLAgent:
    """基于 LangChain 的 SQL Agent"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # 初始化数据库连接
        self.db = SQLDatabase.from_uri(self._build_connection_uri())
        
        # 初始化 LLM
        self.llm = self._init_llm()
        
        # 初始化记忆
        self.memory = MemorySaver()
        
        # 创建工具
        self.tools = self._create_tools()
        
        # 创建智能体
        self.agent = self._create_agent()
    
    def _build_connection_uri(self) -> str:
        """构建数据库连接 URI"""
        db_config = self.config["database"]
        return (
            f"mysql+pymysql://{db_config['user']}:{db_config['password']}@"
            f"{db_config['host']}:{db_config['port']}/{db_config['database']}"
        )
    
    def _init_llm(self):
        """初始化 LLM"""
        from langchain.chat_models import init_chat_model
        
        return init_chat_model(
            self.config["model"]["name"],
            model_provider=self.config["model"].get("provider", "openai"),
            api_key=self.config["model"]["api_key"],
            base_url=self.config["model"].get("base_url")
        )
    
    def _create_tools(self) -> List:
        """创建工具集合"""
        tools = []
        
        # 1. SQL 基础工具包
        toolkit = SQLDatabaseToolkit(db=self.db, llm=self.llm)
        tools.extend(toolkit.get_tools())
        
        # 2. 添加自定义分析工具
        from tools.analysis_tools import (
            SchemaExtractionTool,
            DomainAnalysisTool,
            FieldClassificationTool,
            TableDescriptionTool,
            ColumnDescriptionTool,
            ERAnalysisTool
        )
        
        analysis_tools = [
            SchemaExtractionTool(db=self.db),
            DomainAnalysisTool(llm=self.llm),
            FieldClassificationTool(db=self.db, llm=self.llm),
            TableDescriptionTool(db=self.db, llm=self.llm),
            ColumnDescriptionTool(db=self.db, llm=self.llm),
            ERAnalysisTool(db=self.db, llm=self.llm)
        ]
        tools.extend(analysis_tools)
        
        # 3. 添加验证工具
        from tools.validation_tools import (
            SQLValidationTool,
            SemanticCheckTool
        )
        
        validation_tools = [
            SQLValidationTool(db=self.db),
            SemanticCheckTool(llm=self.llm)
        ]
        tools.extend(validation_tools)
        
        # 4. 添加检索工具（用于专有名词）
        if self.config.get("enable_retrieval", True):
            from tools.retrieval_tools import ProperNounTool
            retrieval_tool = ProperNounTool(db=self.db, llm=self.llm)
            tools.append(retrieval_tool)
        
        # 5. 添加思考工具（可选）
        if self.config.get("enable_thinking", True):
            from tools.thinking_tools import SequentialThinkingTool
            thinking_tool = SequentialThinkingTool(llm=self.llm)
            tools.append(thinking_tool)
        
        return tools
    
    def _create_agent(self):
        """创建 React Agent"""
        # 系统提示词
        system_prompt = self._get_system_prompt()
        
        # 创建智能体
        return create_react_agent(
            self.llm,
            self.tools,
            prompt=system_prompt,
            checkpointer=self.memory
        )
    
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        from prompts.manager import PromptManager
        pm = PromptManager()
        
        return pm.get_system_prompt("sql_agent", 
            dialect=self.db.dialect,
            tables=self.db.get_usable_table_names()
        )
```

### 3.2 查询链实现（LangGraph）

```python
# agent/query_chain.py
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.tools.sql_database.tool import QuerySQLDatabaseTool

class QueryState(TypedDict):
    """查询状态"""
    question: str
    query: str
    result: str
    answer: str
    validated: bool

class QueryChain:
    """结构化的查询链"""
    
    def __init__(self, db, llm):
        self.db = db
        self.llm = llm
        self.query_tool = QuerySQLDatabaseTool(db=db)
        
    def create_chain(self, with_approval=False):
        """创建查询链"""
        # 构建状态图
        graph = StateGraph(QueryState)
        
        # 添加节点
        graph.add_node("analyze_schema", self.analyze_schema)
        graph.add_node("generate_query", self.generate_query)
        graph.add_node("validate_query", self.validate_query)
        graph.add_node("execute_query", self.execute_query)
        graph.add_node("generate_answer", self.generate_answer)
        
        # 添加边
        graph.add_edge(START, "analyze_schema")
        graph.add_edge("analyze_schema", "generate_query")
        graph.add_edge("generate_query", "validate_query")
        
        if with_approval:
            # 在执行前中断，等待人工审核
            graph.add_edge("validate_query", "execute_query")
            return graph.compile(interrupt_before=["execute_query"])
        else:
            graph.add_conditional_edges(
                "validate_query",
                self.should_execute,
                {
                    "execute": "execute_query",
                    "regenerate": "generate_query"
                }
            )
            graph.add_edge("execute_query", "generate_answer")
        
        return graph.compile()
    
    def analyze_schema(self, state: QueryState):
        """分析相关的数据库结构"""
        # 使用 LLM 分析问题涉及的表
        prompt = f"问题：{state['question']}\n\n请分析需要查询哪些表。"
        response = self.llm.invoke(prompt)
        
        # 这里可以调用 schema extraction tool
        return state
    
    def generate_query(self, state: QueryState):
        """生成 SQL 查询"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", "生成 SQL 查询来回答用户问题。"),
            ("user", "{question}")
        ])
        
        structured_llm = self.llm.with_structured_output({"query": str})
        result = structured_llm.invoke({"question": state["question"]})
        
        return {"query": result["query"]}
    
    def validate_query(self, state: QueryState):
        """验证 SQL 查询"""
        # 语法检查
        try:
            self.db.run(f"EXPLAIN {state['query']}")
            validated = True
        except Exception:
            validated = False
        
        return {"validated": validated}
    
    def should_execute(self, state: QueryState):
        """决定是否执行查询"""
        return "execute" if state["validated"] else "regenerate"
```

### 3.3 工具实现示例

```python
# tools/analysis_tools/schema_extraction_tool.py
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Dict, Any, List

class SchemaExtractionTool(BaseTool):
    """数据库结构提取工具"""
    
    name = "extract_database_schema"
    description = (
        "提取数据库的详细结构信息，包括表、列、索引、外键等。"
        "在开始分析前应该先使用此工具了解数据库结构。"
    )
    
    class InputSchema(BaseModel):
        tables: List[str] = Field(
            default=[],
            description="要提取的表名列表，为空则提取所有表"
        )
        include_indexes: bool = Field(
            default=False,
            description="是否包含索引信息"
        )
        include_samples: bool = Field(
            default=True,
            description="是否包含数据样例"
        )
    
    args_schema = InputSchema
    db: Any = Field(exclude=True)
    
    def _run(
        self, 
        tables: List[str] = [], 
        include_indexes: bool = False,
        include_samples: bool = True
    ) -> str:
        """执行 schema 提取"""
        # 获取表列表
        if not tables:
            tables = self.db.get_usable_table_names()
        
        output = [f"数据库包含 {len(tables)} 个表:\n"]
        
        for table in tables:
            output.append(f"\n=== 表: {table} ===")
            
            # 获取表信息
            table_info = self.db.get_table_info_no_throw([table])
            output.append(table_info)
            
            # 获取样例数据
            if include_samples:
                try:
                    samples = self.db.run(f"SELECT * FROM {table} LIMIT 3")
                    output.append(f"\n样例数据:\n{samples}")
                except Exception as e:
                    output.append(f"\n无法获取样例数据: {str(e)}")
            
            # 获取索引信息
            if include_indexes:
                try:
                    indexes = self.db.run(f"SHOW INDEX FROM {table}")
                    output.append(f"\n索引:\n{indexes}")
                except Exception:
                    pass
        
        return "\n".join(output)

# tools/validation_tools/sql_validation_tool.py
class SQLValidationTool(BaseTool):
    """SQL 验证工具"""
    
    name = "validate_sql_query"
    description = (
        "验证 SQL 查询的语法正确性和安全性。"
        "在执行查询前应该使用此工具验证。"
    )
    
    class InputSchema(BaseModel):
        sql: str = Field(description="要验证的 SQL 查询")
        check_semantics: bool = Field(
            default=True,
            description="是否检查语义正确性"
        )
    
    args_schema = InputSchema
    db: Any = Field(exclude=True)
    
    def _run(self, sql: str, check_semantics: bool = True) -> str:
        """验证 SQL"""
        results = []
        
        # 1. 检查是否包含危险操作
        dangerous_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER']
        for keyword in dangerous_keywords:
            if keyword in sql.upper():
                return f"❌ 错误：SQL 包含危险操作 {keyword}"
        
        # 2. 语法验证
        try:
            self.db.run(f"EXPLAIN {sql}")
            results.append("✅ 语法检查通过")
        except Exception as e:
            return f"❌ 语法错误：{str(e)}"
        
        # 3. 表和列存在性检查
        if check_semantics:
            # 提取表名
            import re
            table_pattern = r'FROM\s+`?(\w+)`?|JOIN\s+`?(\w+)`?'
            tables_in_sql = re.findall(table_pattern, sql, re.IGNORECASE)
            tables_in_sql = {t[0] or t[1] for t in tables_in_sql if t[0] or t[1]}
            
            available_tables = set(self.db.get_usable_table_names())
            invalid_tables = tables_in_sql - available_tables
            
            if invalid_tables:
                results.append(f"⚠️ 警告：以下表不存在：{invalid_tables}")
            else:
                results.append("✅ 所有表都存在")
        
        # 4. 性能提示
        if "SELECT *" in sql.upper():
            results.append("💡 建议：避免使用 SELECT *，只选择需要的列")
        
        if not any(keyword in sql.upper() for keyword in ["LIMIT", "TOP"]):
            results.append("💡 建议：考虑添加 LIMIT 子句限制返回行数")
        
        return "\n".join(results)

# tools/retrieval_tools/proper_noun_tool.py
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_community.agent_toolkits import create_retriever_tool

class ProperNounTool:
    """专有名词检索工具"""
    
    def __init__(self, db, llm, embedding_model="text-embedding-3-small"):
        self.db = db
        self.llm = llm
        self.embedding_model = embedding_model
        self._build_retriever()
    
    def _build_retriever(self):
        """构建检索器"""
        # 提取数据库中的专有名词
        proper_nouns = []
        
        # 获取所有表的唯一值
        for table in self.db.get_usable_table_names():
            # 智能识别名称类字段
            columns = self._identify_name_columns(table)
            for column in columns:
                try:
                    values = self.db.run(
                        f"SELECT DISTINCT {column} FROM {table} LIMIT 100"
                    )
                    proper_nouns.extend(self._parse_values(values))
                except Exception:
                    continue
        
        # 创建向量存储
        from langchain_openai import OpenAIEmbeddings
        embeddings = OpenAIEmbeddings(model=self.embedding_model)
        
        self.vector_store = InMemoryVectorStore(embeddings)
        self.vector_store.add_texts(list(set(proper_nouns)))
        
        self.retriever = self.vector_store.as_retriever(
            search_kwargs={"k": 5}
        )
    
    def _identify_name_columns(self, table: str) -> List[str]:
        """识别可能包含名称的列"""
        # 这里可以使用更智能的方法
        name_patterns = ['name', 'title', 'artist', 'album', 'customer']
        columns = []
        
        table_info = self.db.get_table_info_no_throw([table])
        for pattern in name_patterns:
            if pattern in table_info.lower():
                # 简单的模式匹配
                import re
                col_pattern = rf'(\w*{pattern}\w*)'
                matches = re.findall(col_pattern, table_info, re.IGNORECASE)
                columns.extend(matches)
        
        return columns
    
    def create_tool(self):
        """创建 LangChain 工具"""
        description = (
            "用于查找和纠正专有名词（如人名、产品名、公司名等）。"
            "输入拼写可能不准确的名称，返回数据库中最相似的正确名称。"
            "在构建涉及专有名词的查询前必须使用此工具。"
        )
        
        return create_retriever_tool(
            self.retriever,
            name="search_proper_nouns",
            description=description
        )
```

### 3.4 系统提示词模板

```jinja2
{# prompts/templates/system/sql_agent.j2 #}
你是一个专业的 SQL 数据库专家，负责帮助用户查询 {{ dialect }} 数据库。

## 核心职责
1. 理解用户的自然语言查询需求
2. 分析数据库结构
3. 生成准确、高效的 SQL 查询
4. 验证查询的正确性
5. 以清晰的方式返回结果

## 工作流程

### 1. 初始分析
- 总是先使用 `sql_db_list_tables` 查看可用的表
- 使用 `sql_db_schema` 查看相关表的结构
- 使用 `extract_database_schema` 获取更详细的信息（如需要）

### 2. 深入理解
- 使用 `domain_analysis` 理解业务领域
- 使用 `field_classification` 分类字段类型
- 使用 `er_analysis` 理解表关系

### 3. 查询生成
- 仔细构建 SQL 查询
- 只选择必要的列，避免 SELECT *
- 除非用户指定，否则限制结果为最多 {{ max_results | default(10) }} 行
- 使用合适的 JOIN 和 WHERE 条件

### 4. 验证和执行
- 使用 `validate_sql_query` 验证查询
- 如果涉及专有名词，使用 `search_proper_nouns` 查找正确的值
- 使用 `sql_db_query` 执行查询
- 如果出错，分析原因并重新生成

## 重要规则

1. **安全性**：绝不执行 DML 语句（INSERT, UPDATE, DELETE, DROP 等）
2. **准确性**：使用正确的表名和列名，不要猜测
3. **性能**：考虑查询效率，使用适当的索引
4. **专有名词**：对于人名、产品名等，总是先搜索确认

## 可用的表
{% for table in tables %}
- {{ table }}
{% endfor %}

## 输出格式
1. 解释你的分析思路
2. 展示生成的 SQL
3. 解释查询结果
4. 如有必要，提供额外的见解

现在，请帮助用户解答他们的数据库查询需求。
```

## 4. 使用流程

### 4.1 基础使用

```python
# 创建智能体
agent = SemanticSQLAgent(config)

# 执行查询
result = agent.query("查询销售额最高的10个产品")
```

### 4.2 带审核的查询

```python
# 创建带审核的查询链
chain = QueryChain(db, llm)
graph = chain.create_chain(with_approval=True)

# 执行到审核点
state = graph.invoke({"question": "删除所有订单"})

# 人工审核
if approve:
    final_state = graph.invoke(None, config)
```

### 4.3 完整的分析流程

```python
# 使用完整的分析工具链
config = {"configurable": {"thread_id": "analysis_001"}}

messages = [
    {"role": "user", "content": "分析数据库结构并生成月度销售报表的 SQL"}
]

for step in agent.stream({"messages": messages}, config):
    print(step)
```

## 5. 配置示例

```yaml
# config.yaml
model:
  name: "gpt-4"  # 或 "Qwen3-14B"
  provider: "openai"  # 或 "custom"
  api_key: "${OPENAI_API_KEY}"
  base_url: "https://api.openai.com/v1"  # 或自定义 URL

database:
  host: "localhost"
  port: 3306
  user: "root"
  password: "password"
  database: "test_db"

agent:
  max_results: 10
  enable_retrieval: true
  enable_thinking: true
  
memory:
  type: "buffer"
  max_token_limit: 2000
```

这个新设计：
1. **完全基于 LangChain 的 SQL Agent 示例**
2. **保留了完整的分析工具链**（参考原设计）
3. **支持 LangGraph 的查询链**（可选的审核流程）
4. **包含专有名词检索**（参考示例）
5. **清晰的工具分类和组织**