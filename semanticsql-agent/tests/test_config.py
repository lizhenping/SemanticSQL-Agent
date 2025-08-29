"""
配置系统测试
"""

import pytest
import tempfile
import os
from pathlib import Path

from ..config.trae_config import TraeConfig, LLMConfig, DatabaseConfig, AgentConfig


class TestConfig:
    """配置系统测试"""
    
    def test_llm_config_default(self):
        """测试LLM配置默认值"""
        config = LLMConfig()
        assert config.model == "Qwen3-14B"
        assert config.base_url == "http://192.168.200.216:9009/v1"
        assert config.temperature == 0.1
    
    def test_database_config_mysql_connection_string(self):
        """测试MySQL连接字符串"""
        config = DatabaseConfig(
            type="mysql",
            host="localhost",
            port=3306,
            database="testdb",
            username="user",
            password="pass"
        )
        assert "mysql+pymysql://user:pass@localhost:3306/testdb" in config.connection_string
    
    def test_database_config_postgresql_connection_string(self):
        """测试PostgreSQL连接字符串"""
        config = DatabaseConfig(
            type="postgresql",
            host="localhost",
            port=5432,
            database="testdb",
            username="user",
            password="pass"
        )
        assert "postgresql://user:pass@localhost:5432/testdb" in config.connection_string
    
    def test_trae_config_from_dict(self):
        """测试从字典创建配置"""
        config_dict = {
            "llm": {
                "model": "test-model",
                "base_url": "http://test.com/v1"
            },
            "database": {
                "type": "mysql",
                "host": "test-host",
                "database": "test-db"
            }
        }
        
        config = TraeConfig.from_dict(config_dict)
        assert config.llm.model == "test-model"
        assert config.database.host == "test-host"
    
    def test_trae_config_from_yaml(self):
        """测试从YAML文件创建配置"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml_content = """
llm:
  model: "test-model"
  base_url: "http://test.com/v1"
database:
  type: "mysql"
  host: "test-host"
  database: "test-db"
"""
            f.write(yaml_content)
            f.flush()
            
            config = TraeConfig.from_yaml(f.name)
            assert config.llm.model == "test-model"
            assert config.database.host == "test-host"
            
            os.unlink(f.name)
    
    def test_trae_config_from_env(self):
        """测试从环境变量创建配置"""
        os.environ["LLM_MODEL"] = "env-model"
        os.environ["DB_HOST"] = "env-host"
        
        config = TraeConfig.from_env()
        assert config.llm.model == "env-model"
        assert config.database.host == "env-host"
        
        # 清理环境变量
        del os.environ["LLM_MODEL"]
        del os.environ["DB_HOST"]
    
    def test_trae_config_validation(self):
        """测试配置验证"""
        config = TraeConfig()
        assert not config.validate()  # 缺少必要的数据库名称
        
        config.database.database = "test-db"
        assert config.validate()
    
    def test_config_save_yaml(self):
        """测试保存YAML配置"""
        config = TraeConfig()
        config.llm.model = "test-model"
        config.database.database = "test-db"
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_config.yaml"
            config.save_yaml(str(config_path))
            
            loaded_config = TraeConfig.from_yaml(str(config_path))
            assert loaded_config.llm.model == "test-model"
            assert loaded_config.database.database == "test-db"