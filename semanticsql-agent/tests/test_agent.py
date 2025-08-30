"""
Agent测试
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from agent.enhanced_smart_sql_agent import EnhancedSmartSQLAgent
from agent.execution_tracker import ExecutionTracker
from core.models import AgentStep, AgentStepType, QueryScenario
from core.exceptions import AgentExecutionError


class TestEnhancedSmartSQLAgent:
    """测试增强型SQL智能体"""
    
    @pytest.fixture
    def mock_config(self):
        """模拟配置"""
        config = Mock()
        config.llm.model = "test-model"
        config.llm.temperature = 0.1
        config.database.type = "mysql"
        return config
    
    @pytest.fixture
    def agent(self, mock_config):
        """创建测试用的agent"""
        with patch('agent.enhanced_smart_sql_agent.LLMClient'):
            agent = EnhancedSmartSQLAgent(mock_config)
            agent.llm_client = Mock()
            return agent
    
    def test_initialization(self, agent):
        """测试初始化"""
        assert agent.execution_tracker is not None
        assert agent.prompt_manager is not None
        assert len(agent.tools) > 0
        assert agent.max_iterations == 10
    
    def test_execute_success(self, agent):
        """测试成功执行"""
        # 模拟LLM响应
        agent.llm_client.complete.return_value = Mock(
            content="Action: analyze_schema\nAction Input: {}"
        )
        
        # 模拟工具执行
        mock_tool = Mock()
        mock_tool.execute.return_value = {"tables": ["users", "orders"]}
        agent.tools["analyze_schema"] = mock_tool
        
        # 执行
        with patch.object(agent, '_should_continue', side_effect=[True, False]):
            result = agent.execute("获取用户订单")
        
        assert result is not None
        assert mock_tool.execute.called
    
    def test_execute_with_error(self, agent):
        """测试错误处理"""
        # 模拟LLM错误
        agent.llm_client.complete.side_effect = Exception("LLM Error")
        
        with pytest.raises(AgentExecutionError):
            agent.execute("测试查询")
    
    def test_max_iterations(self, agent):
        """测试最大迭代限制"""
        agent.max_iterations = 2
        
        # 模拟持续执行
        agent.llm_client.complete.return_value = Mock(
            content="Thought: 继续思考"
        )
        
        with patch.object(agent, '_should_continue', return_value=True):
            result = agent.execute("测试查询")
        
        # 应该因为达到最大迭代而停止
        steps = agent.execution_tracker.get_execution_log()
        assert len(steps) <= agent.max_iterations * 3  # 每次迭代最多3个步骤
    
    def test_parse_llm_output(self, agent):
        """测试解析LLM输出"""
        # 测试思考
        output = "Thought: 需要查询数据库"
        step_type, content = agent._parse_llm_output(output)
        assert step_type == AgentStepType.THOUGHT
        assert content == "需要查询数据库"
        
        # 测试行动
        output = "Action: generate_sql\nAction Input: {\"question\": \"test\"}"
        step_type, content = agent._parse_llm_output(output)
        assert step_type == AgentStepType.ACTION
        assert "generate_sql" in content
        
        # 测试最终答案
        output = "Final Answer: SELECT * FROM users"
        step_type, content = agent._parse_llm_output(output)
        assert step_type == AgentStepType.OBSERVATION
        assert content == "SELECT * FROM users"


class TestExecutionTracker:
    """测试执行跟踪器"""
    
    @pytest.fixture
    def tracker(self):
        """创建测试用的tracker"""
        return ExecutionTracker()
    
    def test_record_thought(self, tracker):
        """测试记录思考"""
        tracker.record_thought("需要分析数据库结构")
        
        steps = tracker.get_execution_log()
        assert len(steps) == 1
        assert steps[0].step_type == AgentStepType.THOUGHT
        assert steps[0].content == "需要分析数据库结构"
    
    def test_record_action(self, tracker):
        """测试记录行动"""
        tracker.record_action(
            tool_name="analyze_schema",
            tool_input={"database": "test"},
            content="分析数据库结构"
        )
        
        steps = tracker.get_execution_log()
        assert len(steps) == 1
        assert steps[0].step_type == AgentStepType.ACTION
        assert steps[0].tool_name == "analyze_schema"
    
    def test_record_observation(self, tracker):
        """测试记录观察"""
        tracker.record_observation(
            tool_output={"result": "success"},
            content="执行成功"
        )
        
        steps = tracker.get_execution_log()
        assert len(steps) == 1
        assert steps[0].step_type == AgentStepType.OBSERVATION
    
    def test_execution_summary(self, tracker):
        """测试执行摘要"""
        # 记录完整执行流程
        tracker.record_thought("思考1")
        tracker.record_action("tool1", {})
        tracker.record_observation({"result": "ok"})
        tracker.record_thought("思考2")
        
        summary = tracker.get_execution_summary()
        assert summary["total_steps"] == 4
        assert summary["thought_count"] == 2
        assert summary["action_count"] == 1
        assert summary["observation_count"] == 1
    
    def test_clear(self, tracker):
        """测试清除记录"""
        tracker.record_thought("测试")
        assert len(tracker.get_execution_log()) == 1
        
        tracker.clear()
        assert len(tracker.get_execution_log()) == 0
    
    def test_to_dict(self, tracker):
        """测试转换为字典"""
        tracker.record_thought("测试思考")
        tracker.record_action("test_tool", {"param": "value"})
        
        data = tracker.to_dict()
        assert "steps" in data
        assert "metadata" in data
        assert len(data["steps"]) == 2