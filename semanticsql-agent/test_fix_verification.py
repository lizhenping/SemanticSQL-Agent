#!/usr/bin/env python3
"""
验证schema_extraction修复效果的测试脚本
"""

import sys
sys.path.append('.')

from agent.sql_agent import SQLAgent
from utils.database import DatabaseManager
from config.database import DatabaseConfig
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_schema_extraction_fix():
    """测试schema_extraction修复效果"""
    try:
        # 创建数据库配置
        db_config = DatabaseConfig()
        logger.info(f"Database config: {db_config.host}:{db_config.port}/{db_config.database}")
        
        # 创建设置配置
        from config.settings import Settings
        settings = Settings()
        
        # 创建SQL Agent
        agent = SQLAgent(settings=settings, db_config=db_config)
        logger.info("SQL Agent created successfully")
        
        # 检查初始memory状态
        initial_memory = agent.get_memory_state()
        logger.info(f"Initial memory state: {initial_memory}")
        
        # 执行数据库分析
        logger.info("开始执行数据库分析...")
        result = agent.analyze_database('testdb')
        
        # 检查分析后的memory状态
        final_memory = agent.get_memory_state()
        logger.info(f"Final memory state keys: {list(final_memory.get('db_analysis', {}).keys())}")
        
        # 验证schema_info是否存在
        db_analysis = final_memory.get('db_analysis', {})
        if 'schema_info' in db_analysis:
            schema_info = db_analysis['schema_info']
            logger.info(f"✅ schema_info found in memory! Tables count: {len(schema_info.get('tables', {}))}")
            logger.info(f"Tables: {list(schema_info.get('tables', {}).keys())[:5]}...")  # 显示前5个表名
        else:
            logger.error("❌ schema_info not found in memory!")
            logger.error(f"Available keys: {list(db_analysis.keys())}")
        
        logger.info("分析完成！")
        logger.info(f"结果状态: {result.get('status', 'unknown')}")
        
        return result
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        # 清理资源
        if 'db_manager' in locals():
            db_manager.close()

if __name__ == "__main__":
    test_schema_extraction_fix()