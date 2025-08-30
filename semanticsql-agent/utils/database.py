"""
数据库工具函数 - 连接管理和查询执行
"""

import logging
from typing import Dict, Any, List, Optional, Union
from contextlib import contextmanager
from sqlalchemy import create_engine, text, MetaData, Table
from sqlalchemy.engine import Engine, Connection
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


class DatabaseUtil:
    """数据库工具类"""
    
    def __init__(self, connection_string: str = None, **kwargs):
        """
        初始化数据库工具
        
        Args:
            connection_string: 数据库连接字符串
            **kwargs: 其他连接参数
        """
        self.connection_string = connection_string
        self.engine = None
        self.metadata = None
        
        # 连接池配置
        self.pool_config = {
            'poolclass': QueuePool,
            'pool_size': kwargs.get('pool_size', 5),
            'max_overflow': kwargs.get('max_overflow', 10),
            'pool_timeout': kwargs.get('pool_timeout', 30),
            'pool_recycle': kwargs.get('pool_recycle', 3600),
            'pool_pre_ping': kwargs.get('pool_pre_ping', True),
            'echo': kwargs.get('echo', False)
        }
        
        if connection_string:
            self.init_engine(connection_string)
    
    def init_engine(self, connection_string: str = None):
        """初始化数据库引擎"""
        try:
            conn_str = connection_string or self.connection_string
            if not conn_str:
                raise ValueError("Connection string is required")
            
            self.engine = create_engine(conn_str, **self.pool_config)
            self.metadata = MetaData()
            logger.info("Database engine initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database engine: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接的上下文管理器"""
        if not self.engine:
            raise RuntimeError("Database engine not initialized")
        
        connection = None
        try:
            connection = self.engine.connect()
            yield connection
        finally:
            if connection:
                connection.close()
    
    def test_connection(self) -> bool:
        """测试数据库连接"""
        try:
            with self.get_connection() as conn:
                result = conn.execute(text("SELECT 1"))
                result.fetchone()
            logger.info("Database connection test successful")
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
    
    def execute_query(self, query: str, params: Dict = None) -> List[Dict]:
        """
        执行查询并返回结果
        
        Args:
            query: SQL查询语句
            params: 查询参数
            
        Returns:
            查询结果列表
        """
        try:
            with self.get_connection() as conn:
                result = conn.execute(text(query), params or {})
                
                if result.returns_rows:
                    rows = []
                    for row in result:
                        rows.append(dict(row._mapping))
                    return rows
                else:
                    return [{"affected_rows": result.rowcount}]
                    
        except SQLAlchemyError as e:
            logger.error(f"Query execution failed: {e}")
            raise
    
    def execute_many(self, query: str, params_list: List[Dict]) -> int:
        """
        批量执行语句
        
        Args:
            query: SQL语句
            params_list: 参数列表
            
        Returns:
            影响的行数
        """
        total_affected = 0
        
        try:
            with self.get_connection() as conn:
                trans = conn.begin()
                try:
                    for params in params_list:
                        result = conn.execute(text(query), params)
                        total_affected += result.rowcount
                    trans.commit()
                except Exception:
                    trans.rollback()
                    raise
                    
        except SQLAlchemyError as e:
            logger.error(f"Batch execution failed: {e}")
            raise
        
        return total_affected
    
    def get_tables(self) -> List[str]:
        """获取所有表名"""
        try:
            with self.get_connection() as conn:
                self.metadata.reflect(bind=conn)
                return list(self.metadata.tables.keys())
        except Exception as e:
            logger.error(f"Failed to get tables: {e}")
            return []
    
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """获取表信息"""
        try:
            with self.get_connection() as conn:
                self.metadata.reflect(bind=conn, only=[table_name])
                
                if table_name not in self.metadata.tables:
                    return {}
                
                table = self.metadata.tables[table_name]
                
                return {
                    "name": table_name,
                    "columns": [
                        {
                            "name": col.name,
                            "type": str(col.type),
                            "nullable": col.nullable,
                            "primary_key": col.primary_key,
                            "foreign_keys": [str(fk) for fk in col.foreign_keys]
                        }
                        for col in table.columns
                    ],
                    "primary_key": [col.name for col in table.primary_key],
                    "foreign_keys": [
                        {
                            "column": list(fk.column_keys)[0],
                            "referred_table": fk.referred_table.name,
                            "referred_columns": list(fk.column_keys)
                        }
                        for fk in table.foreign_keys
                    ],
                    "indexes": [
                        {
                            "name": idx.name,
                            "columns": [col.name for col in idx.columns],
                            "unique": idx.unique
                        }
                        for idx in table.indexes
                    ]
                }
                
        except Exception as e:
            logger.error(f"Failed to get table info for {table_name}: {e}")
            return {}
    
    def get_sample_data(self, table_name: str, limit: int = 10) -> List[Dict]:
        """获取表的样本数据"""
        try:
            query = f"SELECT * FROM {table_name} LIMIT :limit"
            return self.execute_query(query, {"limit": limit})
        except Exception as e:
            logger.error(f"Failed to get sample data for {table_name}: {e}")
            return []
    
    def get_row_count(self, table_name: str) -> int:
        """获取表的行数"""
        try:
            query = f"SELECT COUNT(*) as count FROM {table_name}"
            result = self.execute_query(query)
            return result[0]["count"] if result else 0
        except Exception as e:
            logger.error(f"Failed to get row count for {table_name}: {e}")
            return 0
    
    def close(self):
        """关闭数据库连接"""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connection closed")
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()


# 便捷函数
def create_database_util(config: Any) -> DatabaseUtil:
    """
    从配置创建数据库工具实例
    
    Args:
        config: 配置对象或字典
        
    Returns:
        DatabaseUtil实例
    """
    if hasattr(config, 'database'):
        db_config = config.database
        connection_string = db_config.to_connection_string()
        
        return DatabaseUtil(
            connection_string=connection_string,
            pool_size=getattr(db_config, 'pool_size', 5),
            max_overflow=getattr(db_config, 'max_overflow', 10),
            pool_timeout=getattr(db_config, 'pool_timeout', 30),
            pool_recycle=getattr(db_config, 'pool_recycle', 3600),
            echo=getattr(db_config, 'echo', False)
        )
    elif isinstance(config, dict):
        return DatabaseUtil(**config)
    else:
        raise ValueError("Invalid configuration type")


def test_database_connection(config: Any) -> bool:
    """
    测试数据库连接
    
    Args:
        config: 配置对象
        
    Returns:
        连接是否成功
    """
    try:
        with create_database_util(config) as db:
            return db.test_connection()
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False