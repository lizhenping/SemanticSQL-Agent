# SemanticSQL-Agent 核心组件设计规范（LangChain & LangGraph）

## 1. 状态和模型定义

### 1.1 LangGraph 状态定义

```python
# models/states.py
from typing import TypedDict, List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime

# LangGraph 状态 - 使用 TypedDict
class NL2SQLState(TypedDict):
    """工作流状态定义"""
    # 基础信息
    query: str
    database_name: str
    timestamp: str
    
    # Schema 信息
    schema_info: Optional[Dict[str, Any]]
    table_count: Optional[int]
    
    # 分析结果
    domain_analysis: Optional[Dict[str, Any]]
    field_classification: Optional[Dict[str, Any]]
    table_descriptions: Optional[Dict[str, List[str]]]
    column_descriptions: Optional[Dict[str, Dict[str, str]]]
    er_relations: Optional[List[Dict[str, Any]]]
    
    # 生成结果
    scenario: Optional[Dict[str, Any]]
    generated_sql: Optional[str]
    sql_explanation: Optional[str]
    
    # 执行追踪
    current_step: str
    execution_steps: List[Dict[str, Any]]
    errors: List[str]
    
# 步骤状态枚举
StepStatus = Literal["pending", "running", "completed", "failed"]
```

### 1.2 Pydantic 模型定义（格式化输入输出）

```python
# models/schemas.py
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional

class DatabaseConfig(BaseModel):
    """数据库配置模型"""
    host: str = Field(description="数据库主机地址")
    port: int = Field(default=3306, description="数据库端口")
    user: str = Field(description="数据库用户名")
    password: str = Field(description="数据库密码")
    database: str = Field(description="数据库名称")
    
    @validator('port')
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError('端口必须在 1-65535 之间')
        return v

class QueryRequest(BaseModel):
    """查询请求模型"""
    query: str = Field(description="自然语言查询")
    database: str = Field(description="目标数据库")
    options: Dict[str, Any] = Field(default_factory=dict)
    
class TableInfo(BaseModel):
    """表信息模型"""
    name: str
    comment: Optional[str] = None
    row_count: Optional[int] = None
    columns: List['ColumnInfo'] = []
    primary_key: Optional[List[str]] = None
    foreign_keys: List[Dict[str, Any]] = []

class ColumnInfo(BaseModel):
    """列信息模型"""
    name: str
    data_type: str
    nullable: bool = True
    default: Optional[Any] = None
    comment: Optional[str] = None
    is_primary: bool = False
    is_foreign: bool = False

class SQLResult(BaseModel):
    """SQL 生成结果模型"""
    sql: str = Field(description="生成的 SQL 语句")
    confidence: float = Field(ge=0, le=1, description="置信度分数")
    tables_used: List[str] = Field(description="使用的表")
    explanation: str = Field(description="SQL 解释")
    complexity: str = Field(description="复杂度: simple/medium/complex")
    execution_plan: List[Dict[str, Any]] = Field(default_factory=list)
    
class StepResult(BaseModel):
    """步骤执行结果"""
    step_name: str
    status: StepStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
```

## 2. LangChain 工具规范

### 2.1 基础工具类

```python
# tools/base.py
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, Optional
from abc import abstractmethod

class BaseNL2SQLTool(BaseTool):
    """NL2SQL 工具基类"""
    
    # 工具元数据
    return_direct: bool = False
    
    # 输入模式
    args_schema: Type[BaseModel] = None
    
    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述"""
        pass
    
    def _run(self, **kwargs) -> Dict[str, Any]:
        """同步执行"""
        try:
            result = self.execute(**kwargs)
            return self.format_output(result)
        except Exception as e:
            return {"error": str(e), "success": False}
    
    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """执行具体逻辑"""
        pass
    
    def format_output(self, result: Any) -> Dict[str, Any]:
        """格式化输出"""
        return {"result": result, "success": True}
```

### 2.2 数据库工具实现

