"""
trae_agent风格的数据库连接管理器
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from ..config.database_models import DatabaseConfig, DatabaseType


class DatabaseConnectionPool:
    """数据库连接池管理"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._engines: Dict[str, AsyncEngine] = {}
        self._sessions: Dict[str, AsyncSession] = {}
        self.logger = logging.getLogger("database.pool")
    
    def get_engine(self) -> AsyncEngine:
        """获取数据库引擎"""
        engine_key = f"{self.config.type.value}_{self.config.host}_{self.config.database}"
        
        if engine_key not in self._engines:
            self._engines[engine_key] = self._create_engine()
        
        return self._engines[engine_key]
    
    def _create_engine(self) -> AsyncEngine:
        """创建异步数据库引擎"""
        try:
            if self.config.type == DatabaseType.MYSQL:
                connection_string = self._build_mysql_connection_string()
            elif self.config.type == DatabaseType.POSTGRESQL:
                connection_string = self._build_postgresql_connection_string()
            elif self.config.type == DatabaseType.SQLITE:
                connection_string = self._build_sqlite_connection_string()
            else:
                raise ValueError(f"不支持的数据库类型: {self.config.type}")
            
            engine = create_async_engine(
                connection_string,
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow,
                pool_timeout=self.config.pool_timeout,
                pool_recycle=self.config.pool_recycle,
                echo=self.config.verbose
            )
            
            self.logger.info(f"创建数据库引擎成功: {self.config.database}@{self.config.host}")
            return engine
            
        except Exception as e:
            self.logger.error(f"创建数据库引擎失败: {e}")
            raise
    
    def _build_mysql_connection_string(self) -> str:
        """构建MySQL异步连接字符串"""
        base_url = f"mysql+aiomysql://{self.config.username}:{self.config.password}@{self.config.host}:{self.config.port}/{self.config.database}"
        params = []
        
        if self.config.charset:
            params.append(f"charset={self.config.charset}")
        if self.config.connect_timeout:
            params.append(f"connect_timeout={self.config.connect_timeout}")
        if self.config.ssl_mode:
            params.append(f"ssl_mode={self.config.ssl_mode}")
        
        if params:
            return f"{base_url}?{'&'.join(params)}"
        return base_url
    
    def _build_postgresql_connection_string(self) -> str:
        """构建PostgreSQL异步连接字符串"""
        base_url = f"postgresql+asyncpg://{self.config.username}:{self.config.password}@{self.config.host}:{self.config.port}/{self.config.database}"
        params = []
        
        if self.config.connect_timeout:
            params.append(f"connect_timeout={self.config.connect_timeout}")
        if self.config.ssl_mode:
            params.append(f"ssl={self.config.ssl_mode}")
        
        if params:
            return f"{base_url}?{'&'.join(params)}"
        return base_url
    
    def _build_sqlite_connection_string(self) -> str:
        """构建SQLite连接字符串"""
        return f"sqlite+aiosqlite:///{self.config.database}"
    
    @asynccontextmanager
    async def get_session(self) -> AsyncSession:
        """获取数据库会话"""
        engine = self.get_engine()
        async_session = sessionmaker(engine, class_=AsyncSession)
        
        async with async_session() as session:
            try:
                yield session
            except Exception as e:
                self.logger.error(f"数据库会话错误: {e}")
                raise
            finally:
                await session.close()
    
    async def test_connection(self) -> bool:
        """测试数据库连接"""
        try:
            engine = self.get_engine()
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                await conn.commit()
                return result.scalar() == 1
        except Exception as e:
            self.logger.error(f"数据库连接测试失败: {e}")
            return False
    
    async def close(self):
        """关闭所有连接"""
        for engine in self._engines.values():
            await engine.dispose()
        self._engines.clear()


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.pool = DatabaseConnectionPool(config)
        self.logger = logging.getLogger("database.manager")
    
    async def initialize(self) -> bool:
        """初始化数据库连接"""
        try:
            is_connected = await self.pool.test_connection()
            if is_connected:
                self.logger.info(f"数据库连接成功: {self.config.database}")
                return True
            else:
                self.logger.error(f"数据库连接失败: {self.config.database}")
                return False
        except Exception as e:
            self.logger.error(f"数据库初始化失败: {e}")
            return False
    
    async def get_tables(self) -> List[str]:
        """获取所有表名"""
        try:
            async with self.pool.get_session() as session:
                if self.config.type == DatabaseType.MYSQL:
                    result = await session.execute(
                        text("SHOW TABLES")
                    )
                elif self.config.type == DatabaseType.POSTGRESQL:
                    result = await session.execute(
                        text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
                    )
                elif self.config.type == DatabaseType.SQLITE:
                    result = await session.execute(
                        text("SELECT name FROM sqlite_master WHERE type='table'")
                    )
                else:
                    return []
                
                return [row[0] for row in result.fetchall()]
                
        except Exception as e:
            self.logger.error(f"获取表列表失败: {e}")
            return []
    
    async def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """获取表信息"""
        try:
            async with self.pool.get_session() as session:
                if self.config.type == DatabaseType.MYSQL:
                    # 获取列信息
                    columns_result = await session.execute(
                        text(f"DESCRIBE {table_name}")
                    )
                    
                    # 获取索引信息
                    indexes_result = await session.execute(
                        text(f"SHOW INDEX FROM {table_name}")
                    )
                    
                    columns = []
                    for row in columns_result.fetchall():
                        columns.append({
                            "name": row[0],
                            "type": row[1],
                            "nullable": row[2] == "YES",
                            "key": row[3],
                            "default": row[4],
                            "extra": row[5]
                        })
                    
                    indexes = []
                    for row in indexes_result.fetchall():
                        indexes.append({
                            "name": row[2],
                            "column": row[4],
                            "unique": row[1] == 0
                        })
                    
                    return {
                        "name": table_name,
                        "columns": columns,
                        "indexes": indexes
                    }
                
                elif self.config.type == DatabaseType.POSTGRESQL:
                    # PostgreSQL表信息
                    columns_result = await session.execute(
                        text("""
                            SELECT column_name, data_type, is_nullable, column_default
                            FROM information_schema.columns
                            WHERE table_name = :table_name
                        """),
                        {"table_name": table_name}
                    )
                    
                    columns = []
                    for row in columns_result.fetchall():
                        columns.append({
                            "name": row[0],
                            "type": row[1],
                            "nullable": row[2] == "YES",
                            "default": row[3]
                        })
                    
                    return {
                        "name": table_name,
                        "columns": columns
                    }
                
                elif self.config.type == DatabaseType.SQLITE:
                    # SQLite表信息
                    result = await session.execute(
                        text(f"PRAGMA table_info({table_name})")
                    )
                    
                    columns = []
                    for row in result.fetchall():
                        columns.append({
                            "name": row[1],
                            "type": row[2],
                            "nullable": not row[3],
                            "default": row[4],
                            "key": row[5]
                        })
                    
                    return {
                        "name": table_name,
                        "columns": columns
                    }
                
                else:
                    return {"name": table_name, "columns": []}
                
        except Exception as e:
            self.logger.error(f"获取表信息失败: {e}")
            return {"name": table_name, "columns": [], "error": str(e)}
    
    async def execute_query(self, sql: str, max_rows: int = 1000) -> Dict[str, Any]:
        """执行查询"""
        try:
            # 安全检查：只允许SELECT查询
            sql_upper = sql.strip().upper()
            if not sql_upper.startswith("SELECT"):
                return {
                    "success": False,
                    "error": "只允许执行SELECT查询",
                    "sql": sql
                }
            
            # 添加LIMIT限制
            if "LIMIT" not in sql_upper:
                sql = f"{sql} LIMIT {max_rows}"
            
            async with self.pool.get_session() as session:
                start_time = datetime.now()
                result = await session.execute(text(sql))
                end_time = datetime.now()
                
                # 获取结果
                rows = result.fetchall()
                columns = list(result.keys())
                
                # 格式化结果
                data = []
                for row in rows:
                    data.append(dict(zip(columns, row)))
                
                return {
                    "success": True,
                    "sql": sql,
                    "columns": columns,
                    "data": data,
                    "row_count": len(data),
                    "execution_time": (end_time - start_time).total_seconds(),
                    "truncated": len(data) >= max_rows
                }
                
        except Exception as e:
            self.logger.error(f"执行查询失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "sql": sql
            }
    
    async def validate_sql(self, sql: str) -> Dict[str, Any]:
        """验证SQL语法"""
        try:
            # 使用EXPLAIN验证SQL
            explain_sql = f"EXPLAIN {sql}"
            
            async with self.pool.get_session() as session:
                result = await session.execute(text(explain_sql))
                plan = [dict(row) for row in result.fetchall()]
                
                return {
                    "success": True,
                    "sql": sql,
                    "valid": True,
                    "execution_plan": plan
                }
                
        except Exception as e:
            return {
                "success": False,
                "sql": sql,
                "valid": False,
                "error": str(e)
            }
    
    async def get_database_info(self) -> Dict[str, Any]:
        """获取数据库信息"""
        try:
            tables = await self.get_tables()
            
            # 获取数据库版本
            async with self.pool.get_session() as session:
                if self.config.type == DatabaseType.MYSQL:
                    version_result = await session.execute(text("SELECT VERSION()"))
                    version = version_result.scalar()
                elif self.config.type == DatabaseType.POSTGRESQL:
                    version_result = await session.execute(text("SELECT version()"))
                    version = version_result.scalar()
                elif self.config.type == DatabaseType.SQLITE:
                    version_result = await session.execute(text("SELECT sqlite_version()"))
                    version = version_result.scalar()
                else:
                    version = "unknown"
            
            return {
                "database": self.config.database,
                "type": self.config.type.value,
                "host": f"{self.config.host}:{self.config.port}",
                "tables_count": len(tables),
                "tables": tables,
                "version": version
            }
            
        except Exception as e:
            self.logger.error(f"获取数据库信息失败: {e}")
            return {
                "error": str(e),
                "database": self.config.database
            }
    
    async def close(self):
        """关闭数据库连接"""
        await self.pool.close()