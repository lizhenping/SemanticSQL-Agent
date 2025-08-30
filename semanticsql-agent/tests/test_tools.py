"""
工具测试
"""

import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any

from tools.base_tool import BaseTool, ToolParameter
from tools.generation.scenario_tool import ScenarioTool
from tools.generation.sql_generation_tool import SQLGenerationTool
from tools.validation.sql_validation_tool import SQLValidationTool
from tools.validation.sql_execution_tool import SQLExecutionTool
from tools.reflection.sql_reflection_tool import SQLReflectionTool


class TestBaseTool:
    """测试基础工具类"""
    
    def test_tool_parameter(self):
        """测试工具参数"""
        param = ToolParameter(
            name="test_param",
            type="string",
            description="测试参数",
            required=True
        )
        
        assert param.name == "test_param"
        assert param.type == "string"
        assert param.required is True
        assert param.default is None
    
    def test_base_tool_abstract(self):
        """测试基础工具抽象类"""
        with pytest.raises(TypeError):
            BaseTool()


class TestScenarioTool:
    """测试场景生成工具"""
    
    @pytest.fixture
    def tool(self):
        """创建测试工具"""
        return ScenarioTool()
    
    def test_initialization(self, tool):
        """测试初始化"""
        assert tool.name == "generate_scenario"
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
        
        result = tool.execute(schema_info=schema_info)
        
        assert "scenario" in result
        assert result["scenario"] in tool.business_scenarios
        assert "confidence" in result
    
    def test_execute_empty_schema(self, tool):
        """测试空schema"""
        result = tool.execute(schema_info={"tables": {}})
        
        assert result["scenario"] == "general"
        assert result["confidence"] < 0.5


class TestSQLGenerationTool:
    """测试SQL生成工具"""
    
    @pytest.fixture
    def tool(self):
        """创建测试工具"""
        with patch('tools.generation.sql_generation_tool.LLMClient'):
            tool = SQLGenerationTool(Mock())
            tool.llm_client = Mock()
            return tool
    
    def test_initialization(self, tool):
        """测试初始化"""
        assert tool.name == "generate_sql"
        assert tool.llm_client is not None
    
    def test_execute_success(self, tool):
        """测试成功生成SQL"""
        # 模拟LLM响应
        tool.llm_client.complete.return_value = Mock(
            content="SELECT COUNT(*) FROM users;"
        )
        
        result = tool.execute(
            question="统计用户数量",
            schema_info={"tables": {"users": {}}},
            scenario="reporting"
        )
        
        assert "sql" in result
        assert "SELECT" in result["sql"]
        assert result["confidence"] > 0
    
    def test_execute_with_hints(self, tool):
        """测试带提示的SQL生成"""
        tool.llm_client.complete.return_value = Mock(
            content="SELECT * FROM users WHERE status = 'active';"
        )
        
        result = tool.execute(
            question="查询活跃用户",
            schema_info={"tables": {"users": {}}},
            hints=["注意用户状态字段"]
        )
        
        assert "WHERE" in result["sql"]


class TestSQLValidationTool:
    """测试SQL验证工具"""
    
    @pytest.fixture
    def tool(self):
        """创建测试工具"""
        return SQLValidationTool()
    
    def test_syntax_validation(self, tool):
        """测试语法验证"""
        # 有效SQL
        result = tool.execute(
            sql="SELECT * FROM users",
            schema_info={"tables": {"users": {}}}
        )
        assert result["is_valid"] is True
        
        # 无效SQL
        result = tool.execute(
            sql="SELEC * FORM users",
            schema_info={"tables": {"users": {}}}
        )
        assert result["is_valid"] is False
        assert len(result["errors"]) > 0
    
    def test_table_validation(self, tool):
        """测试表验证"""
        result = tool.execute(
            sql="SELECT * FROM non_existent_table",
            schema_info={"tables": {"users": {}}}
        )
        
        assert result["is_valid"] is False
        assert any("non_existent_table" in err for err in result["errors"])
    
    def test_dangerous_operation_check(self, tool):
        """测试危险操作检查"""
        result = tool.execute(
            sql="DROP TABLE users",
            schema_info={"tables": {"users": {}}}
        )
        
        assert len(result["warnings"]) > 0
        assert any("DROP" in warn for warn in result["warnings"])


class TestSQLExecutionTool:
    """测试SQL执行工具"""
    
    @pytest.fixture
    def tool(self):
        """创建测试工具"""
        mock_db = Mock()
        return SQLExecutionTool(mock_db)
    
    def test_dry_run(self, tool):
        """测试干运行模式"""
        result = tool.execute(
            sql="SELECT * FROM users",
            dry_run=True
        )
        
        assert result["executed"] is False
        assert result["dry_run"] is True
        assert tool.database.execute_query.called is False
    
    def test_execute_success(self, tool):
        """测试成功执行"""
        # 模拟数据库返回
        tool.database.execute_query.return_value = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"}
        ]
        
        result = tool.execute(
            sql="SELECT * FROM users",
            dry_run=False
        )
        
        assert result["executed"] is True
        assert result["row_count"] == 2
        assert len(result["results"]) == 2
    
    def test_execute_with_limit(self, tool):
        """测试带限制的执行"""
        tool.database.execute_query.return_value = [{"id": i} for i in range(100)]
        
        result = tool.execute(
            sql="SELECT * FROM users",
            limit=10
        )
        
        assert len(result["results"]) == 10
    
    def test_execute_error(self, tool):
        """测试执行错误"""
        tool.database.execute_query.side_effect = Exception("Database error")
        
        result = tool.execute(sql="INVALID SQL")
        
        assert result["executed"] is False
        assert result["error"] == "Database error"


class TestSQLReflectionTool:
    """测试SQL反思工具"""
    
    @pytest.fixture
    def tool(self):
        """创建测试工具"""
        with patch('tools.reflection.sql_reflection_tool.LLMClient'):
            tool = SQLReflectionTool(Mock())
            tool.llm_client = Mock()
            return tool
    
    def test_quality_assessment(self, tool):
        """测试质量评估"""
        tool.llm_client.complete.return_value = Mock(
            content="SQL查询正确，性能良好"
        )
        
        result = tool.execute(
            question="查询用户数量",
            sql="SELECT COUNT(*) FROM users",
            execution_result={"row_count": 1, "results": [{"count": 100}]}
        )
        
        assert "quality_score" in result
        assert result["quality_score"] > 0
        assert "assessment" in result
    
    def test_optimization_suggestions(self, tool):
        """测试优化建议"""
        tool.llm_client.complete.return_value = Mock(
            content="建议添加索引以提高性能"
        )
        
        result = tool.execute(
            question="查询大量数据",
            sql="SELECT * FROM large_table",
            execution_result={"execution_time": 5.0}
        )
        
        assert "suggestions" in result
        assert len(result["suggestions"]) > 0
    
    def test_error_reflection(self, tool):
        """测试错误反思"""
        result = tool.execute(
            question="查询数据",
            sql="INVALID SQL",
            execution_result={"error": "Syntax error"}
        )
        
        assert result["quality_score"] == 0
        assert "needs_regeneration" in result
        assert result["needs_regeneration"] is True