"""
数据模型测试
"""

import pytest
from datetime import datetime
from typing import Dict, Any

from models.schemas import (
    SQLQueryResult, AgentExecution, AgentStep, AgentStepType,
    DatabaseSchema, TableInfo, ColumnInfo
)


class TestSQLQueryResult:
    """测试SQL查询结果模型"""
    
    def test_success_result(self):
        """测试成功结果"""
        result = SQLQueryResult(
            success=True,
            question="查询用户数量",
            sql="SELECT COUNT(*) FROM users",
            answer="共有100个用户",
            data=[{"count": 100}],
            row_count=1,
            execution_time=0.5
        )
        
        assert result.success is True
        assert result.question == "查询用户数量"
        assert result.sql == "SELECT COUNT(*) FROM users"
        assert result.row_count == 1
        assert result.execution_time == 0.5
    
    def test_error_result(self):
        """测试错误结果"""
        result = SQLQueryResult(
            success=False,
            question="无效查询",
            error="SQL语法错误"
        )
        
        assert result.success is False
        assert result.error == "SQL语法错误"
        assert result.sql == ""
        assert result.data == []
    
    def test_to_dict(self):
        """测试转换为字典"""
        result = SQLQueryResult(
            success=True,
            question="测试",
            sql="SELECT 1",
            data=[{"result": 1}]
        )
        
        data = result.to_dict()
        assert data["success"] is True
        assert data["question"] == "测试"
        assert data["sql"] == "SELECT 1"


class TestAgentExecution:
    """测试代理执行模型"""
    
    def test_initialization(self):
        """测试初始化"""
        execution = AgentExecution(task="测试任务")
        
        assert execution.task == "测试任务"
        assert execution.status == "running"
        assert execution.steps == []
        assert execution.start_time is not None
    
    def test_add_step(self):
        """测试添加步骤"""
        execution = AgentExecution(task="测试")
        
        step = AgentStep(
            step_type=AgentStepType.THOUGHT,
            content="思考内容"
        )
        
        execution.add_step(step)
        
        assert len(execution.steps) == 1
        assert execution.steps[0].content == "思考内容"
    
    def test_complete_success(self):
        """测试成功完成"""
        execution = AgentExecution(task="测试")
        result = {"result": "success"}
        
        execution.complete(result)
        
        assert execution.status == "completed"
        assert execution.final_result == result
        assert execution.end_time is not None
    
    def test_complete_error(self):
        """测试错误完成"""
        execution = AgentExecution(task="测试")
        
        execution.complete(error="执行失败")
        
        assert execution.status == "failed"
        assert execution.error == "执行失败"
        assert execution.end_time is not None
    
    def test_get_duration(self):
        """测试获取执行时长"""
        execution = AgentExecution(task="测试")
        execution.complete({"result": "ok"})
        
        duration = execution.get_duration()
        assert duration >= 0
        assert isinstance(duration, float)


class TestAgentStep:
    """测试代理步骤模型"""
    
    def test_thought_step(self):
        """测试思考步骤"""
        step = AgentStep(
            step_type=AgentStepType.THOUGHT,
            content="需要分析数据库结构"
        )
        
        assert step.step_type == AgentStepType.THOUGHT
        assert step.content == "需要分析数据库结构"
        assert step.timestamp is not None
    
    def test_action_step(self):
        """测试行动步骤"""
        step = AgentStep(
            step_type=AgentStepType.ACTION,
            content="执行工具",
            tool_name="extract_schema",
            tool_input={"database": "testdb"}
        )
        
        assert step.step_type == AgentStepType.ACTION
        assert step.tool_name == "extract_schema"
        assert step.tool_input == {"database": "testdb"}
    
    def test_observation_step(self):
        """测试观察步骤"""
        step = AgentStep(
            step_type=AgentStepType.OBSERVATION,
            content="工具执行完成",
            tool_output={"tables": ["users", "orders"]}
        )
        
        assert step.step_type == AgentStepType.OBSERVATION
        assert step.tool_output == {"tables": ["users", "orders"]}


class TestDatabaseSchema:
    """测试数据库结构模型"""
    
    def test_initialization(self):
        """测试初始化"""
        schema = DatabaseSchema(database_name="testdb")
        
        assert schema.database_name == "testdb"
        assert schema.tables == {}
    
    def test_add_table(self):
        """测试添加表"""
        schema = DatabaseSchema(database_name="testdb")
        
        table_info = TableInfo(name="users")
        schema.tables["users"] = table_info
        
        assert "users" in schema.tables
        assert schema.tables["users"].name == "users"


class TestTableInfo:
    """测试表信息模型"""
    
    def test_initialization(self):
        """测试初始化"""
        table = TableInfo(name="users")
        
        assert table.name == "users"
        assert table.columns == []
        assert table.row_count is None
    
    def test_add_column(self):
        """测试添加列"""
        table = TableInfo(name="users")
        
        column = ColumnInfo(
            name="id",
            data_type="int",
            is_primary=True
        )
        
        table.columns.append(column)
        
        assert len(table.columns) == 1
        assert table.columns[0].name == "id"
        assert table.columns[0].is_primary is True


class TestColumnInfo:
    """测试列信息模型"""
    
    def test_primary_key_column(self):
        """测试主键列"""
        column = ColumnInfo(
            name="id",
            data_type="int",
            nullable=False,
            is_primary=True
        )
        
        assert column.name == "id"
        assert column.data_type == "int"
        assert column.nullable is False
        assert column.is_primary is True
    
    def test_regular_column(self):
        """测试普通列"""
        column = ColumnInfo(
            name="name",
            data_type="varchar(255)",
            nullable=True,
            default="''"
        )
        
        assert column.name == "name"
        assert column.data_type == "varchar(255)"
        assert column.nullable is True
        assert column.default == "''"
        assert column.is_primary is False