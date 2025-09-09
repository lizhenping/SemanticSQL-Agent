#!/usr/bin/env python3
"""
简化测试脚本 - 直接测试新架构核心组件
避免旧系统依赖问题
"""

import sys
import logging
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_new_architecture_components():
    """测试新架构的核心组件"""
    logger.info("🧪 测试新架构核心组件")
    
    results = {}
    
    # 1. 测试Agent状态系统
    try:
        from agent.state import create_agent_state, validate_agent_state, extract_database_info
        
        state = create_agent_state(
            user_input="查询用户信息", 
            database_params={"host": "localhost", "database": "test"}
        )
        
        assert validate_agent_state(state)
        db_info = extract_database_info(state)
        assert "database" in db_info
        
        results["agent_state"] = True
        logger.info("✅ Agent状态系统正常")
        
    except Exception as e:
        results["agent_state"] = False
        logger.error(f"❌ Agent状态系统失败: {e}")
    
    # 2. 测试ReAct解析器
    try:
        from agent.parsers import SemanticSQLOutputParser, validate_llm_output
        
        parser = SemanticSQLOutputParser()
        
        # 测试Final Answer解析
        test_output = "Final Answer: SELECT * FROM users"
        result = parser.parse(test_output)
        assert result.return_values["output"] == "SELECT * FROM users"
        
        # 测试输出验证
        assert validate_llm_output("Final Answer: test")
        
        results["react_parser"] = True
        logger.info("✅ ReAct解析器正常")
        
    except Exception as e:
        results["react_parser"] = False
        logger.error(f"❌ ReAct解析器失败: {e}")
    
    # 3. 测试记忆系统
    try:
        from utils.memory import Neo4jMemoryManager
        from models.schemas import create_triple
        
        memory = Neo4jMemoryManager()
        
        # 创建测试三元组
        triple = create_triple("test_subject", "test_predicate", "test_object", "test_tool")
        assert triple.subject == "test_subject"
        
        results["memory_system"] = True
        logger.info("✅ 记忆系统正常")
        
    except Exception as e:
        results["memory_system"] = False
        logger.error(f"❌ 记忆系统失败: {e}")
    
    # 4. 测试工具基类
    try:
        from tools.base_tool import BaseSemanticSQLTool
        
        # 验证基类有必需方法
        assert hasattr(BaseSemanticSQLTool, 'get_memory_by_source_tool')
        assert hasattr(BaseSemanticSQLTool, 'add_analysis_triple')
        
        results["base_tool"] = True
        logger.info("✅ 工具基类正常")
        
    except Exception as e:
        results["base_tool"] = False
        logger.error(f"❌ 工具基类失败: {e}")
    
    # 5. 测试分析工具创建
    try:
        from tools.analysis_tools.schema_extraction_tool import create_schema_extraction_tool
        from tools.analysis_tools.domain_analysis_tool import create_domain_analysis_tool
        
        memory = Neo4jMemoryManager()
        schema_tool = create_schema_extraction_tool(memory_manager=memory)
        domain_tool = create_domain_analysis_tool(memory_manager=memory)
        
        assert schema_tool.name == "schema_extraction"
        assert domain_tool.name == "domain_analysis"
        
        results["analysis_tools"] = True
        logger.info("✅ 分析工具创建正常")
        
    except Exception as e:
        results["analysis_tools"] = False
        logger.error(f"❌ 分析工具创建失败: {e}")
    
    # 6. 测试提示词管理器
    try:
        from prompts.manager import PromptManager
        
        pm = PromptManager()
        template = pm.create_agent_prompt_template("semantic_sql_agent")
        
        assert "input" in template.input_variables
        assert "agent_scratchpad" in template.input_variables
        
        results["prompt_manager"] = True
        logger.info("✅ 提示词管理器正常")
        
    except Exception as e:
        results["prompt_manager"] = False
        logger.error(f"❌ 提示词管理器失败: {e}")
    
    return results


def test_new_agent_direct():
    """直接测试新Agent类"""
    logger.info("🧪 测试新SemanticSQL Agent")
    
    try:
        # 直接从sql_agent模块导入新Agent
        from agent.sql_agent import SemanticSQLReActAgent, create_llm
        from utils.memory import Neo4jMemoryManager
        
        # 创建LLM（测试模式）
        test_llm = create_llm(
            config_type="openai",
            model="gpt-4",
            api_key="test-key",
            base_url="http://test-url"
        )
        
        # 创建Agent
        agent = SemanticSQLReActAgent(
            llm=test_llm,
            memory_manager=Neo4jMemoryManager(),
            max_iterations=3,
            verbose=True
        )
        
        # 验证Agent属性
        assert agent.llm is not None
        assert len(agent.get_tool_names()) > 0
        
        logger.info(f"✅ 新Agent创建成功，工具: {agent.get_tool_names()}")
        return True
        
    except Exception as e:
        logger.error(f"❌ 新Agent测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    logger.info("🚀 开始新架构简化测试")
    
    # 测试核心组件
    component_results = test_new_architecture_components()
    
    # 测试新Agent
    agent_result = test_new_agent_direct()
    
    # 汇总结果
    total_components = len(component_results)
    passed_components = sum(component_results.values())
    
    logger.info(f"\n📊 测试结果:")
    logger.info(f"  核心组件: {passed_components}/{total_components}")
    logger.info(f"  新Agent: {'通过' if agent_result else '失败'}")
    
    if passed_components == total_components and agent_result:
        logger.info("🎉 新架构核心功能全部正常！")
        return True
    else:
        logger.warning("⚠️ 部分功能需要调试")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)