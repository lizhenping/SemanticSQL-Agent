"""
数据库配置模型 - 基于模型数据库配置.md
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any
import os


class DatabaseType(Enum):
    """数据库类型枚举"""
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"


@dataclass
class DatabaseConfig:
    """数据库配置"""
    type: str = "mysql"
    host: str = "localhost"
    port: int = 3306
    database: str = ""
    username: str = "root"
    password: str = ""
    charset: str = "utf8mb4"
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 3600
    connect_timeout: int = 10
    ssl_mode: Optional[str] = None
    verbose: bool = False
    
    @property
    def connection_string(self) -> str:
        """生成数据库连接字符串"""
        if self.type == DatabaseType.MYSQL.value:
            return self._mysql_connection_string()
        elif self.type == DatabaseType.POSTGRESQL.value:
            return self._postgresql_connection_string()
        elif self.type == DatabaseType.SQLITE.value:
            return self._sqlite_connection_string()
        else:
            raise ValueError(f"不支持的数据库类型: {self.type}")
    
    def _mysql_connection_string(self) -> str:
        """MySQL连接字符串"""
        return f"mysql+pymysql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}?charset={self.charset}"
    
    def _postgresql_connection_string(self) -> str:
        """PostgreSQL连接字符串"""
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    def _sqlite_connection_string(self) -> str:
        """SQLite连接字符串"""
        return f"sqlite:///{self.database}.db"
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DatabaseConfig":
        """从字典创建配置"""
        return cls(
            type=data.get("type", "mysql"),
            host=data.get("host", "localhost"),
            port=int(data.get("port", 3306)),
            database=data.get("database", ""),
            username=data.get("username", "root"),
            password=data.get("password", ""),
            charset=data.get("charset", "utf8mb4"),
            pool_size=int(data.get("pool_size", 5)),
            max_overflow=int(data.get("max_overflow", 10)),
            pool_timeout=int(data.get("pool_timeout", 30)),
            pool_recycle=int(data.get("pool_recycle", 3600)),
            connect_timeout=int(data.get("connect_timeout", 10)),
            ssl_mode=data.get("ssl_mode", None)
        )
    
    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """从环境变量创建配置"""
        return cls(
            type=os.getenv("DB_TYPE", "mysql"),
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "3306")),
            database=os.getenv("DB_NAME", ""),
            username=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            charset=os.getenv("DB_CHARSET", "utf8mb4"),
            pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10"))
        )


@dataclass
class ModelDatabaseConfig:
    """模型数据库配置 - 专门用于存储模型相关信息的数据库"""
    type: str = "mysql"
    host: str = "192.168.200.216"
    port: int = 13306
    database: str = "testdb"
    username: str = "testuser"
    password: str = "testpass"
    charset: str = "utf8mb4"
    pool_size: int = 5
    max_overflow: int = 10
    
    @property
    def connection_string(self) -> str:
        """生成模型数据库连接字符串"""
        return f"mysql+pymysql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}?charset={self.charset}"
    
    def to_database_config(self) -> DatabaseConfig:
        """转换为标准数据库配置"""
        return DatabaseConfig(
            type=self.type,
            host=self.host,
            port=self.port,
            database=self.database,
            username=self.username,
            password=self.password,
            charset=self.charset,
            pool_size=self.pool_size,
            max_overflow=self.max_overflow
        )