# Schema Extraction Tool API接口文档

## 工具基本信息

```python
class SchemaExtractionTool(BaseSemanticSQLTool):
    name: str = "schema_extraction_tool"
    description: str = "分析数据库结构，提取表和字段信息，直接存储到Neo4j图数据库"
```

## 构造函数

### `__init__(memory_manager, database_manager, **kwargs)`

**功能**：初始化Schema提取工具

**参数**：
- `memory_manager: Optional[Neo4jMemoryManager]` - Neo4j记忆管理器实例
- `database_manager: Optional[DatabaseManager]` - 数据库管理器实例
- `**kwargs` - 其他基类参数

**使用示例**：
```python
tool = SchemaExtractionTool(
    memory_manager=neo4j_manager,
    database_manager=db_manager
)
```

## 核心方法

### `_run(*args, **kwargs) -> str`

**功能**：执行Schema提取的主入口方法

**参数**：
- `*args, **kwargs` - 输入参数（当前版本不使用）

**返回值**：
- `str` - 执行结果消息

**成功返回**：
```text
"✅ schema_extraction_tool提取完成，已存储到Neo4j。请继续执行field_analysis_tool工具。"
```

**失败返回**：
```text
"❌ Schema提取失败: [错误详情]"
```

**执行流程**：
1. 解析输入参数和配置
2. 获取数据库管理器
3. 从MySQL提取原始数据
4. 直接存储到Neo4j图结构
5. 返回简洁成功消息

**异常处理**：
- 捕获所有异常，返回错误消息而不抛出
- 记录详细错误日志

## 数据提取方法

### `_extract_mysql_metadata(db_manager) -> Dict[str, Any]`

**功能**：从MySQL提取完整的元数据

**参数**：
- `db_manager: DatabaseManager` - 数据库管理器

**返回值**：
```python
{
    "database_info": {
        "name": "database_name",
        "business_desc": ""
    },
    "filtered_tables": ["table1", "table2"],
    "tables_data": [
        {
            "name": "table1",
            "row_count": None,
            "business_desc": "表注释",
            "columns": [...]
        }
    ],
    "connection_info": {
        "host": "localhost",
        "database": "testdb"
    }
}
```

**异常**：
- 抛出 `ToolExecutionError` 如果提取失败

### `_extract_table_metadata(db_manager, table_name) -> Dict[str, Any]`

**功能**：提取单个表的元数据

**参数**：
- `db_manager: DatabaseManager` - 数据库管理器
- `table_name: str` - 表名

**返回值**：
```python
{
    "name": "table_name",
    "row_count": None,  # 当前阶段为null
    "business_desc": "表注释内容",
    "columns": [
        {
            "name": "column_name",
            "data_type": "varchar",
            "is_nullable": True,
            "is_primary": False,
            "is_foreign": False,
            "category": None,
            "entropy_level": "medium",
            "sample_values": ["value1", "value2"],
            "business_desc": "列注释"
        }
    ]
}
```

### `_extract_columns_metadata(db_manager, table_name) -> List[Dict[str, Any]]`

**功能**：提取列元数据

**参数**：
- `db_manager: DatabaseManager` - 数据库管理器
- `table_name: str` - 表名

**返回值**：列信息数组，每个元素包含完整的列元数据

## 数据分析方法

### `_check_foreign_key(db_manager, table_name, column_name) -> Optional[bool]`

**功能**：检查列是否为外键

**参数**：
- `db_manager: DatabaseManager` - 数据库管理器
- `table_name: str` - 表名
- `column_name: str` - 列名

**返回值**：
- `True` - 是外键
- `False` - 不是外键
- `None` - 检查失败

**实现原理**：
- 查询 `INFORMATION_SCHEMA.KEY_COLUMN_USAGE`
- 检查 `REFERENCED_TABLE_NAME` 是否非空

### `_calculate_entropy_level(db_manager, table_name, column_name) -> Optional[str]`

**功能**：计算列的熵值等级

**参数**：
- `db_manager: DatabaseManager` - 数据库管理器
- `table_name: str` - 表名
- `column_name: str` - 列名

**返回值**：
- `"high"` - 高熵（唯一值比例 >= 0.8）
- `"medium"` - 中熵（唯一值比例 >= 0.4）
- `"low"` - 低熵（唯一值比例 < 0.4）
- `None` - 计算失败

**算法参数**：
- 采样数量：500条记录
- 只统计非空值
- 基于唯一值比例分类

### `_collect_sample_values(db_manager, table_name, column_name) -> List`

**功能**：采集列的样本值

**参数**：
- `db_manager: DatabaseManager` - 数据库管理器  
- `table_name: str` - 表名
- `column_name: str` - 列名

**返回值**：
- `List` - 样本值列表（最多100个不重复值）
- `[]` - 采集失败或无数据时返回空列表

**采集策略**：
- 使用 `SELECT DISTINCT` 去重
- 过滤空值 `WHERE column IS NOT NULL`
- 限制数量 `LIMIT 100`

## Neo4j存储方法

### `_store_to_neo4j(raw_data) -> None`

**功能**：将提取的数据直接存储到Neo4j图结构

**参数**：
- `raw_data: Dict[str, Any]` - 从MySQL提取的原始数据

