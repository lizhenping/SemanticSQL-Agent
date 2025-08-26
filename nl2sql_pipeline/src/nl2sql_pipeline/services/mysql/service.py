"""MySQL数据库服务

重构后的服务，使用模块化的组件。
"""

import logging
from typing import Dict, List, Any, Optional, Tuple

from ..database_service import DatabaseService
from ...models.database import TableInfo, ColumnInfo
from .connectors.connection_manager import MySQLConnectionManager
from .executors.query_executor import MySQLQueryExecutor
from .inspectors.schema_inspector import MySQLSchemaInspector

logger = logging.getLogger(__name__)


class MySQLDatabaseService(DatabaseService):
    """MySQL数据库服务实现
    
    使用模块化组件组织功能：
    - 连接管理器：管理数据库连接
    - 查询执行器：执行SQL查询
    - 架构检查器：获取元数据
    """
    
    def __init__(self):
        """初始化MySQL服务"""
        self.connection_manager = MySQLConnectionManager()
        self.query_executor = MySQLQueryExecutor(self.connection_manager)
        self.schema_inspector = MySQLSchemaInspector(self.query_executor)
    
    # 连接管理方法
    
    def connect(self, **kwargs) -> None:
        """连接到MySQL数据库
        
        参数:
            host: 主机地址
            port: 端口号（默认3306）
            user: 用户名
            password: 密码
            database: 数据库名（可选）
            charset: 字符集（默认utf8mb4）
            **kwargs: 其他连接参数
        """
        self.connection_manager.connect(**kwargs)
    
    def disconnect(self) -> None:
        """断开数据库连接"""
        self.connection_manager.disconnect()
    
    def test_connection(self) -> bool:
        """测试数据库连接
        
        返回:
            连接是否正常
        """
        return self.connection_manager.test_connection()
    
    # 架构检查方法
    
    def get_tables(self, schema: Optional[str] = None) -> List[str]:
        """获取表列表
        
        参数:
            schema: 数据库名（为None时使用当前数据库）
            
        返回:
            表名列表
        """
        return self.schema_inspector.get_tables(schema)
    
    def get_columns(self, table_name: str, schema: Optional[str] = None) -> List[ColumnInfo]:
        """获取表的列信息
        
        参数:
            table_name: 表名
            schema: 数据库名
            
        返回:
            列信息列表
        """
        return self.schema_inspector.get_columns(table_name, schema)
    
    def get_primary_key(self, table_name: str, schema: Optional[str] = None) -> Optional[List[str]]:
        """获取表的主键信息
        
        参数:
            table_name: 表名
            schema: 数据库名
            
        返回:
            主键列名列表或None
        """
        return self.schema_inspector.get_primary_key(table_name, schema)
    
    def get_foreign_keys(self, table_name: str, schema: Optional[str] = None) -> List[Dict[str, str]]:
        """获取表的外键信息
        
        参数:
            table_name: 表名
            schema: 数据库名
            
        返回:
            外键信息列表
        """
        return self.schema_inspector.get_foreign_keys(table_name, schema)
    
    def get_indexes(self, table_name: str, schema: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取表的索引信息
        
        参数:
            table_name: 表名
            schema: 数据库名
            
        返回:
            索引信息列表
        """
        return self.schema_inspector.get_indexes(table_name, schema)
    
    def get_table_comment(self, table_name: str, schema: Optional[str] = None) -> Optional[str]:
        """获取表的注释
        
        参数:
            table_name: 表名
            schema: 数据库名
            
        返回:
            表注释或None
        """
        return self.schema_inspector.get_table_comment(table_name, schema)
    
    def get_table_row_count(self, table_name: str, schema: Optional[str] = None) -> int:
        """获取表的行数（精确计数）
        
        参数:
            table_name: 表名
            schema: 数据库名
            
        返回:
            精确的行数
        """
        return self.schema_inspector.get_table_row_count(table_name, schema)
    
    def get_table_info(self, table_name: str, schema: Optional[str] = None) -> Optional[TableInfo]:
        """获取表的完整信息
        
        参数:
            table_name: 表名
            schema: 数据库名
            
        返回:
            表信息对象或None
        """
        return self.schema_inspector.get_table_info(table_name, schema)
    
    # 查询执行方法
    
    def execute_query(self, query: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """执行SQL查询
        
        参数:
            query: SQL查询语句
            params: 查询参数（用于参数化查询）
            
        返回:
            查询结果列表
        """
        return self.query_executor.execute_query(query, params)
    
    def get_column_examples(self, 
                          table_name: str, 
                          column_name: str,
                          limit: int = 10,
                          schema: Optional[str] = None) -> List[Any]:
        """获取列的样例值
        
        参数:
            table_name: 表名
            column_name: 列名
            limit: 限制数量
            schema: 数据库名
            
        返回:
            样例值列表
        """
        return self.query_executor.get_column_examples(
            table_name, column_name, schema, limit
        )
    
    def get_table_sample(self, 
                        table_name: str, 
                        limit: int = 10,
                        schema: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取表的样本数据
        
        参数:
            table_name: 表名
            limit: 限制数量
            schema: 数据库名
            
        返回:
            样本数据列表
        """
        return self.query_executor.get_table_sample(
            table_name, schema, limit
        )
    
    # 事务管理方法
    
    def begin_transaction(self) -> None:
        """开始事务"""
        self.connection_manager.begin_transaction()
    
    def commit(self) -> None:
        """提交事务"""
        self.connection_manager.commit()
    
    def rollback(self) -> None:
        """回滚事务"""
        self.connection_manager.rollback()
    
    def transaction(self):
        """事务上下文管理器
        
        使用方式:
            with db_service.transaction():
                # 执行数据库操作
        """
        return self.connection_manager.transaction()
    
    # 批量操作方法
    
    def execute_many(self, query: str, params_list: List[Tuple]) -> int:
        """批量执行SQL语句
        
        参数:
            query: SQL语句模板
            params_list: 参数列表
            
        返回:
            影响的行数
        """
        return self.query_executor.execute_many(query, params_list)
    
    def execute_with_pagination(self, 
                              query: str, 
                              params: Optional[Tuple] = None,
                              page_size: int = 1000):
        """执行分页查询
        
        参数:
            query: SQL查询语句
            params: 查询参数
            page_size: 每页大小
            
        返回:
            分页结果迭代器
        """
        return self.query_executor.execute_with_pagination(
            query, params, page_size
        )