```python
# tools/database_tools.py
from langchain.sql_database import SQLDatabase
from langchain.tools.sql_database.tool import (
    InfoSQLDatabaseTool,
    ListSQLDatabaseTool,
    QuerySQLDatabaseTool
)

class SchemaExtractionTool(BaseNL2SQLTool):
    """Schema 提取工具"""
    
    name = "extract_database_schema"
    description = "提取数据库完整的表结构信息"
    
    # 输入参数定义
    class InputSchema(BaseModel):
        database_name: str = Field(description="数据库名称")
        include_stats: bool = Field(default=True, description="是否包含统计信息")
    
    args_schema = InputSchema
    db: SQLDatabase = Field(exclude=True)
    
    def execute(self, database_name: str, include_stats: bool = True) -> Dict[str, Any]:
        """提取 schema"""
        # 使用 LangChain SQL 工具
        info_tool = InfoSQLDatabaseTool(db=self.db)
        list_tool = ListSQLDatabaseTool(db=self.db)
        
        tables = list_tool._run()
        schema_info = info_tool._run(tables)
        
        # 格式化结果
        result = {
            "database": database_name,
            "tables": self._parse_tables(tables),
            "schema_ddl": schema_info,
            "statistics": {}
        }
        
        if include_stats:
            result["statistics"] = self._get_statistics()
            
        return result
    
    def _parse_tables(self, tables_str: str) -> List[str]:
        """解析表列表"""
        return [t.strip() for t in tables_str.split(",")]
    
    def _get_statistics(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        query_tool = QuerySQLDatabaseTool(db=self.db)
        
        # 获取表行数
        stats = {}
        for table in self.db.get_usable_table_names():
            try:
                result = query_tool._run(f"SELECT COUNT(*) as cnt FROM {table}")
                stats[table] = {"row_count": int(result.split()[0])}
            except:
                stats[table] = {"row_count": -1}
                
        return stats
```

## 3. 提示词模板管理

### 3.1 模板管理器

```python
# prompts/prompt_manager.py
from langchain.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    PromptTemplate
)
from langchain.prompts.few_shot import FewShotPromptTemplate
from pathlib import Path
import yaml

class PromptManager:
    """提示词模板管理器"""
    
    def __init__(self, template_dir: Path):
        self.template_dir = template_dir
        self.templates = {}
        self.examples = {}
        self._load_examples()
    
    def _load_examples(self):
        """加载示例数据"""
        examples_file = self.template_dir / "examples.yaml"
        if examples_file.exists():
            with open(examples_file, 'r', encoding='utf-8') as f:
                self.examples = yaml.safe_load(f)
    
    def get_chat_prompt(self, name: str, **kwargs) -> ChatPromptTemplate:
        """获取聊天提示词模板"""
        if name not in self.templates:
            self.templates[name] = self._load_chat_template(name)
        
        return self.templates[name].partial(**kwargs)
    
    def get_few_shot_prompt(self, name: str, examples_key: str) -> FewShotPromptTemplate:
        """获取少样本提示词模板"""
        example_prompt = PromptTemplate(
            input_variables=["input", "output"],
            template="Input: {input}\nOutput: {output}"
        )
        
        examples = self.examples.get(examples_key, [])
        
        return FewShotPromptTemplate(
            examples=examples,
            example_prompt=example_prompt,
            prefix=self._load_template_string(f"{name}_prefix.txt"),
            suffix=self._load_template_string(f"{name}_suffix.txt"),
            input_variables=["query"]
        )
    
    def _load_chat_template(self, name: str) -> ChatPromptTemplate:
        """加载聊天模板"""
        system_template = self._load_template_string(f"{name}_system.txt")
        human_template = self._load_template_string(f"{name}_human.txt")
        
        return ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_template),
            HumanMessagePromptTemplate.from_template(human_template)
        ])
    
    def _load_template_string(self, filename: str) -> str:
        """加载模板字符串"""
        file_path = self.template_dir / filename
        if not file_path.exists():
            raise FileNotFoundError(f"模板文件不存在: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
```

### 3.2 模板示例

```text
# prompts/templates/schema_analysis_system.txt
你是一个数据库专家，擅长分析数据库结构和业务逻辑。

你的任务是分析给定的数据库 schema，理解其业务含义和数据关系。

分析时请注意：
1. 识别核心业务实体
2. 理解表之间的关系
3. 推断业务逻辑和规则
4. 发现潜在的数据质量问题

请以结构化的格式输出分析结果。
```

## 4. 输出解析器

### 4.1 基础解析器

