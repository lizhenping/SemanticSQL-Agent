"""数据库服务接口

提供数据库操作的统一接口，包括：
- 连接管理
- 架构信息获取
- 数据采样
- 查询执行
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from ..models.database import DatabaseSchema, TableInfo


class DatabaseService(ABC):
    """数据库服务抽象基类
    
    定义所有数据库操作的接口。
    """
    
    @abstractmethod
    def connect(self, config: Dict[str, Any]):
        """建立数据库连接
        
        参数:
            config: 数据库连接配置，包含host、port、database、user、password等
        """
        pass
    
    @abstractmethod
    def disconnect(self):
        """断开数据库连接"""
        pass
    
    @abstractmethod
    def get_tables(self) -> List[Dict[str, Any]]:
        """获取所有表的基本信息
        
        返回:
            表信息列表，每个元素包含：
            - name: 表名
            - comment: 表注释
            - row_count: 行数（可选）
        """
        pass
    
    @abstractmethod
    def get_columns(self, table_name: str) -> List[Dict[str, Any]]:
        """获取指定表的所有列信息
        
        参数:
            table_name: 表名
            
        返回:
            列信息列表，每个元素包含：
            - name: 列名
            - type: 数据类型
            - nullable: 是否可空
            - default: 默认值
            - comment: 列注释
        """
        pass
    
    @abstractmethod
    def get_primary_key(self, table_name: str) -> List[str]:
        """获取表的主键列
        
        参数:
            table_name: 表名
            
        返回:
            主键列名列表
        """
        pass
    
    @abstractmethod
    def get_foreign_keys(self, table_name: str) -> List[Dict[str, Any]]:
        """获取表的外键信息
        
        参数:
            table_name: 表名
            
        返回:
            外键信息列表，每个元素包含：
            - column: 外键列名
            - referenced_table: 引用的表名
            - referenced_column: 引用的列名
        """
        pass
    
    @abstractmethod
    def get_table_row_count(self, table_name: str, database_name: str) -> int:
        """获取表的行数
        
        参数:
            table_name: 表名
            database_name: 数据库名
            
        返回:
            行数
        """
        pass
    
    @abstractmethod
    def get_column_examples(self, table_name: str, column_name: str, 
                          database_name: str, count: int = 10) -> List[Any]:
        """获取列的样例数据
        
        参数:
            table_name: 表名
            column_name: 列名
            database_name: 数据库名
            count: 样例数量
            
        返回:
            样例数据列表
        """
        pass
    
    @abstractmethod
    def get_table_sample(self, table_name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取表的样本数据
        
        参数:
            table_name: 表名
            limit: 样本行数限制
            
        返回:
            样本数据列表，每行是一个字典
        """
        pass
    
    @abstractmethod
    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """执行SQL查询
        
        参数:
            query: SQL查询语句
            
        返回:
            查询结果列表
        """
        pass
    
    @abstractmethod
    def test_connection(self) -> bool:
        """测试数据库连接
        
        返回:
            True表示连接正常，False表示连接失败
        """
        pass