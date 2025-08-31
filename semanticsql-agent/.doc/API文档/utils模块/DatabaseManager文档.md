# DatabaseManager API 文档

## 概述
`DatabaseManager` 是用于管理数据库连接和执行查询的工具类。提供了统一的接口来处理不同类型的数据库（MySQL、PostgreSQL、SQLite）。

## 类定义
```python
class DatabaseManager:
    """简化的数据库管理器"""
```

## 构造函数
```python
def __init__(self, config: DatabaseConfig)
```

**参数：**
- `config` (DatabaseConfig): 数据库配置对象

**初始化内容：**
- 配置验证
- 日志记录器设置
- 连接参数准备

## 主要方法

### `initialize() -> bool`
初始化数据库连接。

**返回：**
- `bool`: 初始化是否成功

**功能：**
- 创建数据库引擎
- 配置连接池
- 测试连接
- 创建会话工厂

### `get_tables() -> List[str]`
获取所有表名。

**返回：**
- `List[str]`: 表名列表

**支持的数据库：**
- MySQL: `SHOW TABLES`
- PostgreSQL: 查询 `information_schema.tables`
- SQLite: 查询 `sqlite_master`

### `get_table_info(table_name: str) -> Dict[str, Any]`
获取表的详细信息。

**参数：**
- `table_name` (str): 表名

**返回结构：**
```python
{
    "name": str,           # 表名
    "columns": [           # 列信息列表
        {
            "name": str,       # 列名
            "type": str,       # 数据类型
            "nullable": bool,  # 是否可空
            "key": str,        # 键类型 (PRI/MUL/UNI)
            "default": Any,    # 默认值
            "extra": str       # 额外信息
        },
        ...
    ]
}
```

### `execute_query(sql: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]`
执行 SELECT 查询。

**参数：**
- `sql` (str): SQL 查询语句
- `params` (Dict[str, Any]): 查询参数（可选）

**返回：**
- `List[Dict[str, Any]]`: 查询结果列表

**示例：**
```python
# 无参数查询
results = db_manager.execute_query("SELECT * FROM users LIMIT 10")

# 参数化查询
results = db_manager.execute_query(
    "SELECT * FROM users WHERE age > :age",
    params={"age": 18}
)
```

### `execute_command(sql: str, params: Dict[str, Any] = None) -> int`
执行非查询命令（INSERT、UPDATE、DELETE）。

**参数：**
- `sql` (str): SQL 命令
- `params` (Dict[str, Any]): 命令参数（可选）

**返回：**
- `int`: 影响的行数

### `test_connection() -> bool`
测试数据库连接。

**返回：**
- `bool`: 连接是否正常

### `get_sample_data(table_name: str, limit: int = 5) -> List[Dict[str, Any]]`
获取表的示例数据。

**参数：**
- `table_name` (str): 表名
- `limit` (int): 返回行数限制

**返回：**
- `List[Dict[str, Any]]`: 示例数据

### `close()`
关闭数据库连接。

**功能：**
- 释放所有连接
- 清理资源

## 上下文管理器

### `@contextmanager session()`
提供数据库会话的上下文管理器。

**使用示例：**
```python
with db_manager.session() as sess:
    result = sess.execute(text("SELECT * FROM users"))
    data = result.fetchall()
```

### `@contextmanager transaction()`
提供事务的上下文管理器。

**使用示例：**
```python
with db_manager.transaction() as conn:
    conn.execute(text("INSERT INTO users (name) VALUES (:name)"), {"name": "张三"})
    conn.execute(text("UPDATE stats SET count = count + 1"))
    # 自动提交或回滚
```

## 连接池配置

通过 `DatabaseConfig` 对象配置：

```python
config = DatabaseConfig(
    type=DatabaseType.MYSQL,
    host="localhost",
    port=3306,
    username="root",
    password="password",
    database="test_db",
    pool_size=5,              # 连接池大小
    max_overflow=10,          # 最大溢出连接数
    pool_timeout=30,          # 连接超时时间
    pool_recycle=3600,        # 连接回收时间
    pool_pre_ping=True        # 连接前测试
)
```

