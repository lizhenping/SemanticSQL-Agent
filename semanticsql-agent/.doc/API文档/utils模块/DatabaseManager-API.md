# DatabaseManager API 文档

数据库连接管理器，处理 MySQL 数据库的连接和查询。

## 类定义

```python
from typing import Dict, Any, List, Optional, Tuple
from contextlib import contextmanager
import pymysql
from semanticsql_agent.utils.database import DatabaseManager

class DatabaseManager:
    """
    MySQL 数据库管理器
    
    提供数据库连接管理、查询执行和元数据提取功能。
    
    Attributes:
        config: 数据库配置
        connection_pool: 连接池（可选）
    """
```

## 构造函数

```python
def __init__(self, config: DatabaseConfig):
    """
    初始化数据库管理器
    
    Args:
        config: 数据库配置对象
    
    Example:
        ```python
        from semanticsql_agent.config import DatabaseConfig
        
        db_config = DatabaseConfig(
            host="localhost",
            port=3306,
            database="test_db",
            username="root",
            password="password"
        )
        
        db_manager = DatabaseManager(db_config)
        ```
    """
```

## 核心方法

### get_connection

```python
@contextmanager
def get_connection(self) -> pymysql.Connection:
    """
    获取数据库连接（上下文管理器）
    
    Yields:
        pymysql.Connection: 数据库连接对象
    
    Example:
        ```python
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
            results = cursor.fetchall()
        ```
    """
```

### execute_query

```python
def execute_query(
    self,
    sql: str,
    params: Optional[Tuple] = None,
    fetch_size: Optional[int] = None
) -> Tuple[List[Dict[str, Any]], float]:
    """
    执行 SQL 查询
    
    Args:
        sql: SQL 查询语句
        params: 参数化查询的参数
        fetch_size: 限制返回行数
    
    Returns:
        Tuple[List[Dict[str, Any]], float]: (查询结果, 执行时间)
    
    Raises:
        DatabaseConnectionError: 连接失败
        SQLExecutionError: SQL 执行错误
    
    Example:
        ```python
        results, exec_time = db_manager.execute_query(
            "SELECT * FROM orders WHERE status = %s",
            params=("completed",),
            fetch_size=100
        )
        ```
    """
```

### get_table_schema

```python
def get_table_schema(self, table_name: str) -> Dict[str, Any]:
    """
    获取表结构信息
    
    Args:
        table_name: 表名
    
    Returns:
        Dict[str, Any]: 表结构信息
    
    Return Format:
        ```python
        {
            "table_name": "orders",
            "columns": [
                {
                    "name": "order_id",
                    "type": "int",
                    "nullable": False,
                    "key": "PRI",
                    "default": None,
                    "extra": "auto_increment"
                },
                {
                    "name": "customer_id",
                    "type": "int",
                    "nullable": False,
                    "key": "MUL",
                    "default": None,
                    "extra": ""
                }
            ],
            "indexes": [
                {
                    "name": "PRIMARY",
                    "columns": ["order_id"],
                    "unique": True
                }
            ],
            "foreign_keys": [
                {
                    "name": "fk_orders_customers",
                    "column": "customer_id",
                    "ref_table": "customers",
                    "ref_column": "customer_id"
                }
            ]
        }
        ```
    """
```

### get_database_schema

```python
def get_database_schema(self) -> Dict[str, Any]:
    """
    获取整个数据库的结构
    
    Returns:
        Dict[str, Any]: 数据库完整结构
    
    Return Format:
        ```python
        {
            "database": "ecommerce",
            "tables": {
                "orders": {...},  # 表结构
                "customers": {...},
                "products": {...}
            },
            "relationships": [...]  # 外键关系
        }
        ```
    """
```

### test_connection

```python
def test_connection(self) -> bool:
    """
    测试数据库连接
    
    Returns:
        bool: 连接是否成功
    
    Example:
        ```python
        if db_manager.test_connection():
            print("Database connected successfully")
        else:
            print("Failed to connect to database")
        ```
    """
```

### get_sample_data

```python
def get_sample_data(
    self,
    table_name: str,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    获取表的样本数据
    
    Args:
        table_name: 表名
        limit: 返回行数限制
    
    Returns:
        List[Dict[str, Any]]: 样本数据
    """
```

## 事务支持

```python
@contextmanager
def transaction(self):
    """
    事务上下文管理器
    
    Example:
        ```python
        with db_manager.transaction():
            db_manager.execute_query("INSERT INTO orders ...")
            db_manager.execute_query("UPDATE inventory ...")
            # 自动提交或回滚
        ```
    """
```

## 错误处理

```python
from semanticsql_agent.models.exceptions import (
    DatabaseConnectionError,
    SQLExecutionError,
    SchemaExtractionError
)

# 使用示例
try:
    db_manager = DatabaseManager(config)
except Exception as e:
    raise DatabaseConnectionError(
        host=config.host,
        database=config.database,
        original_error=e
    )

# SQL执行错误
try:
    result = db_manager.execute_query(sql)
except Exception as e:
    raise SQLExecutionError(
        sql=sql,
        error=str(e)
    )
```

## 使用示例

### 基本使用
```python
# 创建管理器
db_manager = DatabaseManager(db_config)

# 执行查询
results, exec_time = db_manager.execute_query(
    "SELECT COUNT(*) as total FROM orders"
)
print(f"Total orders: {results[0]['total']}")
print(f"Execution time: {exec_time}s")

# 获取表结构
schema = db_manager.get_table_schema("orders")
for column in schema["columns"]:
    print(f"{column['name']}: {column['type']}")
```

### 高级使用
```python
# 使用事务
with db_manager.transaction():
    # 插入订单
    order_id = db_manager.execute_query(
        "INSERT INTO orders (customer_id, total) VALUES (%s, %s)",
        params=(123, 99.99)
    )
    
    # 更新库存
    db_manager.execute_query(
        "UPDATE inventory SET quantity = quantity - %s WHERE product_id = %s",
        params=(1, 456)
    )
```

## 性能优化

1. **连接复用**：使用连接池减少连接开销
2. **查询缓存**：缓存表结构等元数据
3. **批量操作**：支持批量插入和更新
4. **索引利用**：自动分析查询使用的索引

## 注意事项

1. 只支持 MySQL 数据库
2. 默认使用 UTF-8 编码
3. 自动处理连接超时和重连
4. 查询结果以字典列表形式返回

---

相关文档：
- [配置文档](../../config模块/DatabaseConfig-API.md)
