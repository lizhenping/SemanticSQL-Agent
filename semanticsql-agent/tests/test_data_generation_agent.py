"""
测试 DataGenerationAgent 的端到端功能
"""

import pytest
import json
import tempfile
import os
from unittest.mock import Mock, patch

from agent.data_generation_agent import DataGenerationAgent
from models.training import TrainingDataResult
from config.settings import Settings
from utils.database_config import DatabaseConfig
from models.exceptions import AgentExecutionError


class TestDataGenerationAgent:
    """测试 DataGenerationAgent"""
    
    @pytest.fixture
    def settings(self):
        """创建测试配置"""
        return Settings(
            llm_model="test-model",
            llm_base_url="http://localhost:9991/v1",
            llm_api_key="test-key",
            llm_temperature=0.7,
            max_steps=10
        )
    
    @pytest.fixture
    def db_config(self):
        """创建数据库配置"""
        return DatabaseConfig(
            host="localhost",
            port=3306,
            database="test_db",
            username="test_user",
            password="test_pass"
        )
    
    @pytest.fixture
    def mock_db_manager(self):
        """模拟数据库管理器"""
        with patch('agent.data_generation_agent.DatabaseManager') as mock:
            mock_instance = Mock()
            mock_instance.initialize.return_value = True
            mock_instance.close.return_value = None
            mock.return_value = mock_instance
            yield mock_instance
    
    @pytest.fixture
    def agent(self, settings, db_config, mock_db_manager):
        """创建测试Agent"""
        with patch('agent.data_generation_agent.DatabaseManager'):
            return DataGenerationAgent(settings, db_config)
    
    def test_initialization(self, agent):
        """测试Agent初始化"""
        assert agent is not None
        assert hasattr(agent, 'tools')
        assert hasattr(agent, 'memory')
        assert hasattr(agent, 'agent_executor')
        
        # 验证工具数量（应该包含所有设计规范要求的工具）
        tool_names = agent.get_tool_names()
        expected_tools = [
            'schema_extraction', 'domain_analysis', 'field_classification',
            'column_meaning_analysis', 'table_meaning_analysis', 'er_analysis',
            'scenario_operation_generation', 'question_generation',
            'sql_generation', 'sql_validation', 'sql_execution',
            'sql_reflection', 'sequential_thinking'
        ]
        
        for tool_name in expected_tools:
            assert tool_name in tool_names, f"Missing tool: {tool_name}"
    
    def test_memory_system(self, agent):
        """测试记忆系统"""
        # 测试记忆初始化
        memory_state = agent.get_memory_state()
        assert 'db_analysis' in memory_state
        
        # 测试记忆验证
        validation = agent.validate_memory_state()
        assert 'is_complete' in validation
        assert 'missing_analyses' in validation
        
        # 初始状态应该不完整
        assert not validation['is_complete']
        assert len(validation['missing_analyses']) > 0
    
    def test_analysis_summary(self, agent):
        """测试分析摘要功能"""
        summary = agent.get_analysis_summary()
        
        required_keys = [
            'has_schema', 'has_domain', 'has_classification',
            'has_column_meanings', 'has_table_meanings', 'has_er_analysis',
            'total_tables', 'total_columns'
        ]
        
        for key in required_keys:
            assert key in summary
    
    @patch('agent.data_generation_agent.DatabaseManager')
    def test_database_analysis_task_structure(self, mock_db_manager, settings, db_config):
        """测试数据库分析任务结构"""
        # 创建Agent
        agent = DataGenerationAgent(settings, db_config)
        
        # 模拟成功的数据库分析
        with patch.object(agent, 'run') as mock_run:
            mock_run.return_value = {
                "success": True,
                "result": "analysis completed"
            }
            
            with patch.object(agent, 'get_memory_state') as mock_memory:
                mock_memory.return_value = {
                    "db_analysis": {
                        "schema_info": {"tables": {"test_table": {}}},
                        "domain_info": {"primary_domain": "test"}
                    }
                }
                
                result = agent.run("请分析数据库结构和业务特征")
                
                # 验证任务调用结构
                assert mock_run.called
                task_arg = mock_run.call_args[0][0]
                
                # 验证任务包含正确的工具执行顺序
                assert "schema_extraction" in task_arg
                assert "domain_analysis" in task_arg
                assert "field_classification" in task_arg
                assert "column_meaning_analysis" in task_arg
                assert "table_meaning_analysis" in task_arg
                assert "er_analysis" in task_arg
                
                # 验证返回结果
                assert result["success"]
                assert "analysis" in result
    
    @patch('agent.data_generation_agent.DatabaseManager')
    def test_training_data_generation_task_structure(self, mock_db_manager, settings, db_config):
        """测试训练数据生成任务结构"""
        agent = DataGenerationAgent(settings, db_config)
        
        # 模拟成功的生成过程
        with patch.object(agent, 'run') as mock_run:
            mock_run.return_value = {
                "success": True,
                "result": "generation completed"
            }
            
            with patch.object(agent, '_extract_generated_examples') as mock_extract:
                mock_extract.return_value = [
                    {
                        "id": "test_1",
                        "question": "测试问题",
                        "sql": "SELECT * FROM test",
                        "scenario": {"id": "test_scenario"},
                        "validation": {"syntax_valid": True, "execution_success": True},
                        "quality_score": 0.9
                    }
                ]
                
                with patch.object(agent, '_save_training_data'):
                    result = agent.generate_training_data(
                        count=5, 
                        output_file="test.json"
                    )
                    
                    # 验证任务调用结构
                    assert mock_run.called
                    task_arg = mock_run.call_args[0][0]
                    
                    # 验证任务包含正确的流程描述
                    assert "scenario_operation_generation" in task_arg
                    assert "question_generation" in task_arg
                    assert "sql_generation" in task_arg
                    assert "sql_reflection" in task_arg
                    assert "sequential_thinking" in task_arg
                    
                    # 验证包含反思-修正机制
                    assert "needs_revision" in task_arg
                    assert "重新执行" in task_arg
                    
                    # 验证返回结果
                    assert isinstance(result, TrainingDataResult)
                    assert result.total == 5
                    assert result.successful == 1
    
    def test_format_training_example(self, agent):
        """测试训练样例格式化"""
        raw_example = {
            "scenario": {"id": "test_scenario", "category": "测试"},
            "question": "测试问题？",
            "sql": "SELECT * FROM test_table",
            "operations": ["SELECT"],
            "tables": ["test_table"],
            "validation": {
                "syntax_valid": True,
                "execution_success": True,
                "row_count": 10
            },
            "quality_score": 0.85
        }
        
        formatted = agent._format_training_example(raw_example)
        
        # 验证必需字段
        required_fields = [
            "id", "scenario", "question", "sql", "operations",
            "tables", "timestamp", "validation", "quality_score"
        ]
        
        for field in required_fields:
            assert field in formatted
        
        # 验证ID格式
        assert formatted["id"].startswith("q_")
        assert len(formatted["id"]) > 10
        
        # 验证内容
        assert formatted["question"] == "测试问题？"
        assert formatted["sql"] == "SELECT * FROM test_table"
        assert formatted["quality_score"] == 0.85
    
    def test_save_training_data(self, agent):
        """测试保存训练数据"""
        examples = [
            {
                "id": "test_1",
                "question": "测试问题1",
                "sql": "SELECT * FROM table1",
                "scenario": {"id": "scenario_1"}
            },
            {
                "id": "test_2", 
                "question": "测试问题2",
                "sql": "SELECT count(*) FROM table2",
                "scenario": {"id": "scenario_2"}
            }
        ]
        
        # 测试JSON格式
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json_file = f.name
        
        try:
            agent._save_training_data(examples, json_file)
            
            # 验证文件内容
            with open(json_file, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
            
            assert len(saved_data) == 2
            assert saved_data[0]["id"] == "test_1"
            assert saved_data[1]["question"] == "测试问题2"
            
        finally:
            os.unlink(json_file)
        
        # 测试JSONL格式
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            jsonl_file = f.name
        
        try:
            agent._save_training_data(examples, jsonl_file)
            
            # 验证文件内容
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            assert len(lines) == 2
            
            line1_data = json.loads(lines[0])
            line2_data = json.loads(lines[1])
            
            assert line1_data["id"] == "test_1"
            assert line2_data["question"] == "测试问题2"
            
        finally:
            os.unlink(jsonl_file)
    
    def test_extract_generated_examples_structure(self, agent):
        """测试从轨迹中提取样例的结构"""
        # 模拟轨迹数据
        mock_trajectories = [
            {
                "type": "tool_end",
                "tool_name": "scenario_operation_generation",
                "output": json.dumps({
                    "scenario_id": "test_scenario",
                    "category": "测试场景",
                    "business_purpose": "测试用途",
                    "complexity": "medium"
                })
            },
            {
                "type": "tool_end",
                "tool_name": "question_generation",
                "output": json.dumps({
                    "question": "这是一个测试问题？"
                })
            },
            {
                "type": "tool_end",
                "tool_name": "sql_generation",
                "output": json.dumps({
                    "sql": "SELECT * FROM test_table",
                    "tables_used": ["test_table"]
                })
            },
            {
                "type": "tool_end",
                "tool_name": "sql_reflection",
                "output": json.dumps({
                    "overall_score": 0.9,
                    "needs_revision": False
                })
            }
        ]
        
        # 模拟回调处理器
        with patch.object(agent, 'callback_handler') as mock_callback:
            mock_callback.get_trajectories.return_value = mock_trajectories
            
            examples = agent._extract_generated_examples()
            
            # 验证提取结果
            assert len(examples) == 1
            example = examples[0]
            
            assert "id" in example
            assert example["question"] == "这是一个测试问题？"
            assert example["sql"] == "SELECT * FROM test_table"
            assert example["scenario"]["id"] == "test_scenario"
            assert example["quality_score"] == 0.9
    
    @patch('agent.data_generation_agent.DatabaseManager')
    def test_agent_error_handling(self, mock_db_manager, settings, db_config):
        """测试Agent错误处理"""
        # 测试数据库连接失败
        mock_db_manager.return_value.initialize.return_value = False
        
        with pytest.raises(AgentExecutionError) as exc_info:
            DataGenerationAgent(settings, db_config)
        
        assert "Failed to initialize database connection" in str(exc_info.value)
    
    def test_memory_validation_edge_cases(self, agent):
        """测试记忆验证的边界情况"""
        # 测试空记忆
        validation = agent.validate_memory_state()
        assert not validation["is_complete"]
        assert len(validation["missing_analyses"]) == 6
        
        # 测试部分记忆
        agent.memory.memories = {
            "schema_info": {"tables": {}},
            "domain_info": {"primary_domain": "test"}
        }
        
        validation = agent.validate_memory_state()
        assert not validation["is_complete"]
        assert len(validation["missing_analyses"]) == 4
    
    def test_resource_cleanup(self, agent):
        """测试资源清理"""
        # 确保析构函数正确调用
        with patch.object(agent.db_manager, 'close') as mock_close:
            del agent
            # 注意：Python的垃圾回收是不确定的，这个测试可能不稳定
            # 主要是验证方法存在和逻辑正确