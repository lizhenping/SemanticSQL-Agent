# DatabaseConfig 配置文档

## 概述
`DatabaseConfig` 类定义了数据库连接和配置参数。主要针对 MySQL 进行了优化，同时保留了对 PostgreSQL 和 SQLite 的扩展支持。

## 类定义
```python
class DatabaseConfig(BaseModel):
    """数据库连接配置 - 专注MySQL优化，保留其他数据库扩展"""
```

## 枚举类型

### DatabaseType
支持的数据库类型。

```python
class DatabaseType(Enum):
    MYSQL = "mysql"              # 主要支持
    POSTGRESQL = "postgresql"    # 扩展支持
    SQLITE = "sqlite"           # 扩展支持
```

## 配置参数

### 基础连接参数
| 参数名 | 类型 | 默认值 | 描述 |
|-------|------|--------|------|
| type | DatabaseType | DatabaseType.MYSQL | 数据库类型 |
| host | str | "192.168.200.216" | 数据库主机地址 |
| port | int | 13306 | 数据库端口 |
| database | str | "testdb" | 数据库名称 |
| username | str | "testuser" | 用户名 |
| password | str | "testpass" | 密码 |

### MySQL 专用配置
| 参数名 | 类型 | 默认值 | 描述 |
|-------|------|--------|------|
| charset | str | "utf8mb4" | 字符集 |
| autocommit | bool | True | 自动提交 |
| use_unicode | bool | True | 使用 Unicode |

### 连接池配置
| 参数名 | 类型 | 默认值 | 描述 |
|-------|------|--------|------|
| pool_size | int | 5 | 连接池基础大小 |
| max_overflow | int | 10 | 最大溢出连接数 |
| pool_timeout | int | 30 | 获取连接超时（秒） |
| pool_pre_ping | bool | True | 连接前测试 |
| pool_recycle | int | 3600 | 连接回收时间（秒） |

### 其他设置
| 参数名 | 类型 | 默认值 | 描述 |
|-------|------|--------|------|
| connection_timeout | int | 30 | 连接超时时间（秒） |
| echo | bool | False | 是否打印 SQL 语句 |
| sample_rows_in_table_info | int | 3 | 表信息中的示例行数 |

## 主要方法

### `from_env() -> DatabaseConfig`
从环境变量创建配置。

**环境变量映射：**
| 配置参数 | 环境变量名 |
|---------|------------|
| type | DB_TYPE |
| host | DB_HOST |
| port | DB_PORT |
| database | DB_NAME |
| username | DB_USER |
| password | DB_PASSWORD |
| pool_size | DB_POOL_SIZE |
| max_overflow | DB_MAX_OVERFLOW |
| connection_timeout | DB_CONNECTION_TIMEOUT |

**使用示例：**
```python
# 设置环境变量
export DB_HOST=localhost
export DB_PORT=3306
export DB_NAME=mydb
export DB_USER=root
export DB_PASSWORD=secret

# 从环境变量加载
config = DatabaseConfig.from_env()
```

### `to_connection_string() -> str`
生成数据库连接字符串。

**返回格式：**
- MySQL: `mysql+pymysql://user:pass@host:port/database`
- PostgreSQL: `postgresql+psycopg2://user:pass@host:port/database`
- SQLite: `sqlite:///database`

### `validate_connection_params() -> bool`
验证连接参数的有效性。

**验证规则：**
1. 数据库名不能为空
2. 非 SQLite 数据库需要主机和用户名
3. 端口必须在 1-65535 范围内

## 使用示例

### 基本使用
```python
from config.database import DatabaseConfig, DatabaseType

# 创建 MySQL 配置
mysql_config = DatabaseConfig(
    type=DatabaseType.MYSQL,
    host="localhost",
    port=3306,
    database="myapp",
    username="root",
    password="password"
)

# 验证配置
if mysql_config.validate_connection_params():
    print("配置有效")
    
# 获取连接字符串
conn_str = mysql_config.to_connection_string()
print(f"连接字符串: {conn_str}")
```

### 配置不同数据库

