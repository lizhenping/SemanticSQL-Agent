"""数据库连接管理"""

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool
from typing import Dict, Any, List, Optional
import logging

from config.database import DatabaseConfig

logger = logging.getLogger(__name__)


class DatabaseConnector:
    """数据库连接器"""
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        """初始化数据库连接器
        
        Args:
            config: 数据库配置，如果为 None 则使用默认配置
        """
        self.config = config or DatabaseConfig()
        self._engine: Optional[Engine] = None
    
    @property
    def engine(self) -> Engine:
        """获取数据库引擎（懒加载）"""
        if self._engine is None:
            self._engine = self._create_engine()
        return self._engine
    
    def _create_engine(self) -> Engine:
        """创建数据库引擎"""
        logger.info(f"创建数据库引擎: {self.config.host}:{self.config.port}/{self.config.database}")
        
        # 创建引擎
        engine = create_engine(
            self.config.connection_uri,
            poolclass=QueuePool,
            **self.config.get_engine_kwargs()
        )
        
        # 测试连接
        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.fetchone()
            logger.info("数据库连接测试成功")
        except Exception as e:
            logger.error(f"数据库连接测试失败: {e}")
            raise
        
        return engine
    
    def execute_query(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """执行查询并返回结果
        
        Args:
            sql: SQL 查询语句
            params: 查询参数
            
        Returns:
            查询结果列表
        """
        with self.engine.connect() as conn:
            result = conn.execute(text(sql), params or {})
            
            # 转换为字典列表
            if result.returns_rows:
                columns = result.keys()
                return [dict(zip(columns, row)) for row in result]
            else:
                return []
    
    def get_tables(self) -> List[str]:
        """获取所有表名"""
        sql = """
        SELECT TABLE_NAME 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_SCHEMA = :database
        ORDER BY TABLE_NAME
        """
        
        results = self.execute_query(sql, {"database": self.config.database})
        return [row["TABLE_NAME"] for row in results]
    
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """获取表的详细信息
        
        Args:
            table_name: 表名
            
        Returns:
            表信息字典
        """
        # 获取列信息
        columns_sql = """
        SELECT 
            COLUMN_NAME,
            DATA_TYPE,
            IS_NULLABLE,
            COLUMN_KEY,
            COLUMN_DEFAULT,
            COLUMN_COMMENT
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = :database AND TABLE_NAME = :table
        ORDER BY ORDINAL_POSITION
        """
        
        columns = self.execute_query(
            columns_sql,
            {"database": self.config.database, "table": table_name}
        )
        
        # 获取表注释
        table_sql = """
        SELECT TABLE_COMMENT
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = :database AND TABLE_NAME = :table
        """
        
        table_info = self.execute_query(
            table_sql,
            {"database": self.config.database, "table": table_name}
        )
        
        return {
            "name": table_name,
            "comment": table_info[0]["TABLE_COMMENT"] if table_info else None,
            "columns": columns
        }
    
    def close(self):
        """关闭数据库连接"""
        if self._engine:
            self._engine.dispose()
            self._engine = None
            logger.info("数据库连接已关闭")