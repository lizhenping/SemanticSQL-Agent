"""
trae_agent风格的统一配置系统
"""

import os
import yaml
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from pathlib import Path

from enum import Enum


class DatabaseType(Enum):
    """数据库类型枚举"""
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"


@dataclass
class DatabaseConfig:
    """数据库配置"""
    type: str = "mysql"
    host: str = "192.168.200.216"
    port: int = 13306
    database: str = "testdb"
    username: str = "testuser"
    password: str = "testpass"
    connection_timeout: int = 30
    pool_size: int = 5
    
    # SQLAlchemy连接参数
    echo: bool = False
    pool_pre_ping: bool = True
    pool_recycle: int = 3600
    
    # 额外的数据库参数
    charset: Optional[str] = "utf8mb4"
    max_overflow: int = 10
    sample_rows_in_table_info: int = 3
    pool_timeout: int = 30
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DatabaseConfig":
        """从字典创建配置"""
        # 过滤掉dataclass中不存在的字段
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)
    
    def to_connection_string(self) -> str:
        """生成数据库连接字符串"""
        if self.type == DatabaseType.MYSQL.value:
            driver = "mysql+pymysql"
        elif self.type == DatabaseType.POSTGRESQL.value:
            driver = "postgresql+psycopg2"
        elif self.type == DatabaseType.SQLITE.value:
            return f"sqlite:///{self.database}"
        else:
            raise ValueError(f"不支持的数据库类型: {self.type}")
        
        return f"{driver}://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass
class LLMConfig:
    """LLM配置"""
    model: str = "Qwen3-14B"
    base_url: str = "http://localhost:9009/v1"
    api_key: str = "not-needed"
    temperature: float = 0.1
    max_tokens: int = 2000
    timeout: int = 30
    max_retries: int = 3
    
    # OpenAI特定配置
    organization: Optional[str] = None
    project: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LLMConfig":
        """从字典创建配置"""
        return cls(**data)
    
    @classmethod
    def from_env(cls) -> "LLMConfig":
        """从环境变量创建配置"""
        return cls(
            model=os.getenv("LLM_MODEL", "Qwen3-14B"),
            base_url=os.getenv("LLM_BASE_URL", "http://192.168.200.216:9009/v1"),
            api_key=os.getenv("LLM_API_KEY", "not-needed"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.1")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "2000")),
            timeout=int(os.getenv("LLM_TIMEOUT", "30")),
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "3"))
        )


@dataclass
class AgentConfig:
    """Agent配置"""
    name: str = "SemanticSQLAgent"
    max_steps: int = 10
    verbose: bool = True
    enable_trajectory: bool = True
    enable_reflection: bool = True
    enable_thinking: bool = True
    
    # 工具配置
    enabled_tools: List[str] = field(default_factory=lambda: [
        "connect_database",
        "analyze_schema", 
        "generate_sql",
        "execute_sql",
        "analyze_data",
        "reasoning",
        "analyze_domain"
    ])
    
    # 上下文配置
    max_context_size: int = 10000
    context_persistence: bool = True
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentConfig":
        """从字典创建配置"""
        return cls(**data)


