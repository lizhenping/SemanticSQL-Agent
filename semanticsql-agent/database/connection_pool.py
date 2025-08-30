"""
高性能数据库连接池管理器
实现连接复用、缓存和异步支持
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Union
from contextlib import contextmanager, asynccontextmanager
from datetime import datetime, timedelta
import threading
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import create_engine, text, pool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from config.trae_config import DatabaseConfig


class SchemaCache:
    """数据库Schema缓存"""
    
    def __init__(self, ttl_seconds: int = 3600):
        self._cache: Dict[str, Any] = {}
        self._timestamps: Dict[str, datetime] = {}
        self.ttl = timedelta(seconds=ttl_seconds)
        self._lock = threading.Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存数据"""
        with self._lock:
            if key in self._cache:
                if datetime.now() - self._timestamps[key] < self.ttl:
                    return self._cache[key]
                else:
                    # 缓存过期
                    del self._cache[key]
                    del self._timestamps[key]
        return None
    
    def set(self, key: str, value: Any):
        """设置缓存数据"""
        with self._lock:
            self._cache[key] = value
            self._timestamps[key] = datetime.now()
    
    def clear(self):
        """清除所有缓存"""
        with self._lock:
            self._cache.clear()
            self._timestamps.clear()


class OptimizedDatabaseManager:
    """优化的数据库管理器，支持连接池、缓存和并发"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.sync_engine = None
        self.async_engine = None
        self.session_factory = None
        self.async_session_factory = None
        self.logger = logging.getLogger(__name__)
        
        # Schema缓存
        self.schema_cache = SchemaCache(ttl_seconds=3600)
        
        # 查询结果缓存
        self.query_cache = SchemaCache(ttl_seconds=300)
        
        # 线程池执行器
        self.executor = ThreadPoolExecutor(max_workers=config.pool_size)
        
        # 连接池统计
        self.stats = {
            "connections_created": 0,
            "connections_reused": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "queries_executed": 0
        }
        
        self.logger.info(f"初始化优化数据库管理器: {config.type}://{config.host}:{config.port}/{config.database}")
    
    def initialize(self) -> bool:
        """初始化数据库连接池"""
        try:
            connection_string = self._build_connection_string()
            
            # 创建同步引擎（使用QueuePool连接池）
            self.sync_engine = create_engine(
                connection_string,
                poolclass=pool.QueuePool,
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow,
                pool_timeout=self.config.pool_timeout,
                pool_recycle=self.config.pool_recycle,
                pool_pre_ping=self.config.pool_pre_ping,
                echo=False,
                future=True
            )
            
            # 创建异步引擎（如果支持）
            if self.config.type != "sqlite":
                async_connection_string = self._build_async_connection_string()
                self.async_engine = create_async_engine(
                    async_connection_string,
                    pool_size=self.config.pool_size,
                    max_overflow=self.config.max_overflow,
                    pool_timeout=self.config.pool_timeout,
                    pool_recycle=self.config.pool_recycle,
                    pool_pre_ping=self.config.pool_pre_ping,
                    echo=False
                )
                self.async_session_factory = async_sessionmaker(
                    self.async_engine, 
                    class_=AsyncSession,
                    expire_on_commit=False
                )
            
            # 测试连接
            with self.sync_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                
            self.session_factory = sessionmaker(bind=self.sync_engine)
            self.logger.info("数据库连接池初始化成功")
            self.stats["connections_created"] += 1
            return True
            
        except Exception as e:
            self.logger.error(f"数据库连接池初始化失败: {e}")
            return False
    
    def _build_connection_string(self) -> str:
        """构建同步数据库连接字符串"""
        if self.config.type == "mysql":
            return f"mysql+pymysql://{self.config.username}:{self.config.password}@{self.config.host}:{self.config.port}/{self.config.database}?charset={self.config.charset}"
        elif self.config.type == "postgresql":
            return f"postgresql+psycopg2://{self.config.username}:{self.config.password}@{self.config.host}:{self.config.port}/{self.config.database}"
        elif self.config.type == "sqlite":
            return f"sqlite:///{self.config.database}.db"
        else:
            raise ValueError(f"不支持的数据库类型: {self.config.type}")
    
    def _build_async_connection_string(self) -> str:
        """构建异步数据库连接字符串"""
        if self.config.type == "mysql":
            return f"mysql+aiomysql://{self.config.username}:{self.config.password}@{self.config.host}:{self.config.port}/{self.config.database}?charset={self.config.charset}"
        elif self.config.type == "postgresql":
            return f"postgresql+asyncpg://{self.config.username}:{self.config.password}@{self.config.host}:{self.config.port}/{self.config.database}"
        else:
            raise ValueError(f"不支持异步连接的数据库类型: {self.config.type}")
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接（上下文管理器）"""
        conn = self.sync_engine.connect()
        try:
            self.stats["connections_reused"] += 1
            yield conn
        finally:
            conn.close()
    
    @asynccontextmanager
    async def get_async_connection(self):
        """获取异步数据库连接"""
        if not self.async_engine:
            raise RuntimeError("异步引擎未初始化")
        async with self.async_engine.connect() as conn:
            self.stats["connections_reused"] += 1
            yield conn
    
    def get_tables(self, use_cache: bool = True) -> List[str]:
        """获取所有表名（带缓存）"""
        cache_key = "all_tables"
        
        if use_cache:
            cached = self.schema_cache.get(cache_key)
            if cached:
                self.stats["cache_hits"] += 1
                return cached
        
        self.stats["cache_misses"] += 1
        
        try:
            with self.get_connection() as conn:
                if self.config.type == "mysql":
                    result = conn.execute(text("SHOW TABLES"))
                    tables = [row[0] for row in result.fetchall()]
                elif self.config.type == "postgresql":
                    result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
                    tables = [row[0] for row in result.fetchall()]
                elif self.config.type == "sqlite":
                    result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
                    tables = [row[0] for row in result.fetchall()]
                
                self.schema_cache.set(cache_key, tables)
                return tables
                
        except Exception as e:
            self.logger.error(f"获取表列表失败: {e}")
            return []
    
    def get_table_info(self, table_name: str, use_cache: bool = True) -> Dict[str, Any]:
        """获取表信息（带缓存）"""
        cache_key = f"table_info_{table_name}"
        
        if use_cache:
            cached = self.schema_cache.get(cache_key)
            if cached:
                self.stats["cache_hits"] += 1
                return cached
        
        self.stats["cache_misses"] += 1
        
        try:
            with self.get_connection() as conn:
                info = {"name": table_name, "columns": [], "indexes": [], "constraints": []}
                
                if self.config.type == "mysql":
                    # 获取列信息
                    result = conn.execute(text(f"DESCRIBE `{table_name}`"))
                    for row in result.fetchall():
                        info["columns"].append({
                            "name": row[0],
                            "type": str(row[1]),
                            "nullable": row[2] == "YES",
                            "key": row[3],
                            "default": row[4],
                            "extra": row[5]
                        })
                    
                    # 获取索引信息
                    result = conn.execute(text(f"SHOW INDEX FROM `{table_name}`"))
                    for row in result.fetchall():
                        info["indexes"].append({
                            "name": row[2],
                            "column": row[4],
                            "unique": not row[1],
                            "type": row[10]
                        })
                        
                elif self.config.type == "postgresql":
                    # PostgreSQL实现
                    result = conn.execute(text(f"""
                        SELECT column_name, data_type, is_nullable, column_default
                        FROM information_schema.columns
                        WHERE table_name = '{table_name}'
                    """))
                    for row in result.fetchall():
                        info["columns"].append({
                            "name": row[0],
                            "type": row[1],
                            "nullable": row[2] == "YES",
                            "default": row[3]
                        })
                
                self.schema_cache.set(cache_key, info)
                return info
                
        except Exception as e:
            self.logger.error(f"获取表信息失败: {e}")
            return {}
    
    def execute_query(self, query: str, params: Dict = None, use_cache: bool = False) -> List[Dict]:
        """执行查询（带可选缓存）"""
        cache_key = f"query_{query}_{str(params)}"
        
        if use_cache:
            cached = self.query_cache.get(cache_key)
            if cached:
                self.stats["cache_hits"] += 1
                return cached
        
        self.stats["queries_executed"] += 1
        
        try:
            with self.get_connection() as conn:
                result = conn.execute(text(query), params or {})
                data = [dict(row._mapping) for row in result.fetchall()]
                
                if use_cache:
                    self.query_cache.set(cache_key, data)
                
                return data
                
        except Exception as e:
            self.logger.error(f"查询执行失败: {e}")
            raise
    
    async def execute_query_async(self, query: str, params: Dict = None) -> List[Dict]:
        """异步执行查询"""
        if not self.async_engine:
            # 回退到同步执行
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self.executor,
                self.execute_query,
                query,
                params,
                False
            )
        
        self.stats["queries_executed"] += 1
        
        async with self.get_async_connection() as conn:
            result = await conn.execute(text(query), params or {})
            return [dict(row._mapping) for row in result.fetchall()]
    
    def execute_many(self, queries: List[str], parallel: bool = True) -> List[Any]:
        """批量执行查询"""
        if parallel:
            # 并行执行
            futures = []
            for query in queries:
                future = self.executor.submit(self.execute_query, query)
                futures.append(future)
            
            results = []
            for future in futures:
                try:
                    results.append(future.result(timeout=self.config.connection_timeout))
                except Exception as e:
                    self.logger.error(f"并行查询失败: {e}")
                    results.append(None)
            return results
        else:
            # 串行执行
            results = []
            for query in queries:
                try:
                    results.append(self.execute_query(query))
                except Exception as e:
                    self.logger.error(f"查询失败: {e}")
                    results.append(None)
            return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取连接池统计信息"""
        pool_status = {}
        if self.sync_engine and hasattr(self.sync_engine.pool, 'status'):
            pool_status = {
                "size": self.sync_engine.pool.size(),
                "checked_in": self.sync_engine.pool.checkedin(),
                "overflow": self.sync_engine.pool.overflow(),
                "total": self.sync_engine.pool.size() + self.sync_engine.pool.overflow()
            }
        
        return {
            **self.stats,
            "pool_status": pool_status,
            "cache_size": len(self.schema_cache._cache),
            "query_cache_size": len(self.query_cache._cache)
        }
    
    def clear_cache(self):
        """清除所有缓存"""
        self.schema_cache.clear()
        self.query_cache.clear()
        self.logger.info("所有缓存已清除")
    
    def close(self):
        """关闭数据库连接池"""
        if self.sync_engine:
            self.sync_engine.dispose()
        if self.async_engine:
            asyncio.create_task(self.async_engine.dispose())
        self.executor.shutdown(wait=True)
        self.logger.info("数据库连接池已关闭")
    
    def __del__(self):
        """析构函数"""
        try:
            self.close()
        except:
            pass