"""
数据库管理器测试
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from utils.database import DatabaseManager
from utils.database_config import DatabaseConfig, DatabaseType


class TestDatabaseManager:
    """测试数据库管理器"""
    
    @pytest.fixture
    def mysql_config(self):
        """MySQL配置"""
        return DatabaseConfig(
            type=DatabaseType.MYSQL,
            host="localhost",
            port=3306,
            database="testdb",
            username="user",
            password="pass"
        )
    
    @pytest.fixture
    def postgresql_config(self):
        """PostgreSQL配置"""
        return DatabaseConfig(
            type=DatabaseType.POSTGRESQL,
            host="localhost", 
            port=5432,
            database="testdb",
            username="user",
            password="pass"
        )
    
    def test_initialization_mysql(self, mysql_config):
        """测试MySQL初始化"""
        with patch('pymysql.connect'):
            manager = DatabaseManager(mysql_config)
            assert manager.config.type == DatabaseType.MYSQL
            assert manager.config.host == "localhost"
    
    def test_initialization_postgresql(self, postgresql_config):
        """测试PostgreSQL初始化"""
        with patch('psycopg2.connect'):
            manager = DatabaseManager(postgresql_config)
            assert manager.config.type == DatabaseType.POSTGRESQL
    
    def test_connection_success(self, mysql_config):
        """测试连接成功"""
        with patch('pymysql.connect') as mock_connect:
            mock_connection = Mock()
            mock_connect.return_value = mock_connection
            
            manager = DatabaseManager(mysql_config)
            result = manager.initialize()
            
            assert result is True
            assert mock_connect.called
    
    def test_connection_failure(self, mysql_config):
        """测试连接失败"""
        with patch('pymysql.connect') as mock_connect:
            mock_connect.side_effect = Exception("Connection failed")
            
            manager = DatabaseManager(mysql_config)
            result = manager.initialize()
            
            assert result is False
    
    def test_execute_query_success(self, mysql_config):
        """测试查询执行成功"""
        with patch('pymysql.connect') as mock_connect:
            mock_connection = Mock()
            mock_cursor = Mock()
            mock_cursor.fetchall.return_value = [{"id": 1, "name": "test"}]
            mock_cursor.description = [("id",), ("name",)]
            mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
            mock_connect.return_value = mock_connection
            
            manager = DatabaseManager(mysql_config)
            manager.initialize()
            
            result = manager._execute_query("SELECT * FROM users")
            
            assert result["success"] is True
            assert len(result["data"]) == 1
    
    def test_execute_query_error(self, mysql_config):
        """测试查询执行错误"""
        with patch('pymysql.connect') as mock_connect:
            mock_connection = Mock()
            mock_cursor = Mock()
            mock_cursor.execute.side_effect = Exception("Query error")
            mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
            mock_connect.return_value = mock_connection
            
            manager = DatabaseManager(mysql_config)
            manager.initialize()
            
            result = manager._execute_query("INVALID SQL")
            
            assert result["success"] is False
            assert "error" in result
    
    def test_get_tables(self, mysql_config):
        """测试获取表列表"""
        with patch('pymysql.connect') as mock_connect:
            mock_connection = Mock()
            mock_cursor = Mock()
            mock_cursor.fetchall.return_value = [
                {"table_name": "users"},
                {"table_name": "orders"}
            ]
            mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
            mock_connect.return_value = mock_connection
            
            manager = DatabaseManager(mysql_config)
            manager.initialize()
            
            tables = manager.get_tables()
            
            assert len(tables) == 2
            assert "users" in tables
            assert "orders" in tables
    
    def test_get_table_info(self, mysql_config):
        """测试获取表信息"""
        with patch('pymysql.connect') as mock_connect:
            mock_connection = Mock()
            mock_cursor = Mock()
            mock_cursor.fetchall.return_value = [
                {
                    "name": "id",
                    "type": "int",
                    "nullable": False,
                    "key": "PRI"
                },
                {
                    "name": "name", 
                    "type": "varchar",
                    "nullable": True,
                    "key": ""
                }
            ]
            mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
            mock_connect.return_value = mock_connection
            
            manager = DatabaseManager(mysql_config)
            manager.initialize()
            
            table_info = manager.get_table_info("users")
            
            assert "columns" in table_info
            assert len(table_info["columns"]) == 2
    
    def test_close_connection(self, mysql_config):
        """测试关闭连接"""
        with patch('pymysql.connect') as mock_connect:
            mock_connection = Mock()
            mock_connect.return_value = mock_connection
            
            manager = DatabaseManager(mysql_config)
            manager.initialize()
            manager.close()
            
            assert mock_connection.close.called