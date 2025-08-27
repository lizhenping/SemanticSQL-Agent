"""全局配置（参考 nl2sql_pipeline）"""

from pydantic import BaseSettings, Field
from typing import Dict, Any, Optional


class ModelConfig(BaseSettings):
    """模型配置"""
    name: str = Field(default="Qwen3-14B", description="模型名称")
    provider: str = Field(default="openai", description="模型提供商")
    base_url: Optional[str] = Field(default="http://192.168.200.216:9009/v1", description="API 地址")
    api_key: Optional[str] = Field(default="not-needed", description="API 密钥")
    temperature: float = Field(default=0.1, description="温度参数")
    max_tokens: int = Field(default=2000, description="最大令牌数")
    
    class Config:
        env_prefix = "MODEL_"


class AgentConfig(BaseSettings):
    """智能体配置"""
    max_iterations: int = Field(default=15, description="最大迭代次数")
    enable_thinking: bool = Field(default=True, description="启用深度思考工具")
    verbose: bool = Field(default=True, description="详细输出")
    
    class Config:
        env_prefix = "AGENT_"


class Settings(BaseSettings):
    """全局设置"""
    model: ModelConfig = Field(default_factory=ModelConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    
    # 日志配置
    log_level: str = Field(default="INFO", description="日志级别")
    log_file: Optional[str] = Field(default=None, description="日志文件路径")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    @classmethod
    def from_yaml(cls, yaml_path: str) -> "Settings":
        """从 YAML 文件加载配置"""
        import yaml
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return cls(**data)