```python
# utils/output_parser.py
from langchain.output_parsers import (
    PydanticOutputParser,
    OutputFixingParser,
    RetryOutputParser
)
from langchain.schema import OutputParserException
from typing import Type, TypeVar, Generic
import json
import re

T = TypeVar('T', bound=BaseModel)

class StructuredOutputParser(Generic[T]):
    """结构化输出解析器"""
    
    def __init__(self, pydantic_model: Type[T], llm=None):
        self.pydantic_model = pydantic_model
        self.base_parser = PydanticOutputParser(pydantic_object=pydantic_model)
        
        # 添加修复和重试能力
        if llm:
            self.fixing_parser = OutputFixingParser.from_llm(
                parser=self.base_parser,
                llm=llm
            )
            self.retry_parser = RetryOutputParser.from_llm(
                parser=self.base_parser,
                llm=llm
            )
        else:
            self.fixing_parser = None
            self.retry_parser = None
    
    def parse(self, text: str) -> T:
        """解析输出"""
        try:
            # 尝试提取 JSON
            json_str = self._extract_json(text)
            if json_str:
                return self.pydantic_model.parse_raw(json_str)
            
            # 使用基础解析器
            return self.base_parser.parse(text)
            
        except OutputParserException as e:
            # 尝试修复
            if self.fixing_parser:
                try:
                    return self.fixing_parser.parse(text)
                except:
                    pass
            
            # 尝试重试
            if self.retry_parser:
                try:
                    return self.retry_parser.parse_with_prompt(text)
                except:
                    pass
            
            raise e
    
    def _extract_json(self, text: str) -> Optional[str]:
        """从文本中提取 JSON"""
        # 查找 JSON 代码块
        json_pattern = r'```json\s*(.*?)\s*```'
        matches = re.findall(json_pattern, text, re.DOTALL)
        if matches:
            return matches[0]
        
        # 查找大括号包围的内容
        brace_pattern = r'\{[^{}]*\}'
        matches = re.findall(brace_pattern, text)
        if matches:
            return matches[-1]  # 返回最后一个
        
        return None
```

### 4.2 SQL 专用解析器

```python
# utils/sql_parser.py
class SQLOutputParser(StructuredOutputParser[SQLResult]):
    """SQL 输出专用解析器"""
    
    def __init__(self, llm=None):
        super().__init__(SQLResult, llm)
    
    def parse(self, text: str) -> SQLResult:
        """解析 SQL 输出"""
        # 提取 SQL 语句
        sql = self._extract_sql(text)
        if not sql:
            raise OutputParserException("未找到有效的 SQL 语句")
        
        # 尝试结构化解析
        try:
            return super().parse(text)
        except:
            # 降级处理：手动构建
            return SQLResult(
                sql=sql,
                confidence=self._extract_confidence(text),
                tables_used=self._extract_tables(sql),
                explanation=self._extract_explanation(text),
                complexity=self._analyze_complexity(sql),
                execution_plan=[]
            )
    
    def _extract_sql(self, text: str) -> Optional[str]:
        """提取 SQL 语句"""
        # 查找 SQL 代码块
        sql_pattern = r'```sql\s*(.*?)\s*```'
        matches = re.findall(sql_pattern, text, re.DOTALL | re.IGNORECASE)
        if matches:
            return matches[0].strip()
        
        # 查找 SELECT/INSERT/UPDATE/DELETE 语句
        sql_keywords = r'(SELECT|INSERT|UPDATE|DELETE)\s+.*?;'
        matches = re.findall(sql_keywords, text, re.DOTALL | re.IGNORECASE)
        if matches:
            return matches[0]
        
        return None
```

## 5. LangGraph 节点实现

### 5.1 节点函数规范

```python
# agent/nodes.py
from typing import Dict, Any
from langchain.schema import HumanMessage, SystemMessage

def extract_schema_node(state: NL2SQLState) -> Dict[str, Any]:
    """Schema 提取节点"""
    # 记录步骤
    step_result = StepResult(
        step_name="extract_schema",
        status="running",
        start_time=datetime.now()
    )
    
    try:
        # 获取工具
        tool = SchemaExtractionTool(db=state["db"])
        
        # 执行
        result = tool._run(
            database_name=state["database_name"],
            include_stats=True
        )
        
        # 更新状态
        step_result.status = "completed"
        step_result.result = result
        
        return {
            "schema_info": result,
            "table_count": len(result["tables"]),
            "execution_steps": state["execution_steps"] + [step_result.dict()],
            "current_step": "analyze_domain"
        }
        
    except Exception as e:
        step_result.status = "failed"
        step_result.error = str(e)
        
        return {
            "errors": state["errors"] + [str(e)],
            "execution_steps": state["execution_steps"] + [step_result.dict()],
            "current_step": "error"
        }

def analyze_domain_node(state: NL2SQLState) -> Dict[str, Any]:
    """领域分析节点"""
    # 构建提示词
    prompt = prompt_manager.get_chat_prompt(
        "domain_analysis",
        schema=state["schema_info"],
        query=state["query"]
    )
    
    # 调用 LLM
    llm = get_llm()
    response = llm(prompt.format_messages())
    
    # 解析输出
    parser = StructuredOutputParser(DomainAnalysisResult)
    result = parser.parse(response.content)
    
    return {
        "domain_analysis": result.dict(),
        "current_step": "classify_fields"
    }
```

