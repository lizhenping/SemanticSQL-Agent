"""统一配置管理（参考 TRAEAgent 的简洁设计）"""

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
class ModelConfig:
    """模型配置"""
    provider: str = "openai"
    model: str = "gpt-4"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.0
    max_tokens: int = 2000
    
    def __post_init__(self):
        # 从环境变量读取 API 密钥
        if not self.api_key:
            self.api_key = os.getenv(f"{self.provider.upper()}_API_KEY", "")


@dataclass
class Config:
    """统一配置类"""
    # 模型配置
    model: ModelConfig = field(default_factory=ModelConfig)
    
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
        
        # 解析模型配置
        if "model" in data:
            config.model = ModelConfig(**data["model"])
        
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
        
        # 覆盖环境变量中的配置
        env_mappings = {
            "MODEL_PROVIDER": ("model", "provider"),
            "MODEL_NAME": ("model", "model"),
            "MODEL_API_KEY": ("model", "api_key"),
            "MODEL_BASE_URL": ("model", "base_url"),
            "DB_TYPE": ("database", "type"),
            "DB_HOST": ("database", "host"),
            "DB_PORT": ("database", "port", int),
            "DB_NAME": ("database", "database"),
            "DB_USER": ("database", "username"),
            "DB_PASSWORD": ("database", "password"),
            "MAX_STEPS": ("max_steps", int),
            "VERBOSE": ("verbose", lambda x: x.lower() == "true"),
        }
        
        for env_key, mapping in env_mappings.items():
            value = os.getenv(env_key)
            if value is not None:
                if len(mapping) == 2:
                    setattr(config, mapping[0], value)
                elif len(mapping) == 3:
                    # 嵌套属性
                    obj = getattr(config, mapping[0])
                    setattr(obj, mapping[1], value)
                elif len(mapping) == 4:
                    # 带类型转换
                    obj = getattr(config, mapping[0])
                    setattr(obj, mapping[1], mapping[2](value))
        
        return config
    
    def resolve(self, **overrides) -> "Config":
        """解析配置，支持覆盖"""
        # 应用覆盖
        for key, value in overrides.items():
            if hasattr(self, key):
                setattr(self, key, value)
            elif "." in key:
                # 支持嵌套属性，如 "model.temperature"
                parts = key.split(".")
                obj = self
                for part in parts[:-1]:
                    obj = getattr(obj, part)
                setattr(obj, parts[-1], value)
        
        return self