"""数据库连接管理器

负责管理MySQL数据库连接的生命周期。
"""

import logging
from typing import Optional, Dict, Any
import pymysql
from pymysql.cursors import DictCursor
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class MySQLConnectionManager:
    """MySQL连接管理器
    
    职责：
    1. 管理数据库连接
    2. 提供连接池支持
    3. 处理连接重试
    4. 管理事务
    """
    
    def __init__(self):
        """初始化连接管理器"""
        self.connection = None
        self.config = {}
        self._transaction_active = False
    
    def connect(self, **kwargs) -> None:
        """建立数据库连接
        
        参数:
            host: 主机地址
            port: 端口号（默认3306）
            user: 用户名
            password: 密码
            database: 数据库名（可选）
            charset: 字符集（默认utf8mb4）
            **kwargs: 其他连接参数
        """
        try:
            # 保存配置
            self.config = {
                'host': kwargs.get('host', 'localhost'),
                'port': kwargs.get('port', 3306),
                'user': kwargs.get('user'),
                'password': kwargs.get('password'),
                'database': kwargs.get('database'),
                'charset': kwargs.get('charset', 'utf8mb4'),
                'cursorclass': DictCursor,
                'autocommit': kwargs.get('autocommit', True)
            }
            
            # 移除None值
            self.config = {k: v for k, v in self.config.items() if v is not None}
            
            # 建立连接
            self.connection = pymysql.connect(**self.config)
            
            logger.info(f"Successfully connected to MySQL database at {self.config.get('host')}:{self.config.get('port')}")
            
        except Exception as e:
            logger.error(f"Failed to connect to MySQL database: {e}")
            raise
    
    def disconnect(self) -> None:
        """断开数据库连接"""
        if self.connection:
            try:
                if self._transaction_active:
                    self.rollback()
                self.connection.close()
                logger.info("Disconnected from MySQL database")
            except Exception as e:
                logger.error(f"Error while disconnecting: {e}")
            finally:
                self.connection = None
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        if not self.connection:
            return False
        
        try:
            self.connection.ping(reconnect=False)
            return True
        except:
            return False
    
    def ensure_connected(self) -> None:
        """确保连接可用，必要时重连"""
        if not self.is_connected():
            if self.config:
                logger.info("Reconnecting to database...")
                self.connect(**self.config)
            else:
                raise RuntimeError("No connection configuration available for reconnect")
    
    def get_connection(self):
        """获取数据库连接对象"""
        self.ensure_connected()
        return self.connection
    
    def get_cursor(self, cursor_type=None):
        """获取游标对象
        
        参数:
            cursor_type: 游标类型（默认使用DictCursor）
            
        返回:
            游标对象
        """
        self.ensure_connected()
        if cursor_type:
            return self.connection.cursor(cursor_type)
        return self.connection.cursor()
    
    @contextmanager
    def cursor_context(self, cursor_type=None):
        """游标上下文管理器
        
        使用方式:
            with connection_manager.cursor_context() as cursor:
                cursor.execute(query)
                results = cursor.fetchall()
        """
        cursor = None
        try:
            cursor = self.get_cursor(cursor_type)
            yield cursor
        finally:
            if cursor:
                cursor.close()
    
    def begin_transaction(self) -> None:
        """开始事务"""
        if self._transaction_active:
            raise RuntimeError("Transaction already active")
        
        self.ensure_connected()
        self.connection.begin()
        self._transaction_active = True
        logger.debug("Transaction started")
    
    def commit(self) -> None:
        """提交事务"""
        if not self._transaction_active:
            logger.warning("No active transaction to commit")
            return
        
        try:
            self.connection.commit()
            self._transaction_active = False
            logger.debug("Transaction committed")
        except Exception as e:
            logger.error(f"Failed to commit transaction: {e}")
            raise
    
    def rollback(self) -> None:
        """回滚事务"""
        if not self._transaction_active:
            logger.warning("No active transaction to rollback")
            return
        
        try:
            self.connection.rollback()
            self._transaction_active = False
            logger.debug("Transaction rolled back")
        except Exception as e:
            logger.error(f"Failed to rollback transaction: {e}")
            raise
    
    @contextmanager
    def transaction(self):
        """事务上下文管理器
        
        使用方式:
            with connection_manager.transaction():
                # 执行多个数据库操作
                # 如果发生异常会自动回滚
                # 正常结束会自动提交
        """
        self.begin_transaction()
        try:
            yield
            self.commit()
        except Exception:
            self.rollback()
            raise
    
    def test_connection(self) -> bool:
        """测试数据库连接
        
        返回:
            连接是否正常
        """
        try:
            with self.cursor_context() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                return result is not None
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False