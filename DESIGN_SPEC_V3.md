# SemanticSQL-Agent 核心组件设计规范（基于 LangChain SQL Agent）

## 1. 数据模型定义

### 1.1 状态定义（用于 LangGraph）

```python
# models/states.py
from typing import TypedDict, List, Dict, Any, Optional
from typing_extensions import Annotated

class QueryState(TypedDict):
    """查询执行状态"""
    question: str
    query: str
    result: str
    answer: str
    validated: bool
    error: Optional[str]

class AnalysisState(TypedDict):
    """分析流程状态"""
    question: str
    schema_info: Dict[str, Any]
    domain_analysis: Dict[str, Any]
    field_classification: Dict[str, Any]
    er_relations: List[Dict[str, Any]]
    generated_sql: str
    validation_result: Dict[str, Any]
    final_answer: str
```

### 1.2 Pydantic 模型

```python
# models/schemas.py
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional
from enum import Enum

class FieldType(str, Enum):
    """字段类型枚举"""
    DIMENSION = "dimension"
    MEASURE = "measure"
    IDENTIFIER = "identifier"
    TIMESTAMP = "timestamp"
    DESCRIPTION = "description"

class TableInfo(BaseModel):
    """表信息模型"""
    name: str
    columns: List[Dict[str, Any]]
    row_count: Optional[int] = None
    comment: Optional[str] = None
    sample_data: Optional[List[Dict[str, Any]]] = None

class ColumnInfo(BaseModel):
    """列信息模型"""
    name: str
    data_type: str
    nullable: bool = True
    is_primary: bool = False
    is_foreign: bool = False
    foreign_key_ref: Optional[str] = None
    comment: Optional[str] = None
    field_type: Optional[FieldType] = None
    sample_values: Optional[List[Any]] = None

class DomainAnalysis(BaseModel):
    """领域分析结果"""
    domain: str = Field(description="业务领域")
    description: str = Field(description="领域描述")
    key_entities: List[str] = Field(description="关键实体")
    business_rules: List[str] = Field(description="业务规则")
    terminology: Dict[str, str] = Field(default_factory=dict)

class QueryOutput(BaseModel):
    """SQL 查询输出"""
    query: Annotated[str, Field(description="生成的 SQL 查询")]
    
class SQLValidationResult(BaseModel):
    """SQL 验证结果"""
    is_valid: bool
    syntax_check: bool
    semantic_check: bool
    safety_check: bool
    issues: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    
class QueryResult(BaseModel):
    """查询执行结果"""
    success: bool
    sql: Optional[str] = None
    result: Optional[List[Dict[str, Any]]] = None
    row_count: int = 0
    error: Optional[str] = None
    execution_time: Optional[float] = None
```

## 2. 工具基类设计

### 2.1 基础工具类

```python
# tools/base.py
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, Optional
from abc import abstractmethod
import time
import logging

logger = logging.getLogger(__name__)

class BaseSemanticSQLTool(BaseTool):
    """SemanticSQL 工具基类"""
    
    # 元数据
    category: str = Field(default="general", description="工具类别")
    priority: int = Field(default=0, description="工具优先级")
    
    # 共享资源
    db: Optional[Any] = Field(default=None, exclude=True)
    llm: Optional[Any] = Field(default=None, exclude=True)
    
    def _run(self, *args, **kwargs) -> str:
        """执行工具（包装器）"""
        start_time = time.time()
        tool_input = {**kwargs} if kwargs else {"args": args}
        
        try:
            logger.info(f"执行工具 {self.name}，输入: {tool_input}")
            result = self.execute(**tool_input)
            
            execution_time = time.time() - start_time
            logger.info(f"工具 {self.name} 执行成功，耗时: {execution_time:.2f}s")
            
            return self._format_output(result)
            
        except Exception as e:
            logger.error(f"工具 {self.name} 执行失败: {str(e)}")
            return f"工具执行失败: {str(e)}"
    
    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """执行具体逻辑（子类实现）"""
        pass
    
    def _format_output(self, result: Any) -> str:
        """格式化输出"""
        if isinstance(result, str):
            return result
        elif isinstance(result, dict):
            return self._dict_to_string(result)
        elif isinstance(result, list):
            return self._list_to_string(result)
        else:
            return str(result)
    
    def _dict_to_string(self, d: Dict[str, Any], indent: int = 0) -> str:
        """字典转字符串"""
        lines = []
        for key, value in d.items():
            prefix = "  " * indent
            if isinstance(value, dict):
                lines.append(f"{prefix}{key}:")
                lines.append(self._dict_to_string(value, indent + 1))
            elif isinstance(value, list):
                lines.append(f"{prefix}{key}: {self._list_to_string(value)}")
            else:
                lines.append(f"{prefix}{key}: {value}")
        return "\n".join(lines)
    
    def _list_to_string(self, lst: List[Any]) -> str:
        """列表转字符串"""
        if not lst:
            return "[]"
        if len(lst) <= 3:
            return str(lst)
        return f"[{lst[0]}, {lst[1]}, ... ({len(lst)} items)]"
```

