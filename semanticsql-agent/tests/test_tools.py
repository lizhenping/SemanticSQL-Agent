"""
工具测试
"""

import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any

from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from tools.generation_tools.scenario_operation_tool import ScenarioOperationTool
from tools.generation_tools.sql_generation_tool import SQLGenerationTool
from tools.validation_tools.sql_validation_tool import SQLValidationTool
from tools.validation_tools.sql_execution_tool import SQLExecutionTool
from tools.reflection_tools.sql_reflection_tool import SQLReflectionTool
from config.settings import Settings
from utils.database import DatabaseManager
from utils.database_config import DatabaseConfig, DatabaseType


class TestBaseTool:
    """测试基础工具类"""
    
    def test_base_tool_abstract(self):
        """测试基础工具抽象类"""
        with pytest.raises(TypeError):
            BaseTool()


class TestScenarioOperationTool:
    """测试场景-操作生成工具"""
    
    @pytest.fixture
    def tool(self):
        """创建测试工具"""
        return ScenarioOperationTool()
    
    def test_initialization(self, tool):
        """测试初始化"""
        assert tool.name == "scenario_operation_generation"
        assert tool.description is not None
        assert len(tool.parameters) > 0
    
    def test_execute_success(self, tool):
        """测试成功执行"""
        schema_info = {
            "tables": {
                "users": {
                    "columns": [
                        {"name": "id", "type": "int"},
                        {"name": "name", "type": "varchar"}
                    ]
                },
                "orders": {
                    "columns": [
                        {"name": "id", "type": "int"},
                        {"name": "user_id", "type": "int"}
                    ]
                }
            }
        }
        
        result = tool.run(schema_info=schema_info, count=5)
        
        assert result["success"] is True
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 5


class TestSQLGenerationTool:
    """测试SQL生成工具"""
    
    @pytest.fixture
    def tool(self):
        """创建测试工具"""
        settings = Settings()
        with patch('openai.OpenAI'):
            tool = SQLGenerationTool(settings)
            tool.llm_client = Mock()
            return tool
    
    def test_initialization(self, tool):
        """测试初始化"""
        assert tool.name == "generate_sql"
        assert tool.llm_client is not None
    
    def test_execute_success(self, tool):
        """测试成功生成SQL"""
        # 模拟LLM响应
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "SELECT COUNT(*) FROM users;"
        tool.llm_client.chat.completions.create.return_value = mock_response
        
        result = tool.run(
            question="统计用户数量",
            schema_info={"tables": {"users": {"columns": [{"name": "id", "type": "int"}]}}},
            use_llm=True
        )
        
        assert result["success"] is True
        assert "sql" in result["data"]
        assert "SELECT" in result["data"]["sql"]
    
    def test_rule_based_generation(self, tool):
        """测试基于规则的SQL生成"""
        result = tool.run(
            question="查询所有用户",
            schema_info={"tables": {"users": {"columns": [{"name": "id", "type": "int"}]}}},
            use_llm=False
        )
        
        assert result["success"] is True
        assert "sql" in result["data"]


class TestSQLValidationTool:
    """测试SQL验证工具"""
    
    @pytest.fixture
    def tool(self):
        """创建测试工具"""
        settings = Settings()
        return SQLValidationTool(settings)
    
    def test_syntax_validation(self, tool):
        """测试语法验证"""
        # 有效SQL
        result = tool.run(
            sql="SELECT * FROM users",
            schema_info={"tables": {"users": {}}}
        )
        assert result["success"] is True
        assert result["data"]["valid"] is True
        
        # 无效SQL  
        result = tool.run(
            sql="SELEC * FORM users",
            schema_info={"tables": {"users": {}}}
        )
        assert result["success"] is True
        assert result["data"]["valid"] is False
        assert len(result["data"]["errors"]) > 0
    
    def test_table_validation(self, tool):
        """测试表验证"""
        result = tool.run(
            sql="SELECT * FROM non_existent_table",
            schema_info={"tables": {"users": {}}}
        )
        
        assert result["data"]["valid"] is False
        assert any("non_existent_table" in err for err in result["data"]["errors"])
    
    def test_dangerous_operation_check(self, tool):
        """测试危险操作检查"""
        result = tool.run(
            sql="DROP TABLE users",
            schema_info={"tables": {"users": {}}}
        )
        
        assert len(result["data"]["warnings"]) > 0


class TestSQLExecutionTool:
    """测试SQL执行工具"""
    
    @pytest.fixture
    def tool(self):
        """创建测试工具"""
        mock_db_manager = Mock()
        return SQLExecutionTool(mock_db_manager)
    
    def test_dry_run(self, tool):
        """测试干运行模式"""
        result = tool.run(
            sql="SELECT * FROM users",
            dry_run=True
        )
        
        assert result["success"] is True
        assert result["data"]["dry_run"] is True
        assert not tool.db_manager._execute_query.called
    
    def test_execute_success(self, tool):
        """测试成功执行"""
        # 模拟数据库返回
        tool.db_manager._execute_query.return_value = {
            "success": True,
            "data": [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"}
            ]
        }
        
        result = tool.run(
            sql="SELECT * FROM users",
            dry_run=False
        )
        
        assert result["success"] is True
        assert len(result["data"]["data"]) == 2
    
    def test_execute_error(self, tool):
        """测试执行错误"""
        tool.db_manager._execute_query.return_value = {
            "success": False,
            "error": "Database error"
        }
        
        result = tool.run(sql="INVALID SQL")
        
        assert result["success"] is True  # Tool executed successfully
        assert result["data"]["success"] is False  # But query failed


class TestSQLReflectionTool:
    """测试SQL反思工具"""
    
    @pytest.fixture
    def tool(self):
        """创建测试工具"""
        settings = Settings()
        with patch('openai.OpenAI'):
            tool = SQLReflectionTool(settings)
            tool.llm_client = Mock()
            return tool
    
    def test_quality_assessment(self, tool):
        """测试质量评估"""
        result = tool.run(
            question="查询用户数量",
            sql="SELECT COUNT(*) FROM users",
            execution_result={"success": True, "data": [{"count": 100}]}
        )
        
        assert result["success"] is True
        assert "quality_score" in result["data"]
        assert result["data"]["quality_score"] > 0
    
    def test_optimization_suggestions(self, tool):
        """测试优化建议"""
        result = tool.run(
            question="查询大量数据",
            sql="SELECT * FROM large_table",
            execution_result={"success": True, "execution_time": 5.0}
        )
        
        assert result["success"] is True
        assert "suggestions" in result["data"]
        assert len(result["data"]["suggestions"]) > 0
    
    def test_error_reflection(self, tool):
        """测试错误反思"""
        result = tool.run(
            question="查询数据",
            sql="INVALID SQL",
            execution_result={"success": False, "error": "Syntax error"}
        )
        
        assert result["success"] is True
        assert result["data"]["quality_score"] < 50