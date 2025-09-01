"""
Global configuration using Pydantic BaseSettings
Based on the design specification for SemanticSQL Agent
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
        description="LLM model name"
    )
    llm_base_url: str = Field(
        default=os.getenv("SEMANTICSQL_LLM_BASE_URL", "http://127.0.0.1:9991/v1"),
        description="LLM API base URL"
    )
    llm_api_key: str = Field(
        default=os.getenv("SEMANTICSQL_LLM_API_KEY", "not-needed"),
        description="LLM API key"
    )
    llm_temperature: float = Field(
        default=float(os.getenv("SEMANTICSQL_LLM_TEMPERATURE", "0.7")),
        description="LLM temperature for creativity"
    )
    llm_max_tokens: int = Field(
        default=int(os.getenv("SEMANTICSQL_LLM_MAX_TOKENS", "20000")),
        description="Maximum tokens for LLM"
    )
    llm_timeout: int = 30
    llm_max_retries: int = 3
    
    # Agent configuration
    max_iterations: int = 20
    max_steps: int = 10
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
        "sequential_thinking"
    ]
    
    # Generation settings
    scenarios_per_batch: int = 10
    questions_per_scenario: int = 5
    
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