## 3. SQL 工具实现

### 3.1 Schema 工具

```python
# tools/sql_tools/schema_tool.py
from tools.base import BaseSemanticSQLTool
from pydantic import BaseModel, Field
from typing import List, Optional

class SchemaQueryTool(BaseSemanticSQLTool):
    """数据库 Schema 查询工具"""
    
    name = "sql_db_schema"
    description = (
        "获取指定表的详细 schema 信息。"
        "输入表名列表，返回这些表的 CREATE TABLE 语句。"
        "在生成查询前应该使用此工具了解表结构。"
    )
    category = "sql"
    priority = 10
    
    class InputSchema(BaseModel):
        tables: List[str] = Field(
            description="要查询 schema 的表名列表"
        )
    
    args_schema = InputSchema
    
    def execute(self, tables: List[str]) -> Dict[str, Any]:
        """获取表 schema"""
        result = {
            "tables": {},
            "total_columns": 0
        }
        
        for table in tables:
            try:
                # 获取表信息
                table_info = self.db.get_table_info_no_throw([table])
                
                # 解析列信息
                columns = self._parse_columns(table_info)
                
                result["tables"][table] = {
                    "ddl": table_info,
                    "columns": columns,
                    "column_count": len(columns)
                }
                result["total_columns"] += len(columns)
                
            except Exception as e:
                result["tables"][table] = {"error": str(e)}
        
        return result
    
    def _parse_columns(self, table_info: str) -> List[Dict[str, str]]:
        """解析列信息"""
        columns = []
        lines = table_info.split('\n')
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('CREATE') and not line.startswith(')'):
                # 简单的列解析
                parts = line.split()
                if len(parts) >= 2:
                    col_name = parts[0].strip('`,"')
                    col_type = parts[1].strip(',')
                    columns.append({
                        "name": col_name,
                        "type": col_type
                    })
        
        return columns
```

### 3.2 查询执行工具

```python
# tools/sql_tools/query_tool.py
class QueryExecutionTool(BaseSemanticSQLTool):
    """SQL 查询执行工具"""
    
    name = "sql_db_query"
    description = (
        "执行 SQL 查询并返回结果。"
        "查询结果会被限制在合理的行数内。"
        "执行前请确保查询已经过验证。"
    )
    category = "sql"
    priority = 5
    
    class InputSchema(BaseModel):
        query: str = Field(description="要执行的 SQL 查询")
        limit: Optional[int] = Field(
            default=10,
            description="返回结果的最大行数"
        )
    
    args_schema = InputSchema
    
    def execute(self, query: str, limit: Optional[int] = 10) -> Dict[str, Any]:
        """执行查询"""
        try:
            # 添加 LIMIT 子句（如果没有）
            query_with_limit = self._add_limit(query, limit)
            
            # 执行查询
            result = self.db.run(query_with_limit)
            
            # 解析结果
            rows = self._parse_result(result)
            
            return {
                "success": True,
                "query": query_with_limit,
                "rows": rows,
                "row_count": len(rows),
                "limited": self._is_limited(query, len(rows), limit)
            }
            
        except Exception as e:
            return {
                "success": False,
                "query": query,
                "error": str(e)
            }
    
    def _add_limit(self, query: str, limit: int) -> str:
        """添加 LIMIT 子句"""
        query_upper = query.upper()
        if 'LIMIT' not in query_upper and limit:
            # 简单处理，实际应该用 SQL 解析器
            query = query.rstrip(';')
            query += f" LIMIT {limit}"
        return query
