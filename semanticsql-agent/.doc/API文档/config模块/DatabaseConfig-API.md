# DatabaseConfig API 文档

MySQL 数据库配置类，管理数据库连接参数。

## 类定义

```python
from pydantic import BaseModel, Field, validator
from typing import Optional
from semanticsql_agent.config import DatabaseConfig

class DatabaseConfig(BaseModel):
    """
    MySQL 数据库配置
    
    使用 Pydantic BaseModel 实现，提供参数验证。
    """
```

## 配置项

### 基础连接参数

```python
host: str = Field(
    description="数据库主机地址",
    example="localhost"
)

port: int = Field(
    default=3306,
    ge=1,
    le=65535,
    description="数据库端口"
)

database: str = Field(
    description="数据库名称",
    example="ecommerce_db"
)

username: str = Field(
    description="数据库用户名",
    example="root"
)

password: str = Field(
    description="数据库密码"
)
```

### 高级参数

```python
charset: str = Field(
    default="utf8mb4",
    description="字符编码"
)

connect_timeout: int = Field(
    default=10,
    ge=1,
    description="连接超时时间（秒）"
)

read_timeout: Optional[int] = Field(
    default=None,
    ge=1,
    description="读取超时时间（秒）"
)

write_timeout: Optional[int] = Field(
    default=None,
    ge=1,
    description="写入超时时间（秒）"
)

max_connections: int = Field(
    default=10,
    ge=1,
    le=100,
    description="最大连接数"
)

autocommit: bool = Field(
    default=True,
    description="是否自动提交事务"
)
```

## 验证器

```python
@validator("port")
def validate_port(cls, v):
    """验证端口号"""
    if not 1 <= v <= 65535:
        raise ValueError("Port must be between 1 and 65535")
    return v

@validator("database")
def validate_database(cls, v):
    """验证数据库名"""
    if not v or not v.strip():
        raise ValueError("Database name cannot be empty")
    return v.strip()
```

## 连接 URL 生成

```python
@property
def connection_url(self) -> str:
    """
    生成 MySQL 连接 URL
    
    Returns:
        str: MySQL 连接 URL
    
    Example:
        mysql://user:pass@localhost:3306/dbname?charset=utf8mb4
    """
    from urllib.parse import quote_plus
    
    password = quote_plus(self.password)
    url = f"mysql://{self.username}:{password}@{self.host}:{self.port}/{self.database}"
    
    if self.charset:
        url += f"?charset={self.charset}"
    
    return url

@property
def pymysql_params(self) -> dict:
    """
    生成 PyMySQL 连接参数
    
    Returns:
        dict: PyMySQL connect() 参数
    """
    return {
        "host": self.host,
        "port": self.port,
        "user": self.username,
        "password": self.password,
        "database": self.database,
        "charset": self.charset,
        "connect_timeout": self.connect_timeout,
        "read_timeout": self.read_timeout,
        "write_timeout": self.write_timeout,
        "autocommit": self.autocommit
    }
```

## 使用示例

### 基本使用
```python
from semanticsql_agent.config import DatabaseConfig

# 创建配置
db_config = DatabaseConfig(
    host="localhost",
    port=3306,
    database="test_db",
    username="root",
    password="password123"
)

# 获取连接 URL
print(db_config.connection_url)
# mysql://root:password123@localhost:3306/test_db?charset=utf8mb4

# 获取 PyMySQL 参数
params = db_config.pymysql_params
```

### 从环境变量加载
```python
import os
from semanticsql_agent.config import DatabaseConfig

# 从环境变量创建配置
db_config = DatabaseConfig(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "3306")),
    database=os.getenv("DB_NAME"),
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD")
)
```

### 配置验证
```python
from pydantic import ValidationError

try:
    # 无效配置
    db_config = DatabaseConfig(
        host="localhost",
        port=99999,  # 无效端口
        database="",  # 空数据库名
        username="root",
        password="pass"
    )
except ValidationError as e:
    print(f"配置错误: {e}")
```

## 与其他组件集成

### 与 DatabaseManager 集成
```python
from semanticsql_agent.utils.database import DatabaseManager
from semanticsql_agent.config import DatabaseConfig

# 创建配置
db_config = DatabaseConfig(
    host="localhost",
    database="ecommerce",
    username="root",
    password="password"
)

# 创建数据库管理器
db_manager = DatabaseManager(db_config)

# 测试连接
if db_manager.test_connection():
    print("数据库连接成功")
```

### 与 SQLAgent 集成
```python
from semanticsql_agent.agent import SQLAgent
from semanticsql_agent.config import Settings, DatabaseConfig

# 配置
settings = Settings()
db_config = DatabaseConfig(
    host="localhost",
    database="test_db",
    username="root",
    password="password"
)

# 创建 Agent
agent = SQLAgent(settings, db_config)
```

## 安全建议

### 1. 密码管理
```python
# 不要硬编码密码
# 错误示例
db_config = DatabaseConfig(
    password="hardcoded_password"  # 不要这样做
)

# 正确示例
import os
db_config = DatabaseConfig(
    password=os.environ["DB_PASSWORD"]  # 从环境变量读取
)
```

### 2. 配置文件
```python
# config.json (加入 .gitignore)
{
    "host": "localhost",
    "database": "prod_db",
    "username": "app_user"
}

# 加载配置
import json
with open("config.json") as f:
    config_data = json.load(f)

db_config = DatabaseConfig(
    **config_data,
    password=os.environ["DB_PASSWORD"]  # 密码从环境变量
)
```

## 连接池配置

```python
# 扩展配置以支持连接池
class PooledDatabaseConfig(DatabaseConfig):
    """支持连接池的数据库配置"""
    
    pool_size: int = Field(
        default=5,
        ge=1,
        le=50,
        description="连接池大小"
    )
    
    pool_recycle: int = Field(
        default=3600,
        description="连接回收时间（秒）"
    )
    
    pool_pre_ping: bool = Field(
        default=True,
        description="是否在使用前检查连接"
    )
```

## 注意事项

1. 只支持 MySQL 数据库
2. 密码应该通过环境变量或密钥管理系统提供
3. 默认使用 utf8mb4 字符集支持完整 Unicode
4. 连接参数会自动验证

---

相关文档：
- [Settings API](./Settings-API.md)
- [DatabaseManager API](../utils模块/DatabaseManager-API.md)