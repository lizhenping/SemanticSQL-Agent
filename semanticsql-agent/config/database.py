"""数据库配置（参考 nl2sql_pipeline）"""

from pydantic import BaseSettings, Field
from typing import Optional


class DatabaseConfig(BaseSettings):
    """数据库配置"""
    host: str = Field(default="localhost", description="数据库主机")
    port: int = Field(default=3306, description="数据库端口")
    user: str = Field(default="root", description="数据库用户")
    password: str = Field(default="", description="数据库密码")
    database: str = Field(default="test", description="数据库名称")
    charset: str = Field(default="utf8mb4", description="字符集")
    
    # 连接池配置
    pool_size: int = Field(default=5, description="连接池大小")
    max_overflow: int = Field(default=10, description="最大溢出连接数")
    pool_timeout: int = Field(default=30, description="连接池超时时间")
    pool_recycle: int = Field(default=3600, description="连接回收时间")
    
    class Config:
        env_prefix = "DB_"
    
    @property
    def connection_uri(self) -> str:
        """获取数据库连接 URI"""
        return (
            f"mysql+pymysql://{self.user}:{self.password}@"
            f"{self.host}:{self.port}/{self.database}"
            f"?charset={self.charset}"
        )
    
    def get_engine_kwargs(self) -> dict:
        """获取 SQLAlchemy 引擎参数"""
        return {
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_timeout": self.pool_timeout,
            "pool_recycle": self.pool_recycle,
            "pool_pre_ping": True  # 启用连接健康检查
        }