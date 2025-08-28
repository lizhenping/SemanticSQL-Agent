"""智能体配置

定义智能体相关的配置类。
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from .settings import ModelConfig, DatabaseConfig


class AgentConfig(BaseModel):
    """基础智能体配置"""
    model: ModelConfig = Field(description="模型配置")
    max_steps: int = Field(default=10, description="最大执行步骤数")
    trajectory_dir: Optional[str] = Field(default="trajectories", description="轨迹保存目录")
    verbose: bool = Field(default=False, description="是否输出详细日志")


class SQLAgentConfig(AgentConfig):
    """SQL 智能体配置"""
    database: DatabaseConfig = Field(description="数据库配置")
    tools: List[str] = Field(
        default=[
            "extract_database_schema",
            "analyze_business_domain",
            "classify_table_fields",
            "analyze_entity_relationships",
            "generate_sql",
            "validate_sql",
            "execute_sql",
            "deep_thinking"
        ],
        description="启用的工具列表"
    )
    auto_analyze: bool = Field(
        default=True,
        description="是否自动进行数据库分析（对于简单查询可以跳过）"
    )
    analysis_cache_ttl: int = Field(
        default=3600,
        description="分析结果缓存时间（秒）"
    )
    sql_dialects: List[str] = Field(
        default=["mysql"],
        description="支持的 SQL 方言"
    )
    execution_timeout: int = Field(
        default=30,
        description="SQL 执行超时时间（秒）"
    )
    max_result_rows: int = Field(
        default=100,
        description="最大返回行数"
    )
    enable_reflection: bool = Field(
        default=True,
        description="是否启用反思机制"
    )
    prompt_templates_dir: Optional[str] = Field(
        default="prompts/templates",
        description="提示词模板目录"
    )