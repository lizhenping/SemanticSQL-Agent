"""
Database configuration - DEPRECATED: Use config.settings instead
This module is kept for backward compatibility only.
All new code should use config.settings.Settings directly.
"""

import warnings
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
import os

from models.exceptions import InvalidConfigError, MissingConfigError

# 发出废弃警告
warnings.warn(
    "utils.database_config is deprecated. Use config.settings.Settings instead.",
    DeprecationWarning,
    stacklevel=2
)


class DatabaseType(Enum):
    """支持的数据库类型 - 主要支持MySQL，保留其他扩展"""
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"  # 扩展支持，预留接口
    SQLITE = "sqlite"          # 扩展支持，预留接口


class DatabaseConfig(BaseModel):
    """数据库连接配置 - 专注MySQL优化，保留其他数据库扩展"""
    
    type: DatabaseType = DatabaseType.MYSQL
    host: str = Field(
        default=os.getenv("SEMANTICSQL_DB_HOST", ""),
        description="Database host - DEPRECATED: use config.settings instead"
    )
    port: int = Field(
        default=int(os.getenv("SEMANTICSQL_DB_PORT", "13306")),
        description="Database port"
    )
    database: str = Field(
        default=os.getenv("SEMANTICSQL_DB_DATABASE", "testdb"),
        description="Database name"
    )
    username: str = Field(
        default=os.getenv("SEMANTICSQL_DB_USERNAME", "testuser"),
        description="Database username"
    )
    password: str = Field(
        default=os.getenv("SEMANTICSQL_DB_PASSWORD", "testpass"),
        description="Database password"
    )
    
    # MySQL专用配置
    charset: str = "utf8mb4"
    autocommit: bool = True
    use_unicode: bool = True
    
    # 连接池配置（主要为MySQL优化）
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_pre_ping: bool = True
    pool_recycle: int = 3600
    
    # 连接设置
    connection_timeout: int = 30
    
    # 其他设置
    echo: bool = False
    sample_rows_in_table_info: int = 3
    
    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Create configuration from environment variables - DEPRECATED"""
        warnings.warn(
            "DatabaseConfig.from_env() is deprecated. Use config.settings.get_settings() instead.",
            DeprecationWarning
        )
        return cls(
            type=DatabaseType(os.getenv("SEMANTICSQL_DB_TYPE", "mysql")),
            host=os.getenv("SEMANTICSQL_DB_HOST", ""),
            port=int(os.getenv("SEMANTICSQL_DB_PORT", "3306")),
            database=os.getenv("SEMANTICSQL_DB_DATABASE", ""),
            username=os.getenv("SEMANTICSQL_DB_USERNAME", ""),
            password=os.getenv("SEMANTICSQL_DB_PASSWORD", ""),
            pool_size=int(os.getenv("SEMANTICSQL_DB_POOL_SIZE", "5")),
            max_overflow=int(os.getenv("SEMANTICSQL_DB_MAX_OVERFLOW", "10")),
            connection_timeout=int(os.getenv("SEMANTICSQL_DB_CONNECTION_TIMEOUT", "30"))
        )
    
    @classmethod 
    def from_settings(cls, settings=None) -> "DatabaseConfig":
        """Create configuration from unified settings - RECOMMENDED"""
        if settings is None:
            from config.settings import get_settings
            settings = get_settings()
            
        return cls(
            type=DatabaseType(settings.db_type),
            host=settings.db_host,
            port=settings.db_port,
            database=settings.db_database,
            username=settings.db_username,
            password=settings.db_password
        )
    
    def to_connection_string(self) -> str:
        """Generate database connection string"""
        if self.type == DatabaseType.MYSQL:
            driver = "mysql+pymysql"
        elif self.type == DatabaseType.POSTGRESQL:
            driver = "postgresql+psycopg2"
        elif self.type == DatabaseType.SQLITE:
            return f"sqlite:///{self.database}"
        else:
            raise InvalidConfigError(
                config_name="database_type",
                value=self.type,
                expected="mysql, postgresql, or sqlite"
            )
        
        return f"{driver}://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    def validate_connection_params(self) -> bool:
        """Validate connection parameters"""
        if not self.database:
            raise MissingConfigError("database")
        
        if self.type != DatabaseType.SQLITE:
            if not self.host:
                raise MissingConfigError("host")
            if not self.username:
                raise MissingConfigError("username")
            if self.port <= 0 or self.port > 65535:
                raise InvalidConfigError(
                    config_name="port",
                    value=self.port,
                    expected="1-65535"
                )
        
        return True