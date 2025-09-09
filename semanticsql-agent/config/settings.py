"""
Global configuration using Pydantic BaseSettings - UNIQUE CONFIGURATION SOURCE
Based on the design specification for SemanticSQL Agent

ENVIRONMENT VARIABLES REFERENCE:
================================

LLM Configuration:
- SEMANTICSQL_LLM_MODEL: LLM model name (default: Qwen3-14B)
- SEMANTICSQL_LLM_BASE_URL: LLM API base URL (default: http://127.0.0.1:9991/v1)  
- SEMANTICSQL_LLM_API_KEY: LLM API key (default: not-needed)
- SEMANTICSQL_LLM_TEMPERATURE: LLM temperature (default: 0.7)
- SEMANTICSQL_LLM_MAX_TOKENS: Maximum tokens (default: 8000)

Neo4j Configuration:
- SEMANTICSQL_NEO4J_URI: Neo4j connection URI (REQUIRED in production)
- SEMANTICSQL_NEO4J_USER: Neo4j username (default: neo4j) 
- SEMANTICSQL_NEO4J_PASSWORD: Neo4j password (REQUIRED in production)

Database Configuration:
- SEMANTICSQL_DB_TYPE: Database type (default: mysql)
- SEMANTICSQL_DB_HOST: Database host (REQUIRED in production)
- SEMANTICSQL_DB_PORT: Database port (default: 13306)
- SEMANTICSQL_DB_DATABASE: Database name (REQUIRED in production)
- SEMANTICSQL_DB_USERNAME: Database username (REQUIRED in production)
- SEMANTICSQL_DB_PASSWORD: Database password (REQUIRED in production)

NOTE: Default values are provided for development. In production,
      critical values should be explicitly set via environment variables.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
import os


class Settings(BaseModel):
    """Global application settings"""

    # Application configuration
    app_name: str = "SemanticSQL Agent"
    app_version: str = "2.0.0"
    debug: bool = False
    environment: str = "development"

    # LLM configuration - 使用VLLM实际返回的模型名
    llm_model: str = Field(
        default=os.getenv("SEMANTICSQL_LLM_MODEL", "Qwen3-14B"),
        description="LLM model name",
    )
    llm_base_url: str = Field(
        default=os.getenv("SEMANTICSQL_LLM_BASE_URL", "http://127.0.0.1:9991/v1"),
        description="LLM API base URL - REQUIRED in production, avoid hardcoded localhost",
    )
    llm_api_key: str = Field(
        default=os.getenv("SEMANTICSQL_LLM_API_KEY", "not-needed"),
        description="LLM API key",
    )
    llm_temperature: float = Field(
        default=float(os.getenv("SEMANTICSQL_LLM_TEMPERATURE", "0.1")),
        description="LLM temperature for creativity",
    )
    llm_max_tokens: int = Field(
        default=int(os.getenv("SEMANTICSQL_LLM_MAX_TOKENS", "28000")),
        description="Maximum tokens for LLM",
    )
    llm_timeout: int = 30
    llm_max_retries: int = 3

    # Neo4j configuration - NO HARDCODED DEFAULTS IN PRODUCTION
    neo4j_uri: str = Field(
        default=os.getenv("SEMANTICSQL_NEO4J_URI", "bolt://127.0.0.1:7687"),
        description="Neo4j connection URI - avoid hardcoded localhost in production",
    )
    neo4j_user: str = Field(
        default=os.getenv("SEMANTICSQL_NEO4J_USER", "neo4j"),
        description="Neo4j username",
    )
    neo4j_password: str = Field(
        default=os.getenv("SEMANTICSQL_NEO4J_PASSWORD", "88888888"),
        description="Neo4j password - REQUIRED in production",
    )

    # MySQL database configuration - NO HARDCODED DEFAULTS IN PRODUCTION  
    db_type: str = Field(
        default=os.getenv("SEMANTICSQL_DB_TYPE", "mysql"),
        description="Database type",
    )
    db_host: str = Field(
        default=os.getenv("SEMANTICSQL_DB_HOST", "http://127.0.0.1"),
        description="Database host - REQUIRED in production",
    )
    db_port: int = Field(
        default=int(os.getenv("SEMANTICSQL_DB_PORT", "13306")),
        description="Database port",
    )
    db_database: str = Field(
        default=os.getenv("SEMANTICSQL_DB_DATABASE", "testdb"),
        description="Database name - REQUIRED in production",
    )
    db_username: str = Field(
        default=os.getenv("SEMANTICSQL_DB_USERNAME", "testuser"),
        description="Database username - REQUIRED in production",
    )
    db_password: str = Field(
        default=os.getenv("SEMANTICSQL_DB_PASSWORD", "testpass"),
        description="Database password - REQUIRED in production",
    )

    # Fail-fast configuration - 强制fail-fast策略
    fail_fast: bool = Field(
        default=bool(os.getenv("SEMANTICSQL_FAIL_FAST", "true").lower() == "true"),
        description="Enable fail-fast mode: fail immediately on any connection/configuration error"
    )
    
    # Agent configuration
    max_iterations: int = 20
    max_steps: int = 100  # 统一为100，足够处理所有场景组合
    enable_reflection: bool = True
    enable_trajectory: bool = True
    enable_thinking: bool = True
    verbose: bool = True

    # Enabled tools
    enabled_tools: List[str] = [
        "schema_extraction",
        "domain_analysis",
        "field_classification",
        "er_analysis",
        "sql_generation",
        "sql_validation",
        "sql_execution",
        "sequential_thinking",
    ]

    # Output settings
    output_directory: str = "./output"
    output_format: str = "json"
    save_intermediate: bool = False

    # Logging configuration
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_file_path: Optional[str] = None
    log_max_file_size: int = 10 * 1024 * 1024  # 10MB
    log_backup_count: int = 5

    # Trajectory configuration
    trajectory_enabled: bool = True
    trajectory_directory: str = "trajectories"
    trajectory_max_count: int = 100
    trajectory_compress_old: bool = True
    trajectory_include_llm_calls: bool = True
    trajectory_include_tool_calls: bool = True

    # Paths
    config_dir: str = "config"
    data_dir: str = "data"
    logs_dir: str = "logs"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Support nested env vars like LLM__MODEL
        env_nested_delimiter = "__"


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """获取全局设置实例"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
