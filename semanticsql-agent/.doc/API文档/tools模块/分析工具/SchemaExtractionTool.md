# SchemaExtractionTool API 文档

数据库结构提取工具，负责获取数据库的完整结构信息。

## 类定义

```python
from typing import Dict, List, Any
from langchain.tools import BaseTool
from langchain.pydantic_v1 import BaseModel, Field

class SchemaExtractionTool(BaseTool):
    """
    数据库结构提取工具
    
    提取 MySQL 数据库的完整结构信息，包括：
    - 表信息（名称、注释、引擎类型）
    - 列信息（名称、类型、约束、注释）
    - 索引信息（主键、唯一索引、普通索引）
    - 外键约束
    
    Attributes:
        name: 工具名称，固定为 "extract_schema"
        description: 工具描述
        db_config: 数据库配置
    """
    
    name = "extract_schema"
    description = "Extract complete database schema including tables, columns, constraints, and indexes"
```

## 输入定义

```python
class InputSchema(BaseModel):
    """工具输入参数"""
    database_name: str = Field(
        description="Name of the database to analyze"
    )
    include_views: bool = Field(
        default=False,
        description="Whether to include views in the schema"
    )
    include_indexes: bool = Field(
        default=True,
        description="Whether to include index information"
    )

args_schema = InputSchema
```

## 核心方法

### _run

```python
def _run(
    self,
    database_name: str,
    include_views: bool = False,
    include_indexes: bool = True
) -> Dict[str, Any]:
    """
    同步执行数据库结构提取
    
    Args:
        database_name: 数据库名称
        include_views: 是否包含视图
        include_indexes: 是否包含索引信息
    
    Returns:
        Dict[str, Any]: 数据库结构信息
    
    Raises:
        DatabaseConnectionError: 数据库连接失败
        PermissionError: 权限不足
    
    Return Format:
        ```python
        {
            "database": "mydb",
            "tables": [
                {
                    "name": "users",
                    "comment": "用户表",
                    "engine": "InnoDB",
                    "collation": "utf8mb4_general_ci",
                    "row_count": 1000  # 估算值
                }
            ],
            "columns": [
                {
                    "table": "users",
                    "name": "id",
                    "type": "int",
                    "nullable": False,
                    "default": None,
                    "comment": "用户ID",
                    "is_primary": True,
                    "is_unique": True,
                    "auto_increment": True
                }
            ],
            "indexes": [
                {
                    "table": "users",
                    "name": "PRIMARY",
                    "type": "PRIMARY",
                    "columns": ["id"],
                    "unique": True
                }
            ],
            "foreign_keys": [
                {
                    "table": "orders",
                    "constraint_name": "fk_user_id",
                    "column": "user_id",
                    "referenced_table": "users",
                    "referenced_column": "id",
                    "on_delete": "CASCADE",
                    "on_update": "CASCADE"
                }
            ],
            "statistics": {
                "total_tables": 10,
                "total_columns": 85,
                "total_indexes": 25,
                "total_constraints": 15
            }
        }
        ```
    """
```

### _arun

```python
async def _arun(
    self,
    database_name: str,
    include_views: bool = False,
    include_indexes: bool = True
) -> Dict[str, Any]:
    """
    异步执行（当前未实现）
    
    Raises:
        NotImplementedError: 异步执行未实现
    """
```

## 内部方法

### _get_tables

```python
def _get_tables(self, database_name: str) -> List[Dict[str, Any]]:
    """
    获取所有表信息
    
    使用 INFORMATION_SCHEMA 查询表元数据。
    """
```

### _get_columns

```python
def _get_columns(self, database_name: str) -> List[Dict[str, Any]]:
    """
    获取所有列信息
    
    包括数据类型、约束、默认值等。
    """
```

### _get_indexes

```python
def _get_indexes(self, database_name: str) -> List[Dict[str, Any]]:
    """
    获取所有索引信息
    
    包括主键、唯一索引、普通索引、全文索引等。
    """
```

### _get_foreign_keys

```python
def _get_foreign_keys(self, database_name: str) -> List[Dict[str, Any]]:
    """
    获取所有外键约束
    
    包括级联删除和更新规则。
    """
```

## 使用示例

### 基础使用

```python
from semanticsql_agent.tools.analysis import SchemaExtractionTool
from semanticsql_agent.config import DatabaseConfig

# 创建工具
db_config = DatabaseConfig(
    host="localhost",
    port=3306,
    database="mydb",
    username="root",
    password="password"
)

tool = SchemaExtractionTool(db_config=db_config)

# 执行提取
result = tool.run(database_name="mydb")

# 使用结果
print(f"Total tables: {result['statistics']['total_tables']}")
for table in result['tables']:
    print(f"Table: {table['name']} ({table['row_count']} rows)")
```

### 在 Agent 中使用

