"""数据库配置模块

负责构建和管理数据库连接配置
"""

from typing import Dict, Any, Optional


class DatabaseConfig:
    """数据库配置管理器"""
    
    DEFAULT_PORT = 3306
    
    def __init__(self, 
                 host: Optional[str] = None,
                 port: Optional[int] = None,
                 user: Optional[str] = None,
                 password: Optional[str] = None,
                 database: Optional[str] = None):
        """初始化数据库配置
        
        Args:
            host: 数据库主机地址
            port: 数据库端口
            user: 数据库用户名
            password: 数据库密码
            database: 数据库名称
        """
        self.host = host
        self.port = port or self.DEFAULT_PORT
        self.user = user
        self.password = password
        self.database = database
    
    @classmethod
    def from_args(cls, args: Dict[str, Any]) -> 'DatabaseConfig':
        """从命令行参数创建数据库配置
        
        Args:
            args: 命令行参数字典
            
        Returns:
            DatabaseConfig实例
        """
        return cls(
            host=args.get('host'),
            port=args.get('port', cls.DEFAULT_PORT),
            user=args.get('user'),
            password=args.get('password'),
            database=args.get('database')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式
        
        Returns:
            包含数据库配置的字典
        """
        return {
            'host': self.host,
            'port': self.port,
            'user': self.user,
            'password': self.password,
            'database': self.database
        }
    
    def validate(self) -> bool:
        """验证配置是否完整
        
        Returns:
            如果配置完整返回True，否则返回False
        """
        required_fields = ['host', 'user', 'password', 'database']
        return all(getattr(self, field) is not None for field in required_fields)
    
    def get_missing_fields(self) -> list:
        """获取缺失的必要字段
        
        Returns:
            缺失字段的列表
        """
        required_fields = {
            'host': '数据库主机地址',
            'user': '数据库用户名',
            'password': '数据库密码',
            'database': '数据库名称'
        }
        
        missing = []
        for field, description in required_fields.items():
            if getattr(self, field) is None:
                missing.append(f"{field} ({description})")
        
        return missing