@dataclass
class LoggingConfig:
    """日志配置"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: Optional[str] = None
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LoggingConfig":
        """从字典创建配置"""
        return cls(**data)


@dataclass
class TrajectoryConfig:
    """轨迹记录配置"""
    enabled: bool = True
    directory: str = "trajectories"
    max_trajectories: int = 100
    compress_old: bool = True
    include_llm_calls: bool = True
    include_tool_calls: bool = True
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrajectoryConfig":
        """从字典创建配置"""
        return cls(**data)


@dataclass
class TraeConfig:
    """trae_agent风格的统一配置"""
    
    # 核心配置
    llm: LLMConfig = field(default_factory=LLMConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    trajectory: TrajectoryConfig = field(default_factory=TrajectoryConfig)
    
    # 应用配置
    app_name: str = "SemanticSQLAgent"
    app_version: str = "2.0.0"
    environment: str = "development"
    
    # 路径配置
    config_dir: str = "config"
    data_dir: str = "data"
    logs_dir: str = "logs"
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TraeConfig":
        """从字典创建配置"""
        config = cls()
        
        # 解析嵌套配置
        if "llm" in data:
            config.llm = LLMConfig.from_dict(data["llm"])
        if "database" in data:
            config.database = DatabaseConfig.from_dict(data["database"])
        if "agent" in data:
            config.agent = AgentConfig.from_dict(data["agent"])
        if "logging" in data:
            config.logging = LoggingConfig.from_dict(data["logging"])
        if "trajectory" in data:
            config.trajectory = TrajectoryConfig.from_dict(data["trajectory"])
        
        # 解析其他配置
        for key in ["app_name", "app_version", "environment", "config_dir", "data_dir", "logs_dir"]:
            if key in data:
                setattr(config, key, data[key])
        
        return config
    
    @classmethod
    def from_yaml(cls, yaml_path: str) -> "TraeConfig":
        """从YAML文件创建配置"""
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        return cls.from_dict(data)
    
    @classmethod
    def from_env(cls) -> "TraeConfig":
        """从环境变量创建配置"""
        return cls(
            llm=LLMConfig.from_env(),
            database=DatabaseConfig.from_env(),
            agent=AgentConfig(),
            logging=LoggingConfig(),
            trajectory=TrajectoryConfig(),
            app_name=os.getenv("APP_NAME", "SemanticSQLAgent"),
            app_version=os.getenv("APP_VERSION", "2.0.0"),
            environment=os.getenv("ENVIRONMENT", "development")
        )
    
    @classmethod
    def load_config(cls, config_path: Optional[str] = None) -> "TraeConfig":
        """加载配置（支持多种方式）"""
        # 1. 从指定路径加载
        if config_path and Path(config_path).exists():
            return cls.from_yaml(config_path)
        
        # 2. 从默认路径加载
        default_paths = ["config.yaml", "semanticsql_config.yaml", "trae_config.yaml"]
        for path in default_paths:
            if Path(path).exists():
                return cls.from_yaml(path)
        
        # 3. 从环境变量加载
        if any(os.getenv(k) for k in ["DB_HOST", "LLM_MODEL", "APP_NAME"]):
            return cls.from_env()
        
        # 4. 返回默认配置
        return cls()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "llm": self.llm.__dict__,
            "database": self.database.to_dict(),
            "agent": self.agent.__dict__,
            "logging": self.logging.__dict__,
            "trajectory": self.trajectory.__dict__,
            "app_name": self.app_name,
            "app_version": self.app_version,
            "environment": self.environment,
            "config_dir": self.config_dir,
            "data_dir": self.data_dir,
            "logs_dir": self.logs_dir
        }
    
    def save_yaml(self, path: str) -> None:
        """保存为YAML文件"""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, allow_unicode=True)
    
    def validate(self) -> bool:
        """验证配置有效性"""
        try:
            # 验证数据库配置
            if not self.database.database:
                raise ValueError("数据库名称不能为空")
            
            # 验证LLM配置
            if not self.llm.model:
                raise ValueError("LLM模型不能为空")
            
            # 验证工具配置
            if not self.agent.enabled_tools:
                raise ValueError("至少需要启用一个工具")
            
            return True
            
        except Exception as e:
            self.logger.error(f"配置验证失败: {e}")
            return False


# 配置模板生成
DEFAULT_CONFIG_TEMPLATE = {
    "llm": {
        "model": "Qwen3-14B",
        "base_url": "http://192.168.200.216:9009/v1",
        "api_key": "not-needed",
        "temperature": 0.1,
        "max_tokens": 2000,
        "timeout": 30,
        "max_retries": 3
    },
    "database": {
        "type": "mysql",
        "host": "192.168.200.216",
        "port": 13306,
        "database": "testdb",
        "username": "testuser",
        "password": "testpass",
        "charset": "utf8mb4",
        "pool_size": 5,
        "max_overflow": 10,
        "sample_rows_in_table_info": 3
    },
    "agent": {
        "name": "SemanticSQLAgent",
        "max_steps": 10,
        "verbose": True,
        "enable_trajectory": True,
        "enable_reflection": True,
        "enable_thinking": True,
        "enabled_tools": [
            "schema_extraction",
            "domain_analysis",
            "field_classification",
            "er_analysis",
            "sql_generation",
            "sql_validation",
            "sql_execution",
            "sequential_thinking"
        ]
    },
    "logging": {
        "level": "INFO",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        "file_path": "logs/semanticsql.log",
        "max_file_size": 10485760,
        "backup_count": 5
    },
    "trajectory": {
        "enabled": True,
        "directory": "trajectories",
        "max_trajectories": 100,
        "compress_old": True,
        "include_llm_calls": True,
        "include_tool_calls": True
    },
    "app_name": "SemanticSQLAgent",
    "app_version": "2.0.0",
    "environment": "development",
    "config_dir": "config",
    "data_dir": "data",
    "logs_dir": "logs"
}