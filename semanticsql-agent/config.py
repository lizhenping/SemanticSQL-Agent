"""统一配置管理（简化版）"""

import os
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import yaml


@dataclass
class DatabaseConfig:
    """数据库配置"""
    type: str = "mysql"
    host: str = "localhost"
    port: int = 3306
    database: str = ""
    username: str = ""
    password: str = ""
    
    @property
    def connection_string(self) -> str:
        """生成连接字符串"""
        if self.type == "mysql":
            return f"mysql+pymysql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        elif self.type == "postgresql":
            return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        else:
            raise ValueError(f"不支持的数据库类型: {self.type}")


@dataclass
class LLMConfig:
    """LLM 配置（简化版，仅支持本地 Qwen）"""
    model: str = "Qwen3-14B"
    base_url: str = "http://192.168.200.216:9009/v1"
    api_key: str = "not-needed"
    temperature: float = 0.1
    max_tokens: int = 2000


@dataclass
class Config:
    """统一配置类"""
    # LLM 配置
    llm: LLMConfig = field(default_factory=LLMConfig)
    
    # 数据库配置
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    
    # 智能体配置
    max_steps: int = 10
    verbose: bool = True
    save_trajectory: bool = True
    
    # 工具配置
    enable_thinking_tool: bool = True
    enable_reflection: bool = True
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        """从字典创建配置"""
        config = cls()
        
        # 解析 LLM 配置
        if "llm" in data:
            config.llm = LLMConfig(**data["llm"])
        
        # 解析数据库配置
        if "database" in data:
            config.database = DatabaseConfig(**data["database"])
        
        # 解析其他配置
        for key in ["max_steps", "verbose", "save_trajectory", 
                    "enable_thinking_tool", "enable_reflection"]:
            if key in data:
                setattr(config, key, data[key])
        
        return config
    
    @classmethod
    def from_yaml(cls, yaml_path: str) -> "Config":
        """从 YAML 文件加载配置"""
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)
    
    @classmethod
    def from_env(cls) -> "Config":
        """从环境变量加载配置"""
        config = cls()
        
        # LLM 环境变量
        if model := os.getenv("LLM_MODEL"):
            config.llm.model = model
        if base_url := os.getenv("LLM_BASE_URL"):
            config.llm.base_url = base_url
        if api_key := os.getenv("LLM_API_KEY"):
            config.llm.api_key = api_key
        
        # 数据库环境变量
        if db_type := os.getenv("DB_TYPE"):
            config.database.type = db_type
        if db_host := os.getenv("DB_HOST"):
            config.database.host = db_host
        if db_port := os.getenv("DB_PORT"):
            config.database.port = int(db_port)
        if db_name := os.getenv("DB_NAME"):
            config.database.database = db_name
        if db_user := os.getenv("DB_USER"):
            config.database.username = db_user
        if db_password := os.getenv("DB_PASSWORD"):
            config.database.password = db_password
        
        # 其他环境变量
        if max_steps := os.getenv("MAX_STEPS"):
            config.max_steps = int(max_steps)
        if verbose := os.getenv("VERBOSE"):
            config.verbose = verbose.lower() == "true"
        
        return config