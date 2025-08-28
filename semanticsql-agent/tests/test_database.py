"""
数据库连接和查询测试
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from ..database.connection_manager import DatabaseManager, DatabaseConnectionPool
from ..config.database_models import DatabaseConfig, DatabaseType


class TestDatabase:
    """数据库测试"""
    
    def test_database_config_creation(self):
        """测试数据库配置创建"""
        config = DatabaseConfig(
            type="mysql",
            host="localhost",
            port=3306,
            database="testdb",
            username="user",
            password="pass"
        )
        
        assert config.type == DatabaseType.MYSQL
        assert config.host == "localhost"
        assert config.port == 3306
        assert config.database == "testdb"
    
    def test_connection_string_mysql(self):
        """测试MySQL连接字符串"""
        config = DatabaseConfig(
            type="mysql",
            host="localhost",
            port=3306,
            database="testdb",
            username="user",
            password="pass"
        )
        
        connection_string = config.connection_string
        assert "mysql+pymysql://user:pass@localhost:3306/testdb" in connection_string
    
    def test_connection_string_postgresql(self):
        """测试PostgreSQL连接字符串"""
        config = DatabaseConfig(
            type="postgresql",
            host="localhost",
            port=5432,
            database="testdb",
            username="user",
            password="pass"
        )
        
        connection_string = config.connection_string
        assert "postgresql://user:pass@localhost:5432/testdb" in connection_string
    
    @pytest.mark.asyncio
    async def test_database_manager_initialization(self):
        """测试数据库管理器初始化"""
        config = DatabaseConfig(
            type="mysql",
            host="localhost",
            port=3306,
            database="testdb",
            username="user",
            password="pass"
        )
        
        # Mock数据库连接
        with patch.object(DatabaseConnectionPool, 'test_connection') as mock_test:
            mock_test.return_value = True
            
            manager = DatabaseManager(config)
            result = await manager.initialize()
            
            assert result is True
            mock_test.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_database_manager_connection_failure(self):
        """测试数据库连接失败"""
        config = DatabaseConfig(
            type="mysql",
            host="invalid_host",
            port=3306,
            database="testdb",
            username="user",
            password="pass"
        )
        
        # Mock数据库连接失败
        with patch.object(DatabaseConnectionPool, 'test_connection') as mock_test:
            mock_test.return_value = False
            
            manager = DatabaseManager(config)
            result = await manager.initialize()
            
            assert result is False
    
    def test_database_type_enum(self):
        """测试数据库类型枚举"""
        assert DatabaseType.MYSQL.value == "mysql"
        assert DatabaseType.POSTGRESQL.value == "postgresql"
        assert DatabaseType.SQLITE.value == "sqlite"
    
    def test_database_config_from_env(self):
        """测试从环境变量创建配置"""
        import os
        
        os.environ["DB_TYPE"] = "postgresql"
        os.environ["DB_HOST"] = "test-host"
        os.environ["DB_PORT"] = "5432"
        os.environ["DB_NAME"] = "test-db"
        os.environ["DB_USER"] = "test-user"
        os.environ["DB_PASSWORD"] = "test-pass"
        
        config = DatabaseConfig.from_env()
        
        assert config.type == DatabaseType.POSTGRESQL
        assert config.host == "test-host"
        assert config.port == 5432
        assert config.database == "test-db"
        assert config.username == "test-user"
        assert config.password == "test-pass"
        
        # 清理环境变量
        del os.environ["DB_TYPE"]
        del os.environ["DB_HOST"]
        del os.environ["DB_PORT"]
        del os.environ["DB_NAME"]
        del os.environ["DB_USER"]
        del os.environ["DB_PASSWORD"]