```

## 4. 分析工具实现

### 4.1 领域分析工具

```python
# tools/analysis_tools/domain_analysis_tool.py
from tools.base import BaseSemanticSQLTool
from models.schemas import DomainAnalysis

class DomainAnalysisTool(BaseSemanticSQLTool):
    """业务领域分析工具"""
    
    name = "analyze_business_domain"
    description = (
        "分析数据库的业务领域，识别关键实体和业务规则。"
        "这有助于更好地理解数据模型和生成准确的查询。"
    )
    category = "analysis"
    priority = 8
    
    class InputSchema(BaseModel):
        schema_info: Dict[str, Any] = Field(
            description="数据库 schema 信息"
        )
        user_query: Optional[str] = Field(
            default=None,
            description="用户的查询意图"
        )
    
    args_schema = InputSchema
    
    def execute(
        self, 
        schema_info: Dict[str, Any],
        user_query: Optional[str] = None
    ) -> Dict[str, Any]:
        """分析业务领域"""
        # 构建分析提示词
        from prompts.manager import PromptManager
        pm = PromptManager()
        
        prompt = pm.get_prompt(
            "analysis/domain_analysis",
            schema=schema_info,
            query=user_query
        )
        
        # 调用 LLM 分析
        response = self.llm.invoke(prompt)
        
        # 解析结果
        try:
            # 使用结构化输出
            structured_llm = self.llm.with_structured_output(DomainAnalysis)
            result = structured_llm.invoke(prompt)
            
            return {
                "domain": result.domain,
                "description": result.description,
                "key_entities": result.key_entities,
                "business_rules": result.business_rules,
                "terminology": result.terminology
            }
        except Exception:
            # 降级处理：从文本中提取
            return self._parse_text_response(response.content)
    
    def _parse_text_response(self, text: str) -> Dict[str, Any]:
        """从文本响应中提取信息"""
        # 简单的文本解析逻辑
        return {
            "domain": "未知",
            "description": text[:200],
            "key_entities": [],
            "business_rules": [],
            "terminology": {}
        }
```

### 4.2 字段分类工具

```python
# tools/analysis_tools/field_classification_tool.py
class FieldClassificationTool(BaseSemanticSQLTool):
    """字段分类工具"""
    
    name = "classify_table_fields"
    description = (
        "对表的字段进行分类，识别维度、度量、标识符等。"
        "这有助于理解数据结构和生成正确的聚合查询。"
    )
    category = "analysis"
    priority = 7
    
    class InputSchema(BaseModel):
        tables: List[str] = Field(
            description="要分类字段的表名列表"
        )
        sample_data: bool = Field(
            default=True,
            description="是否需要样本数据辅助分类"
        )
    
    args_schema = InputSchema
    
    def execute(
        self, 
        tables: List[str],
        sample_data: bool = True
    ) -> Dict[str, Any]:
        """执行字段分类"""
        result = {}
        
        for table in tables:
            # 获取表结构
            table_info = self.db.get_table_info_no_throw([table])
            
            # 获取样本数据
            samples = None
            if sample_data:
                try:
                    samples = self.db.run(f"SELECT * FROM {table} LIMIT 5")
                except Exception:
                    pass
            
            # 分类字段
            field_classes = self._classify_fields(table, table_info, samples)
            result[table] = field_classes
        
        return result
    
    def _classify_fields(
        self, 
        table: str, 
        schema: str, 
        samples: Optional[str]
    ) -> Dict[str, List[str]]:
        """分类字段"""
        # 构建提示词
        prompt = f"""
        分析表 {table} 的字段，将它们分类为：
        - dimensions（维度）: 用于分组的分类字段
        - measures（度量）: 可以聚合的数值字段
        - identifiers（标识符）: ID类字段
        - timestamps（时间戳）: 时间相关字段
        - descriptions（描述）: 文本描述字段
        
        表结构：
        {schema}
        
        样本数据：
        {samples if samples else '无'}
        
        请返回 JSON 格式的分类结果。
        """
        
        response = self.llm.invoke(prompt)
        
        # 解析 JSON 结果
        import json
        try:
            return json.loads(response.content)
        except Exception:
            # 降级处理
            return {
                "dimensions": [],
                "measures": [],
                "identifiers": [],
                "timestamps": [],
                "descriptions": []
            }
```

## 5. 验证工具实现

### 5.1 SQL 验证工具

```python
# tools/validation_tools/sql_validation_tool.py
from tools.base import BaseSemanticSQLTool
from models.schemas import SQLValidationResult