```python
# 工具会自动注册到 Agent
agent = SQLAgent(config, db_config)

# Agent 内部调用
# Thought: I need to understand the database structure first
# Action: extract_schema
# Action Input: {"database_name": "mydb"}
# Observation: [database schema details]
```

### 高级选项

```python
# 包含视图
result = tool.run(
    database_name="mydb",
    include_views=True,
    include_indexes=True
)

# 只获取表结构，不包含索引
result = tool.run(
    database_name="mydb",
    include_indexes=False
)
```

## 输出处理

### 解析表信息

```python
schema = tool.run(database_name="mydb")

# 构建表名到列的映射
table_columns = {}
for column in schema['columns']:
    table_name = column['table']
    if table_name not in table_columns:
        table_columns[table_name] = []
    table_columns[table_name].append(column)

# 查找特定表的主键
def get_primary_key(table_name):
    for column in schema['columns']:
        if column['table'] == table_name and column['is_primary']:
            return column['name']
    return None
```

### 分析表关系

```python
# 构建关系图
relationships = {}
for fk in schema['foreign_keys']:
    if fk['table'] not in relationships:
        relationships[fk['table']] = []
    relationships[fk['table']].append({
        'to': fk['referenced_table'],
        'via': fk['column']
    })

# 找出核心表（被多个表引用）
referenced_count = {}
for fk in schema['foreign_keys']:
    ref_table = fk['referenced_table']
    referenced_count[ref_table] = referenced_count.get(ref_table, 0) + 1

core_tables = sorted(
    referenced_count.items(),
    key=lambda x: x[1],
    reverse=True
)[:5]
```

## 性能优化

### 缓存机制

```python
class CachedSchemaExtractionTool(SchemaExtractionTool):
    """带缓存的结构提取工具"""
    
    def __init__(self, db_config, cache_ttl=3600):
        super().__init__(db_config)
        self._cache = {}
        self._cache_time = {}
        self.cache_ttl = cache_ttl
    
    def _run(self, database_name, **kwargs):
        cache_key = f"{database_name}_{kwargs}"
        
        # 检查缓存
        if cache_key in self._cache:
            if time.time() - self._cache_time[cache_key] < self.cache_ttl:
                return self._cache[cache_key]
        
        # 执行提取
        result = super()._run(database_name, **kwargs)
        
        # 更新缓存
        self._cache[cache_key] = result
        self._cache_time[cache_key] = time.time()
        
        return result
```

### 分批查询

```python
# 对于大型数据库，分批查询表信息
def _get_tables_batch(self, database_name, batch_size=100):
    offset = 0
    all_tables = []
    
    while True:
        query = f"""
        SELECT TABLE_NAME, TABLE_COMMENT, ENGINE
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = %s
        LIMIT {batch_size} OFFSET {offset}
        """
        
        tables = self.db_manager.execute_query(query, [database_name])
        if not tables:
            break
            
        all_tables.extend(tables)
        offset += batch_size
    
    return all_tables
```

## 错误处理

```python
from semanticsql_agent.models.exceptions import (
    DatabaseConnectionError,
    SchemaExtractionError,
    ToolExecutionError
)

try:
    schema = tool.run({"database_name": "mydb"})
except DatabaseConnectionError as e:
    print(f"连接失败: {e.message}")
    print(f"错误代码: {e.error_code}")  # DB_001
    # 尝试重连或使用备用数据库
except SchemaExtractionError as e:
    print(f"Schema提取失败: {e.message}")
    print(f"错误代码: {e.error_code}")  # DB_003
    # 可能需要检查表结构或权限
except ToolExecutionError as e:
    print(f"工具执行错误: {e.message}")
    # 记录错误并通知
```

## 配置选项

```python
# 自定义配置
class SchemaExtractionConfig:
    # 查询超时时间（秒）
    query_timeout: int = 30
    
    # 是否包含系统表
    include_system_tables: bool = False
    
    # 表名过滤模式
    table_pattern: Optional[str] = None
    
    # 最大返回表数量
    max_tables: Optional[int] = None

# 使用配置
tool = SchemaExtractionTool(
    db_config=db_config,
    config=SchemaExtractionConfig(
        query_timeout=60,
        table_pattern="order_%",
        max_tables=50
    )
)
```

## 注意事项

1. **权限要求**：需要对 INFORMATION_SCHEMA 的读权限
2. **性能影响**：大型数据库的完整提取可能耗时较长
3. **内存使用**：结果可能很大，注意内存限制
4. **版本兼容**：针对 MySQL 5.7+ 优化，其他版本可能需要调整
5. **字符编码**：确保正确处理中文注释和特殊字符

## 相关工具

- [DomainAnalysisTool](./DomainAnalysisTool.md) - 基于 schema 进行领域分析
- [FieldClassificationTool](./FieldClassificationTool.md) - 对字段进行语义分类
- [ERAnalysisTool](./ERAnalysisTool.md) - 分析实体关系

---

更多信息请参考 [LangChain Tools 文档](https://docs.langchain.com/docs/modules/tools/)