## 使用示例

### 基本使用
```python
from config.database import DatabaseConfig, DatabaseType

# 创建配置
config = DatabaseConfig(
    type=DatabaseType.MYSQL,
    host="localhost",
    port=3306,
    username="root",
    password="password",
    database="test_db"
)

# 创建管理器
db_manager = DatabaseManager(config)

# 初始化连接
if db_manager.initialize():
    # 获取所有表
    tables = db_manager.get_tables()
    print(f"数据库中有 {len(tables)} 个表")
    
    # 获取表信息
    for table in tables[:3]:
        info = db_manager.get_table_info(table)
        print(f"\n表 {table} 有 {len(info['columns'])} 列")
    
    # 执行查询
    results = db_manager.execute_query(
        "SELECT COUNT(*) as count FROM users"
    )
    print(f"用户总数: {results[0]['count']}")
    
    # 关闭连接
    db_manager.close()
```

### 事务处理
```python
try:
    with db_manager.transaction() as conn:
        # 插入订单
        conn.execute(text(
            "INSERT INTO orders (user_id, amount) VALUES (:user_id, :amount)"
        ), {"user_id": 1, "amount": 100.00})
        
        # 更新库存
        conn.execute(text(
            "UPDATE inventory SET quantity = quantity - :qty WHERE product_id = :pid"
        ), {"qty": 1, "pid": 123})
        
        # 事务自动提交
        
except Exception as e:
    print(f"事务失败: {e}")
    # 事务自动回滚
```

### 批量操作
```python
# 批量插入
users = [
    {"name": "张三", "email": "zhang@example.com"},
    {"name": "李四", "email": "li@example.com"},
    {"name": "王五", "email": "wang@example.com"}
]

with db_manager.session() as session:
    for user in users:
        session.execute(
            text("INSERT INTO users (name, email) VALUES (:name, :email)"),
            user
        )
    session.commit()
```

## 错误处理

### 常见异常
- `SQLAlchemyError`: 数据库操作错误
- `ConnectionError`: 连接失败
- `TimeoutError`: 连接超时

### 错误处理示例
```python
try:
    results = db_manager.execute_query("SELECT * FROM users")
except SQLAlchemyError as e:
    logger.error(f"查询失败: {e}")
    # 尝试重新连接
    if not db_manager.test_connection():
        db_manager.initialize()
```

## 性能优化

### 1. 连接池调优
```python
config = DatabaseConfig(
    # ... 其他配置
    pool_size=10,        # 根据并发量调整
    max_overflow=20,     # 允许更多临时连接
    pool_pre_ping=True   # 确保连接有效
)
```

### 2. 查询优化
```python
# 使用 LIMIT 限制结果集
results = db_manager.execute_query(
    "SELECT * FROM large_table LIMIT 1000"
)

# 只选择需要的列
results = db_manager.execute_query(
    "SELECT id, name FROM users WHERE active = true"
)
```

### 3. 批量操作
```python
# 使用事务批量操作
with db_manager.transaction() as conn:
    for i in range(1000):
        conn.execute(text("INSERT INTO ..."))
    # 一次性提交
```

## 安全考虑

### 1. 参数化查询
始终使用参数化查询防止 SQL 注入：
```python
# 正确方式
db_manager.execute_query(
    "SELECT * FROM users WHERE id = :id",
    params={"id": user_id}
)

# 错误方式（不要这样做）
# db_manager.execute_query(f"SELECT * FROM users WHERE id = {user_id}")
```

### 2. 权限控制
- 使用最小权限原则
- 为不同操作使用不同的数据库用户
- 定期审查权限设置

## 注意事项

1. 始终在使用完后关闭连接
2. 大查询结果考虑分页处理
3. 长时间运行的事务会锁定资源
4. 监控连接池使用情况
5. 定期检查慢查询日志