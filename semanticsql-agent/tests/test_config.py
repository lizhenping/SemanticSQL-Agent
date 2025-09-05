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
    
    def test_settings_default(self):
        """测试Settings默认值"""
        settings = Settings()
        assert settings.app_name == "SemanticSQL Agent"
        assert settings.llm_model == "Qwen3-14B"
        assert settings.llm_base_url == "http://192.168.200.216:9991/v1"
        assert settings.llm_temperature == 0.1
    
    def test_database_config_mysql(self):
        """测试MySQL数据库配置"""
        config = DatabaseConfig(
            type=DatabaseType.MYSQL,
            host="localhost",
            port=3306,
            database="testdb",
            username="user",
            password="pass"
        )
        assert config.type == DatabaseType.MYSQL
        assert config.host == "localhost"
        assert config.port == 3306
    
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
    
    def test_settings_validation(self):
        """测试Settings验证"""
        settings = Settings()
        # Pydantic自动验证
        assert isinstance(settings.max_steps, int)
        assert isinstance(settings.enable_reflection, bool)
        assert isinstance(settings.llm_temperature, float)
    
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