**存储结构**：
```cypher
# Database节点
(d:Database {name, business_desc})

# Table节点和关系
(d)-[:CONTAINS]->(t:Table {name, row_count, business_desc})

# Column节点和关系
(t)-[:HAS_COLUMN]->(c:Column {
    name, data_type, is_nullable, is_primary, 
    is_foreign, category, entropy_level, 
    sample_values, business_desc
})
```

**异常**：
- 如果Neo4j连接不可用，抛出异常

### `_create_database_node(neo4j_graph, database_info) -> None`

**功能**：创建Database节点

**Cypher查询**：
```cypher
MERGE (d:Database {name: $name})
SET d.business_desc = $business_desc
```

### `_create_table_node(neo4j_graph, database_name, table_data) -> None`

**功能**：创建Table节点和CONTAINS关系

**Cypher查询**：
```cypher
MATCH (d:Database {name: $database_name})
MERGE (t:Table {name: $table_name})
SET t.row_count = $row_count,
    t.business_desc = $business_desc
MERGE (d)-[:CONTAINS]->(t)
```

### `_create_column_node(neo4j_graph, table_name, column_data) -> None`

**功能**：创建Column节点和HAS_COLUMN关系

**Cypher查询**：
```cypher
MATCH (t:Table {name: $table_name})
MERGE (c:Column {name: $column_name})
SET c.data_type = $data_type,
    c.is_nullable = $is_nullable,
    c.is_primary = $is_primary,
    c.is_foreign = $is_foreign,
    c.category = $category,
    c.entropy_level = $entropy_level,
    c.sample_values = $sample_values,
    c.business_desc = $business_desc
MERGE (t)-[:HAS_COLUMN]->(c)
```

## 工具方法

### `_get_database_manager() -> DatabaseManager`

**功能**：获取数据库管理器

**返回值**：
- `DatabaseManager` - 注入的数据库管理器实例

**异常**：
- 如果未注入数据库管理器，抛出 `ToolExecutionError`

### `_get_all_table_names(db_manager) -> List[str]`

**功能**：获取数据库中所有表名

**SQL查询**：
```sql
SELECT TABLE_NAME as table_name 
FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_SCHEMA = 'database_name'
```

### `_filter_tables(table_names, blacklist) -> List[str]`

**功能**：根据黑名单过滤表名

**参数**：
- `table_names: List[str]` - 所有表名
- `blacklist: List[str]` - 黑名单列表

**过滤逻辑**：
- 部分匹配：如果表名包含黑名单中的任意字符串，则过滤
- 记录统计：输出过滤的表数量

## 便利函数

### `create_schema_extraction_tool(memory_manager, database_manager) -> SchemaExtractionTool`

**功能**：创建Schema提取工具的便利函数

**参数**：
- `memory_manager: Optional[Neo4jMemoryManager]` - Neo4j记忆管理器
- `database_manager: Optional[DatabaseManager]` - 数据库管理器

**返回值**：
- `SchemaExtractionTool` - 配置好的工具实例

**使用示例**：
```python
from tools.analysis_tools.schema_extraction_tool import create_schema_extraction_tool

tool = create_schema_extraction_tool(
    memory_manager=neo4j_manager,
    database_manager=db_manager
)
```

## 日志接口

### 日志级别
- `INFO` - 正常执行信息
- `WARNING` - 非关键错误（如采集样本值失败）
- `ERROR` - 关键错误

### 日志格式
```python
# 开始执行
self.logger.info(f"🔧 {self.name}: 开始执行 - 输入: ...")

# 执行完成
self.logger.info(f"✅ {self.name}: 执行完成 - 成功处理 {table_count} 个表")

# 统计信息
self.logger.info(f"📊 成功提取数据库 {database_name}: {len(filtered_tables)} 个表 (过滤后)")

# Neo4j存储
self.logger.info(f"💾 成功存储到Neo4j: 1个数据库, {len(tables_data)}个表, {sum(len(t['columns']) for t in tables_data)}个列")

# 警告信息
self.logger.warning(f"获取表 {table_name} comment失败: {e}")

# 错误信息  
self.logger.error(f"❌ {self.name}: {error_msg}")
```

## 错误码定义

### 工具级错误
- **TOOL_INIT_ERROR**: 工具初始化失败
- **DATABASE_MISSING**: 数据库管理器未注入
- **NEO4J_MISSING**: Neo4j连接不可用

### 业务逻辑错误
- **METADATA_EXTRACT_FAILED**: 元数据提取失败
- **TABLE_FILTER_FAILED**: 表过滤失败
- **NEO4J_STORE_FAILED**: Neo4j存储失败

### 数据质量警告
- **COMMENT_MISSING**: 注释信息缺失
- **SAMPLE_COLLECT_FAILED**: 样本值采集失败
- **ENTROPY_CALC_FAILED**: 熵值计算失败
- **FK_CHECK_FAILED**: 外键检查失败

## 性能指标

### 时间复杂度
- **表数量**: O(n) 其中n为表的数量
- **列数量**: O(m) 其中m为总列数
- **样本采集**: O(k) 其中k为采样数量（500-100）

### 空间复杂度
- **内存使用**: O(n*m*k) 存储所有表、列和样本值
- **Neo4j存储**: O(n+m) 创建节点和关系

### 性能建议
- 对于大型数据库（>100表），考虑分批处理
- 对于高并发场景，使用连接池
- 对于历史数据，考虑增量更新机制