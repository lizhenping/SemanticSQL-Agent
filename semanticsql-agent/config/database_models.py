"""
pn“Mn!‹ - úŽtrae_agent¾¡!Œ!‹pn“Mn
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum
import os


class DatabaseType(Enum):
    """pn“{‹š>"""
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"
    MONGODB = "mongodb"


@dataclass
class DatabaseConfig:
    """pn“Mnú{ - úŽ!‹pn“Mn<"""
    
    # ú,Þ¥áo
    type: DatabaseType = DatabaseType.MYSQL
    host: str = "localhost"
    port: int = 3306
    database: str = ""
    username: str = ""
    password: str = ""
    
    # Ø§Þ¥	y
    charset: str = "utf8mb4"
    ssl_mode: Optional[str] = None
    connect_timeout: int = 30
    
    # pn“yšMn
    mysql_config: Optional[Dict[str, Any]] = None
    postgresql_config: Optional[Dict[str, Any]] = None
    
    # Þ¥`Mn
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 3600
    
    # hMn
    include_tables: Optional[List[str]] = None
    exclude_tables: Optional[List[str]] = None
    sample_rows_in_table_info: int = 3
    
    # åâMn
    max_string_length: int = 1000
    max_query_results: int = 10000
    
    def __post_init__(self):
        """Ë"""
        if isinstance(self.type, str):
            self.type = DatabaseType(self.type)
    
    @property
    def connection_string(self) -> str:
        """pn“Þ¥W&2"""
        if self.type == DatabaseType.MYSQL:
            return self._mysql_connection_string()
        elif self.type == DatabaseType.POSTGRESQL:
            return self._postgresql_connection_string()
        elif self.type == DatabaseType.SQLITE:
            return self._sqlite_connection_string()
        else:
            raise ValueError(f"/„pn“{‹: {self.type}")
    
    def _mysql_connection_string(self) -> str:
        """MySQLÞ¥W&2"""
        base_url = f"mysql+pymysql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        params = []
        if self.charset:
            params.append(f"charset={self.charset}")
        if self.connect_timeout:
            params.append(f"connect_timeout={self.connect_timeout}")
        
        if params:
            return f"{base_url}?{'&'.join(params)}"
        return base_url
    
    def _postgresql_connection_string(self) -> str:
        """PostgreSQLÞ¥W&2"""
        base_url = f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        params = []
        if self.connect_timeout:
            params.append(f"connect_timeout={self.connect_timeout}")
        if self.ssl_mode:
            params.append(f"sslmode={self.ssl_mode}")
        
        if params:
            return f"{base_url}?{'&'.join(params)}"
        return base_url
    
    def _sqlite_connection_string(self) -> str:
        """SQLiteÞ¥W&2"""
        return f"sqlite:///{self.database}"
    
    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Î¯ƒØÏúMn"""
        return cls(
            type=DatabaseType(os.getenv("DB_TYPE", "mysql")),
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "3306")),
            database=os.getenv("DB_NAME", ""),
            username=os.getenv("DB_USER", ""),
            password=os.getenv("DB_PASSWORD", ""),
            charset=os.getenv("DB_CHARSET", "utf8mb4"),
            ssl_mode=os.getenv("DB_SSL_MODE"),
            connect_timeout=int(os.getenv("DB_CONNECT_TIMEOUT", "30")),
            pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
            sample_rows_in_table_info=int(os.getenv("DB_SAMPLE_ROWS", "3"))
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DatabaseConfig":
        """ÎWxúMn"""
        # LWMn
        mysql_config = data.pop("mysql", {})
        postgresql_config = data.pop("postgresql", {})
        
        config = cls(**data)
        config.mysql_config = mysql_config
        config.postgresql_config = postgresql_config
        
        return config
    
    def to_dict(self) -> Dict[str, Any]:
        """lb:Wx"""
        return {
            "type": self.type.value,
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "username": self.username,
            "password": self.password,
            "charset": self.charset,
            "ssl_mode": self.ssl_mode,
            "connect_timeout": self.connect_timeout,
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_timeout": self.pool_timeout,
            "pool_recycle": self.pool_recycle,
            "include_tables": self.include_tables,
            "exclude_tables": self.exclude_tables,
            "sample_rows_in_table_info": self.sample_rows_in_table_info,
            "max_string_length": self.max_string_length,
            "max_query_results": self.max_query_results,
            "mysql": self.mysql_config,
            "postgresql": self.postgresql_config
        }


@dataclass
class ModelDatabaseConfig:
    """!‹pn“Mn - úŽ!‹pn“Mn.md<"""
    
    # LLMMn
    model: str = "Qwen3-14B"
    api_key: str = "not-needed"
    base_url: str = "http://192.168.200.216:9009/v1"
    
    # pn“Mn
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    
    # Mn
    count: int = 20
    output_file: str = "test_ddd.json"
    
    @classmethod
    def from_command_line(cls, **kwargs) -> "ModelDatabaseConfig":
        """Î}äLÂpúMn"""
        database_config = DatabaseConfig(
            type=DatabaseType.MYSQL,
            host=kwargs.get("host", "192.168.200.216"),
            port=kwargs.get("port", 13306),
            username=kwargs.get("user", "testuser"),
            password=kwargs.get("password", "testpass"),
            database=kwargs.get("database", "testdb")
        )
        
        return cls(
            model=kwargs.get("model", "Qwen3-14B"),
            api_key=kwargs.get("api_key", "not-needed"),
            base_url=kwargs.get("base_url", "http://192.168.200.216:9009/v1"),
            database=database_config,
            count=kwargs.get("count", 20),
            output_file=kwargs.get("output", "test_ddd.json")
        )
    
    def to_command_line(self) -> str:
        """lb:}äL<"""
        return (
            f"cd ${{workspaceFolder}} && PYTHONPATH=./nl2sql_pipeline/src python -m nl2sql_pipeline "
            f"--model {self.model} --api-key {self.api_key} --base-url {self.base_url} "
            f"--host {self.database.host} --port {self.database.port} "
            f"--user {self.database.username} --password {self.database.password} "
            f"--database {self.database.database} generate --count {self.count} --output {self.output_file}"
        )