"""
Agent测试
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from agent.smart_sql_agent import SmartSQLAgent
from config.settings import Settings
from utils.database_config import DatabaseConfig, DatabaseType
from models.schemas import AgentStep, AgentStepType, SQLQueryResult


class TestSmartSQLAgent:
    """测试智能SQL代理"""
    
    @pytest.fixture
    def settings(self):
        """创建测试配置"""
        return Settings()
    
    @pytest.fixture  
    def db_config(self):
        """创建测试数据库配置"""
        return DatabaseConfig(
            type=DatabaseType.MYSQL,
            database="testdb"
        )
    
    @pytest.fixture
    def agent(self, settings, db_config):
        """创建测试用的agent"""
        with patch('utils.database.DatabaseManager'):
            agent = SmartSQLAgent(settings, db_config)
            agent.db_manager = Mock()
            agent.db_manager.initialize.return_value = True
            return agent
    
    def test_initialization(self, agent):
        """测试初始化"""
        assert agent.settings is not None
        assert agent.db_config is not None
        assert len(agent.tools) > 0
    
    def test_query_success(self, agent):
        """测试成功查询"""
        # 模拟LLM响应
        with patch.object(agent, 'llm_client') as mock_llm:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "Action: generate_sql\nAction Input: {\"question\": \"test\"}"
            mock_llm.chat.completions.create.return_value = mock_response
            
            # 模拟工具执行
            mock_tool = Mock()
            mock_tool.execute.return_value = {
                "success": True,
                "data": {
                    "sql": "SELECT COUNT(*) FROM users",
                    "data": [{"count": 100}],
                    "row_count": 1
                }
            }
            agent.tools["generate_sql"] = mock_tool
            
            result = agent.query("统计用户数量")
            
            assert isinstance(result, SQLQueryResult)
            assert result.success is True
    
    def test_query_failure(self, agent):
        """测试查询失败"""
        with patch.object(agent, '_execute_react_loop') as mock_loop:
            mock_loop.side_effect = Exception("Execution failed")
            
            result = agent.query("测试查询")
            
            assert isinstance(result, SQLQueryResult)
            assert result.success is False
            assert "Execution failed" in result.error
    
    def test_system_prompt_generation(self, agent):
        """测试系统提示词生成"""
        prompt = agent.get_system_prompt()
        
        assert "Smart SQL Generation Agent" in prompt
        assert "extract_schema" in prompt
        assert "generate_sql" in prompt
        assert "ReAct" in prompt