"""
工具系统测试
"""

import pytest
import asyncio

from ..tools.trae_base_tool import TraeBaseTool, ToolParameter
from ..tools.sql_tools import SchemaExtractionTool, SQLGenerationTool, SQLValidationTool
from ..config.database_models import DatabaseConfig


class MockSQLTool(TraeBaseTool):
    """Mock SQL工具用于测试"""
    
    def __init__(self):
        super().__init__("mock_sql", "Mock SQL tool for testing")
    
    @property
    def parameters(self):
        return [
            ToolParameter("query", "string", "SQL查询", required=True),
            ToolParameter("limit", "integer", "限制行数", required=False, default=100)
        ]
    
    async def execute(self, query: str, limit: int = 100):
        return {"success": True, "query": query, "limit": limit}


class TestTools:
    """工具系统测试"""
    
    def test_tool_parameter_creation(self):
        """测试工具参数创建"""
        param = ToolParameter("test", "string", "test param")
        assert param.name == "test"
        assert param.type == "string"
        assert param.description == "test param"
        assert param.required is True
    
    def test_tool_schema_generation(self):
        """测试工具schema生成"""
        tool = MockSQLTool()
        schema = tool.get_schema()
        
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "mock_sql"
        assert "query" in schema["function"]["parameters"]["properties"]
    
    def test_tool_parameter_validation(self):
        """测试参数验证"""
        tool = MockSQLTool()
        
        # 有效参数
        valid, error = tool.validate_parameters({"query": "SELECT * FROM users"})
        assert valid is True
        assert error is None
        
        # 无效参数
        valid, error = tool.validate_parameters({})
        assert valid is False
        assert "缺少必需参数: query" in error
    
    @pytest.mark.asyncio
    async def test_mock_tool_execution(self):
        """测试工具执行"""
        tool = MockSQLTool()
        result = await tool.execute("SELECT * FROM users", limit=50)
        
        assert result["success"] is True
        assert result["query"] == "SELECT * FROM users"
        assert result["limit"] == 50
    
    def test_sql_generation_tool_creation(self):
        """测试SQL生成工具创建"""
        config = DatabaseConfig(
            type="mysql",
            host="localhost",
            port=3306,
            database="testdb",
            username="user",
            password="pass"
        )
        
        tool = SQLGenerationTool(config)
        assert tool.name == "generate_sql"
        assert "query" in [p.name for p in tool.parameters]
    
    def test_sql_validation_tool_creation(self):
        """测试SQL验证工具创建"""
        config = DatabaseConfig(
            type="mysql",
            host="localhost",
            port=3306,
            database="testdb",
            username="user",
            password="pass"
        )
        
        tool = SQLValidationTool(config)
        assert tool.name == "validate_sql"
        assert "sql" in [p.name for p in tool.parameters]