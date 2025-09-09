"""
配置系统测试
"""

import pytest
import tempfile
import os
from pathlib import Path

from config.settings import Settings
from utils.database_config import DatabaseConfig, DatabaseType


class TestConfig:
    """配置系统测试"""
    
    def test_settings_with_env(self):
        """测试Settings环境变量配置"""
        # 设置测试环境变量
        test_env = {
            "SEMANTICSQL_LLM_MODEL": "Qwen3-14B",
            "SEMANTICSQL_LLM_BASE_URL": "http://test-server:9991/v1", 
            "SEMANTICSQL_LLM_TEMPERATURE": "0.1",
            "SEMANTICSQL_DB_HOST": "test-db-host",
            "SEMANTICSQL_DB_DATABASE": "test_db",
            "SEMANTICSQL_NEO4J_PASSWORD": "test-password",
            "SEMANTICSQL_FAIL_FAST": "false"  # 测试环境允许非严格模式
        }
        
        # 保存原环境变量
        original_env = {}
        for key, value in test_env.items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value
        
        try:
            settings = Settings()
            assert settings.app_name == "SemanticSQL Agent"
            assert settings.llm_model == "Qwen3-14B"
            assert settings.llm_base_url == "http://test-server:9991/v1"
            assert settings.llm_temperature == 0.1
            assert settings.db_host == "test-db-host"
            assert settings.db_database == "test_db"
            assert settings.neo4j_password == "test-password"
            assert settings.fail_fast == False
            
        finally:
            # 恢复原环境变量
            for key, original_value in original_env.items():
                if original_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = original_value
    
    def test_database_config_from_settings(self):
        """测试从统一Settings创建数据库配置 - 推荐方式"""
        # 设置测试环境变量
        test_env = {
            "SEMANTICSQL_DB_HOST": "test-mysql-host",
            "SEMANTICSQL_DB_PORT": "3306",
            "SEMANTICSQL_DB_DATABASE": "test_database",
            "SEMANTICSQL_DB_USERNAME": "test_user",
            "SEMANTICSQL_DB_PASSWORD": "test_password"
        }
        
        # 保存和设置环境变量
        original_env = {}
        for key, value in test_env.items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value
        
        try:
            # 使用from_settings方法（推荐）
            config = DatabaseConfig.from_settings()
            assert config.type == DatabaseType.MYSQL
            assert config.host == "test-mysql-host"
            assert config.port == 3306
            assert config.database == "test_database"
            assert config.username == "test_user"
            assert config.password == "test_password"
            
        finally:
            # 恢复环境变量
            for key, original_value in original_env.items():
                if original_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = original_value
    
    def test_database_config_postgresql(self):
        """测试PostgreSQL数据库配置"""
        config = DatabaseConfig(
            type=DatabaseType.POSTGRESQL,
            host="localhost",
            port=5432,
            database="testdb",
            username="user",
            password="pass"
        )
        assert config.type == DatabaseType.POSTGRESQL
        assert config.port == 5432
    
    def test_fail_fast_strategy(self):
        """测试fail-fast策略"""
        # 测试fail_fast=True时的行为
        os.environ["SEMANTICSQL_FAIL_FAST"] = "true"
        
        try:
            settings = Settings()
            assert settings.fail_fast == True
            
            # 测试fail_fast=False时的行为  
            os.environ["SEMANTICSQL_FAIL_FAST"] = "false"
            settings = Settings()
            assert settings.fail_fast == False
            
        finally:
            os.environ.pop("SEMANTICSQL_FAIL_FAST", None)
    
    def test_settings_validation(self):
        """测试Settings验证"""
        settings = Settings()
        # Pydantic自动验证
        assert isinstance(settings.max_steps, int)
        assert isinstance(settings.enable_reflection, bool)
        assert isinstance(settings.llm_temperature, float)
        assert isinstance(settings.fail_fast, bool)
    
    def test_database_config_validation(self):
        """测试DatabaseConfig验证"""
        # 有效配置
        config = DatabaseConfig(
            type=DatabaseType.MYSQL,
            database="testdb"
        )
        assert config.database == "testdb"
        
        # 测试枚举类型
        assert config.type in [DatabaseType.MYSQL, DatabaseType.POSTGRESQL, DatabaseType.SQLITE]