class SQLValidationTool(BaseSemanticSQLTool):
    """SQL 查询验证工具"""
    
    name = "validate_sql_query"
    description = (
        "验证 SQL 查询的语法、安全性和语义正确性。"
        "返回详细的验证结果和改进建议。"
    )
    category = "validation"
    priority = 9
    
    class InputSchema(BaseModel):
        sql: str = Field(description="要验证的 SQL 查询")
        context: Optional[Dict[str, Any]] = Field(
            default=None,
            description="查询上下文（如用户意图）"
        )
    
    args_schema = InputSchema
    
    def execute(
        self, 
        sql: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """验证 SQL"""
        validation = SQLValidationResult(
            is_valid=True,
            syntax_check=True,
            semantic_check=True,
            safety_check=True
        )
        
        # 1. 安全性检查
        safety_result = self._check_safety(sql)
        if not safety_result["safe"]:
            validation.safety_check = False
            validation.is_valid = False
            validation.issues.extend(safety_result["issues"])
            return validation.dict()
        
        # 2. 语法检查
        syntax_result = self._check_syntax(sql)
        if not syntax_result["valid"]:
            validation.syntax_check = False
            validation.is_valid = False
            validation.issues.extend(syntax_result["issues"])
            validation.suggestions.extend(syntax_result["suggestions"])
            return validation.dict()
        
        # 3. 语义检查
        if context:
            semantic_result = self._check_semantics(sql, context)
            if not semantic_result["valid"]:
                validation.semantic_check = False
                validation.issues.extend(semantic_result["issues"])
                validation.suggestions.extend(semantic_result["suggestions"])
        
        # 4. 性能建议
        perf_suggestions = self._get_performance_suggestions(sql)
        validation.suggestions.extend(perf_suggestions)
        
        return validation.dict()
    
    def _check_safety(self, sql: str) -> Dict[str, Any]:
        """安全性检查"""
        dangerous_keywords = [
            'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 
            'CREATE', 'TRUNCATE', 'GRANT', 'REVOKE'
        ]
        
        sql_upper = sql.upper()
        issues = []
        
        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                issues.append(f"包含危险操作: {keyword}")
        
        return {
            "safe": len(issues) == 0,
            "issues": issues
        }
    
    def _check_syntax(self, sql: str) -> Dict[str, Any]:
        """语法检查"""
        try:
            # 使用 EXPLAIN 检查语法
            self.db.run(f"EXPLAIN {sql}")
            return {"valid": True, "issues": [], "suggestions": []}
        except Exception as e:
            error_str = str(e)
            
            # 分析错误并提供建议
            suggestions = []
            if "Unknown column" in error_str:
                suggestions.append("检查列名是否正确，使用 sql_db_schema 工具查看表结构")
            elif "Table" in error_str and "doesn't exist" in error_str:
                suggestions.append("检查表名是否正确，使用 sql_db_list_tables 工具查看可用表")
            elif "syntax error" in error_str.lower():
                suggestions.append("检查 SQL 语法，特别是关键字拼写和标点符号")
            
            return {
                "valid": False,
                "issues": [f"语法错误: {error_str}"],
                "suggestions": suggestions
            }
    
    def _check_semantics(self, sql: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """语义检查"""
        # 使用 LLM 检查查询是否符合用户意图
        prompt = f"""
        用户查询: {context.get('user_query', '')}
        生成的SQL: {sql}
        
        请检查这个SQL是否正确回答了用户的问题。
        如果不正确，请指出问题并给出建议。
        """
        
        response = self.llm.invoke(prompt)
        
        # 简单的判断逻辑
        if "不正确" in response.content or "问题" in response.content:
            return {
                "valid": False,
                "issues": ["SQL 可能未正确回答用户问题"],
                "suggestions": [response.content[:200]]
            }
        
        return {"valid": True, "issues": [], "suggestions": []}
```

## 6. 检索工具实现

### 6.1 专有名词检索工具

```python
# tools/retrieval_tools/proper_noun_tool.py
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings
import ast
import re

class ProperNounRetriever:
    """专有名词检索器"""
    
    def __init__(self, db, embedding_model="text-embedding-3-small"):
        self.db = db
        self.embedding_model = embedding_model
        self.vector_store = None
        self.proper_nouns = []
        
    def build_index(self, tables: Optional[List[str]] = None):
        """构建专有名词索引"""
        # 获取要索引的表
        if not tables:
            tables = self.db.get_usable_table_names()
        
        # 提取专有名词
        for table in tables:
            self._extract_proper_nouns(table)
        
        # 创建向量存储
        if self.proper_nouns:
            embeddings = OpenAIEmbeddings(model=self.embedding_model)
            self.vector_store = InMemoryVectorStore(embeddings)
            self.vector_store.add_texts(self.proper_nouns)
    
    def _extract_proper_nouns(self, table: str):
        """从表中提取专有名词"""
        # 智能识别包含名称的列
        name_columns = self._identify_name_columns(table)
        
        for column in name_columns:
            try:
                query = f"SELECT DISTINCT {column} FROM {table} WHERE {column} IS NOT NULL LIMIT 1000"
                result = self.db.run(query)
                
                # 解析结果
                values = self._parse_query_result(result)
                self.proper_nouns.extend(values)
                
            except Exception as e:
                logger.warning(f"提取专有名词失败 {table}.{column}: {e}")
    
    def _identify_name_columns(self, table: str) -> List[str]:
        """识别可能包含名称的列"""
        # 获取表信息
        table_info = self.db.get_table_info_no_throw([table])
        
        # 名称相关的模式
        patterns = [
            r'(\w*name\w*)', r'(\w*title\w*)', r'(\w*artist\w*)',
            r'(\w*album\w*)', r'(\w*product\w*)', r'(\w*customer\w*)',
            r'(\w*supplier\w*)', r'(\w*company\w*)'
        ]
        
        columns = set()
        for pattern in patterns:
            matches = re.findall(pattern, table_info, re.IGNORECASE)
            columns.update(matches)
        
        # 过滤掉非列名
        valid_columns = []
        for col in columns:
            if col and not any(kw in col.lower() for kw in ['create', 'table', 'constraint']):
                valid_columns.append(col)
        
        return valid_columns
    
    def search(self, query: str, k: int = 5) -> List[str]:
        """搜索相似的专有名词"""
        if not self.vector_store:
            return []
        
        results = self.vector_store.similarity_search(query, k=k)
        return [doc.page_content for doc in results]

class ProperNounTool(BaseSemanticSQLTool):
    """专有名词检索工具"""
    
    name = "search_proper_nouns"
    description = (
        "搜索数据库中的专有名词（如人名、产品名、公司名等）。"
        "当查询涉及具体名称时，使用此工具查找正确的拼写。"
        "输入: 可能拼写错误的名称，输出: 数据库中最相似的正确名称。"
    )
    category = "retrieval"
    priority = 6
    
    class InputSchema(BaseModel):
        query: str = Field(description="要搜索的名称")
        k: int = Field(default=5, description="返回结果数量")
    
    args_schema = InputSchema
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.retriever = ProperNounRetriever(self.db)
        self._initialized = False
    
    def execute(self, query: str, k: int = 5) -> Dict[str, Any]:
        """执行搜索"""
        # 懒加载：首次使用时构建索引
        if not self._initialized:
            self.retriever.build_index()
            self._initialized = True
        
        # 搜索相似名称
        results = self.retriever.search(query, k)
        
        if not results:
            return {
                "found": False,
                "query": query,
                "suggestions": [],
                "message": "未找到相似的名称"
            }
        
        return {
            "found": True,
            "query": query,
            "suggestions": results,
            "best_match": results[0] if results else None,
            "message": f"找到 {len(results)} 个相似名称"
        }
```

## 7. 思考工具实现

### 7.1 深度思考工具

```python
# tools/thinking_tools/sequential_thinking_tool.py
class SequentialThinkingTool(BaseSemanticSQLTool):
    """深度思考工具"""
    
    name = "deep_thinking"
    description = (
        "对复杂问题进行深度思考和分析。"
        "适用于需要多步推理或复杂逻辑的查询。"
        "会逐步分解问题并给出详细的思考过程。"
    )
    category = "thinking"
    priority = 3
    
    class InputSchema(BaseModel):
        problem: str = Field(description="需要深度思考的问题")
        context: Optional[Dict[str, Any]] = Field(
            default=None,
            description="相关上下文信息"
        )
        max_steps: int = Field(
            default=5,
            description="最大思考步骤数"
        )
    
    args_schema = InputSchema
    
    def execute(
        self, 
        problem: str,
        context: Optional[Dict[str, Any]] = None,
        max_steps: int = 5
    ) -> Dict[str, Any]:
        """执行深度思考"""
        thoughts = []
        current_understanding = ""
        
        for step in range(max_steps):
            # 构建思考提示词
            prompt = self._build_thinking_prompt(
                problem, 
                current_understanding, 
                thoughts,
                context,
                step + 1
            )
            
            # 获取思考结果
            response = self.llm.invoke(prompt)
            thought = response.content
            
            thoughts.append({
                "step": step + 1,
                "thought": thought
            })
            
            # 更新理解
            current_understanding = self._update_understanding(
                current_understanding, thought
            )
            
            # 检查是否得出结论
            if self._has_conclusion(thought):
                break
        
        # 总结思考结果
        conclusion = self._summarize_thoughts(problem, thoughts)
        
        return {
            "problem": problem,
            "thinking_steps": thoughts,
            "conclusion": conclusion,
            "total_steps": len(thoughts)
        }
    
    def _build_thinking_prompt(
        self, 
        problem: str, 
        current: str, 
        thoughts: List[Dict],
        context: Optional[Dict],
        step: int
    ) -> str:
        """构建思考提示词"""
        prompt = f"""
        问题: {problem}
        
        当前步骤: {step}
        
        之前的思考:
        {self._format_thoughts(thoughts)}
        
        当前理解:
        {current if current else '尚未开始分析'}
        
        请继续深入思考这个问题。考虑：
        1. 问题的关键点是什么？
        2. 需要哪些信息来回答？
        3. 可能的解决方案是什么？
        4. 是否需要进一步分解问题？
        
        如果已经得出结论，请明确说明"结论："。
        """
        
        if context:
            prompt += f"\n\n相关上下文:\n{context}"
        
        return prompt
```

## 8. 提示词管理

### 8.1 提示词管理器

```python
# prompts/manager.py
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from typing import Dict, Any
import yaml

class PromptManager:
    """Jinja2 提示词管理器"""
    
    def __init__(self, template_dir: str = None):
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"
        
        self.template_dir = Path(template_dir)
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # 加载配置
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载提示词配置"""
        config_file = self.template_dir.parent / "config.yaml"
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        return {}
    
    def get_prompt(self, template_name: str, **kwargs) -> str:
        """获取渲染后的提示词"""
        # 添加 .j2 后缀
        if not template_name.endswith('.j2'):
            template_name += '.j2'
        
        # 加载模板
        template = self.env.get_template(template_name)
        
        # 合并配置和参数
        context = {
            **self.config,
            **kwargs
        }
        
        return template.render(context)
    
    def get_system_prompt(self, agent_type: str, **kwargs) -> str:
        """获取系统提示词"""
        return self.get_prompt(f"system/{agent_type}", **kwargs)
    
    def get_tool_description(self, tool_name: str, **kwargs) -> str:
        """获取工具描述"""
        return self.get_prompt(f"tools/{tool_name}", **kwargs)
```

### 8.2 提示词模板示例

```jinja2
{# prompts/templates/analysis/field_classification.j2 #}
## 任务：字段分类

请分析以下数据库表的字段，并将它们分类。

### 表信息
表名：{{ table_name }}
表结构：
{{ table_schema }}

{% if sample_data %}
### 样本数据
{{ sample_data }}
{% endif %}

### 分类标准

1. **维度 (dimensions)**
   - 用于分组、筛选的分类字段
   - 例如：地区、产品类别、客户类型

2. **度量 (measures)**
   - 可以进行数学运算的数值字段
   - 例如：金额、数量、分数

3. **标识符 (identifiers)**
   - 唯一标识记录的字段
   - 例如：ID、编号、代码

4. **时间戳 (timestamps)**
   - 时间相关的字段
   - 例如：创建时间、更新时间、日期

5. **描述 (descriptions)**
   - 文本描述性字段
   - 例如：备注、说明、名称

### 输出格式

请以 JSON 格式返回分类结果：
```json
{
  "dimensions": ["field1", "field2"],
  "measures": ["field3", "field4"],
  "identifiers": ["field5"],
  "timestamps": ["field6"],
  "descriptions": ["field7", "field8"]
}
```
```