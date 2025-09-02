#!/usr/bin/env python3
"""
测试schema_extraction预执行和domain_analysis修复
验证analyze_database方法中的程序化schema提取是否有效
"""

import sys
import os
import json
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.settings import Settings
from config.database import DatabaseConfig
from agent.sql_agent import SQLAgent
from utils.database import DatabaseManager
from utils.memory import DatabaseAnalysisMemory
from tools.analysis_tools.domain_analysis_tool import DomainAnalysisTool

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_schema_domain_fix():
    """测试schema_extraction预执行和domain_analysis修复"""
    try:
        # 1. 初始化配置
        logger.info("=== 初始化配置 ===")
        settings = Settings()
        db_config = DatabaseConfig()
        
        # 2. 创建数据库管理器
        logger.info("=== 创建数据库管理器 ===")
        db_manager = DatabaseManager(db_config)
        
        # 初始化数据库连接
        if not db_manager.initialize():
            logger.error("数据库连接失败")
            return False
        logger.info("数据库连接成功")
        
        # 3. 创建SQL Agent
        logger.info("=== 创建SQL Agent ===")
        agent = SQLAgent(settings, db_config)
        
        # 4. 测试analyze_database方法（包含预执行schema_extraction）
        logger.info("=== 测试analyze_database方法 ===")
        database_name = db_config.database
        result = agent.analyze_database(database_name)
        
        if not result["success"]:
            logger.error(f"analyze_database失败: {result.get('error', 'Unknown error')}")
            return False
        
        logger.info("analyze_database执行成功")
        
        # 5. 验证记忆中是否有schema_info
        logger.info("=== 验证记忆状态 ===")
        memory_state = agent.get_memory_state()
        
        if 'schema_info' not in memory_state:
            logger.error("记忆中未找到schema_info")
            return False
        
        schema_info = memory_state['schema_info']
        logger.info(f"找到schema_info，包含 {len(schema_info.get('tables', {}))} 个表")
        
        # 6. 单独测试domain_analysis工具
        logger.info("=== 单独测试domain_analysis工具 ===")
        domain_tool = DomainAnalysisTool(llm=agent.llm)
        domain_tool.set_memory_reference(agent.memory)
        
        try:
            domain_result = domain_tool._run(
                database_name=database_name,
                analysis_focus="business_domain"
            )
            logger.info("domain_analysis工具执行成功")
            logger.info(f"Domain分析结果: {domain_result[:200]}...")
        except Exception as e:
            logger.error(f"domain_analysis工具执行失败: {str(e)}")
            return False
        
        # 7. 验证轨迹记录
        logger.info("=== 验证轨迹记录 ===")
        if hasattr(agent, 'callback_handler'):
            trajectories = agent.callback_handler.get_trajectories()
            logger.info(f"记录了 {len(trajectories)} 个轨迹")
            
            for i, traj in enumerate(trajectories):
                logger.info(f"轨迹 {i+1}: {traj.get('tool_name', 'Unknown')} - {traj.get('status', 'Unknown')}")
        
        logger.info("=== 所有测试通过 ===")
        return True
        
    except Exception as e:
        logger.error(f"测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 清理资源
        if 'db_manager' in locals():
            db_manager.close()

def main():
    """主函数"""
    logger.info("开始测试schema_extraction预执行和domain_analysis修复")
    
    success = test_schema_domain_fix()
    
    if success:
        logger.info("✅ 所有测试通过！schema_extraction预执行和domain_analysis修复成功")
        sys.exit(0)
    else:
        logger.error("❌ 测试失败")
        sys.exit(1)

if __name__ == "__main__":
    main()