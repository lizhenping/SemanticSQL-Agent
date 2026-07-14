"""基础设施层（infra/）

抽象接口 + 具体实现，供 tools/core 依赖注入。
依赖方向：只依赖 models，不依赖 tools/core/cli。

模块：
- llm.py:       LLMClient 协议 + ChatOpenAI 实现 + FakeLLM
- database.py:  DatabaseManager（MySQL/SQLite，删 Neo4j）+ classify_sql_error
- storage.py:   KnowledgeStore 协议 + JSONL 实现 + InMemory 实现
- sql_ast.py:   SQLAstParser 协议 + sqlglot 实现 + FakeSQLAstParser
"""

# LLM
from infra.llm import (
    LLMClient,
    ChatOpenAILLMClient,
    FakeLLMClient,
    create_llm_client,
)

# Database
from infra.database import (
    DatabaseManager,
    DatabaseInfo,
    SchemaExtractor,
    SQLExecutor,
    classify_sql_error,
    create_database_manager,
)

# Storage
from infra.storage import (
    KnowledgeStore,
    JSONLKnowledgeStore,
    InMemoryKnowledgeStore,
)

# SQL AST
from infra.sql_ast import (
    SQLAstParser,
    SqlglotParser,
    FakeSQLAstParser,
    AggregateCall,
    JoinClause,
)

__all__ = [
    # LLM
    "LLMClient", "ChatOpenAILLMClient", "FakeLLMClient", "create_llm_client",
    # Database
    "DatabaseManager", "DatabaseInfo", "SchemaExtractor", "SQLExecutor",
    "classify_sql_error", "create_database_manager",
    # Storage
    "KnowledgeStore", "JSONLKnowledgeStore", "InMemoryKnowledgeStore",
    # SQL AST
    "SQLAstParser", "SqlglotParser", "FakeSQLAstParser",
    "AggregateCall", "JoinClause",
]