## 6. 数据库连接管理

```python
# utils/database_connector.py
from langchain.sql_database import SQLDatabase
from sqlalchemy import create_engine, pool
from typing import Dict, Any, Optional
import pymysql

class DatabaseConnector:
    """数据库连接管理器"""
    
    _instances: Dict[str, SQLDatabase] = {}
    
    @classmethod
    def get_connection(cls, config: DatabaseConfig) -> SQLDatabase:
        """获取数据库连接（单例模式）"""
        key = f"{config.host}:{config.port}/{config.database}"
        
        if key not in cls._instances:
            cls._instances[key] = cls._create_connection(config)
        
        return cls._instances[key]
    
    @classmethod
    def _create_connection(cls, config: DatabaseConfig) -> SQLDatabase:
        """创建新的数据库连接"""
        # 构建连接字符串
        connection_string = cls._build_connection_string(config)
        
        # 创建引擎
        engine = create_engine(
            connection_string,
            poolclass=pool.NullPool,  # 禁用连接池
            connect_args={
                "charset": "utf8mb4",
                "connect_timeout": 10
            }
        )
        
        # 创建 SQLDatabase 实例
        db = SQLDatabase(engine)
        
        # 测试连接
        db.run("SELECT 1")
        
        return db
    
    @classmethod
    def _build_connection_string(cls, config: DatabaseConfig) -> str:
        """构建连接字符串"""
        # 目前只支持 MySQL
        return (
            f"mysql+pymysql://{config.user}:{config.password}@"
            f"{config.host}:{config.port}/{config.database}"
        )
    
    @classmethod
    def close_all(cls):
        """关闭所有连接"""
        for db in cls._instances.values():
            if hasattr(db, '_engine'):
                db._engine.dispose()
        cls._instances.clear()
```

## 7. LLM 客户端配置

```python
# utils/llm_client.py
from langchain.chat_models import ChatOpenAI
from langchain.llms import OpenAI
from typing import Optional

def get_llm(model_name: Optional[str] = None):
    """获取 LLM 实例"""
    settings = Settings()
    
    # 支持 vLLM 服务
    return ChatOpenAI(
        model_name=model_name or settings.model_name,
        openai_api_key=settings.api_key,
        openai_api_base=settings.base_url,
        temperature=settings.temperature,
        max_tokens=2048,
        request_timeout=30
    )
```

## 8. 内存管理

```python
# agent/memory.py
from langchain.memory import ConversationSummaryBufferMemory
from langchain.schema import BaseMessage

class NL2SQLMemory:
    """对话记忆管理"""
    
    def __init__(self, llm):
        self.memory = ConversationSummaryBufferMemory(
            llm=llm,
            max_token_limit=2000,
            return_messages=True
        )
        
        # 查询历史
        self.query_history: List[Dict[str, Any]] = []
    
    def add_query(self, query: str, sql: str, success: bool):
        """添加查询记录"""
        self.query_history.append({
            "query": query,
            "sql": sql,
            "success": success,
            "timestamp": datetime.now()
        })
    
    def get_similar_queries(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """获取相似的历史查询"""
        # 简单的关键词匹配
        keywords = set(query.lower().split())
        
        scored_queries = []
        for hist in self.query_history:
            hist_keywords = set(hist["query"].lower().split())
            score = len(keywords & hist_keywords) / len(keywords)
            if score > 0.3:
                scored_queries.append((score, hist))
        
        # 按分数排序
        scored_queries.sort(key=lambda x: x[0], reverse=True)
        
        return [q[1] for q in scored_queries[:limit]]
```