#### MySQL 配置
```python
mysql_config = DatabaseConfig(
    type=DatabaseType.MYSQL,
    host="mysql.example.com",
    port=3306,
    database="production_db",
    username="app_user",
    password="secure_password",
    charset="utf8mb4",
    pool_size=10,
    max_overflow=20
)
```

#### PostgreSQL 配置
```python
pg_config = DatabaseConfig(
    type=DatabaseType.POSTGRESQL,
    host="postgres.example.com",
    port=5432,
    database="analytics_db",
    username="postgres",
    password="pg_password"
)
```

#### SQLite 配置
```python
sqlite_config = DatabaseConfig(
    type=DatabaseType.SQLITE,
    database="./data/local.db"
    # 不需要 host、port、username、password
)
```

### 连接池优化

#### 高并发场景
```python
high_concurrency_config = DatabaseConfig(
    # 基础连接信息...
    pool_size=20,              # 增加基础连接数
    max_overflow=50,           # 允许更多溢出连接
    pool_timeout=10,           # 减少等待时间
    pool_pre_ping=True,        # 确保连接有效
    pool_recycle=1800          # 30分钟回收连接
)
```

#### 低频访问场景
```python
low_traffic_config = DatabaseConfig(
    # 基础连接信息...
    pool_size=2,               # 减少基础连接
    max_overflow=5,            # 限制最大连接
    pool_timeout=60,           # 可以等待更长时间
    pool_recycle=7200          # 2小时回收
)
```

### 调试配置
```python
debug_config = DatabaseConfig(
    # 基础连接信息...
    echo=True,                 # 打印所有 SQL 语句
    connection_timeout=60,      # 增加超时时间
    sample_rows_in_table_info=10  # 获取更多示例数据
)
```

## 环境配置示例

### 开发环境 (.env.development)
```bash
DB_TYPE=mysql
DB_HOST=localhost
DB_PORT=3306
DB_NAME=dev_db
DB_USER=dev_user
DB_PASSWORD=dev_password
DB_POOL_SIZE=5
```

### 测试环境 (.env.test)
```bash
DB_TYPE=mysql
DB_HOST=test-mysql.internal
DB_PORT=3306
DB_NAME=test_db
DB_USER=test_user
DB_PASSWORD=test_password
DB_POOL_SIZE=10
```

### 生产环境 (.env.production)
```bash
DB_TYPE=mysql
DB_HOST=prod-mysql.internal
DB_PORT=3306
DB_NAME=prod_db
DB_USER=prod_user
DB_PASSWORD=${SECURE_DB_PASSWORD}
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40
```

## 安全建议

1. **密码管理**
   - 不要在代码中硬编码密码
   - 使用环境变量或密钥管理服务
   - 定期更换密码

2. **连接安全**
   - 生产环境使用 SSL 连接
   - 限制数据库访问 IP
   - 使用最小权限原则

3. **连接池安全**
   - 设置合理的超时时间
   - 监控连接池使用情况
   - 防止连接泄露

## 性能优化

1. **连接池调优**
   ```python
   # 根据并发量调整
   pool_size = 预期并发数 * 0.5
   max_overflow = 预期并发数 * 1.5
   ```

2. **连接复用**
   - 启用 pool_pre_ping 确保连接有效
   - 合理设置 pool_recycle 避免长连接问题

3. **字符集优化**
   - MySQL 使用 utf8mb4 支持完整 Unicode
   - 确保客户端和服务端字符集一致

## 故障排查

### 常见问题

1. **连接失败**
   - 检查网络连通性
   - 验证用户名密码
   - 确认数据库服务状态

2. **连接池耗尽**
   - 增加 pool_size 和 max_overflow
   - 检查是否有连接泄露
   - 优化查询性能

3. **字符集问题**
   - 确保使用 utf8mb4
   - 检查表和列的字符集

## 注意事项

1. 不同数据库的参数可能不完全通用
2. SQLite 不需要大部分连接参数
3. 连接池大小需要根据实际负载调整
4. 生产环境建议启用连接测试（pool_pre_ping）
5. 定期监控数据库连接状态