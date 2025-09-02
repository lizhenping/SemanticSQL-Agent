#!/usr/bin/env python3
"""
测试修复后的 schema_extraction 工具和回调处理器
"""

import sys
import os
import json
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.database import DatabaseConfig
from utils.database import DatabaseManager
from tools.analysis_tools.schema_extraction_tool import SchemaExtractionTool
from utils.memory import DatabaseAnalysisMemory
from utils.callbacks import TrajectoryCallbackHandler
from utils.trajectory import TrajectoryRecorder
from langchain_openai import ChatOpenAI

def test_schema_extraction_with_callback():
    """测试修复后的schema_extraction工具和回调处理器"""
    print("=== 测试修复后的 schema_extraction 工具 ===")
    
    try:
        # 1. 配置数据库连接
        db_config = DatabaseConfig(
            host="192.168.200.216",
            port=13306,
            database="testdb",
            username="testuser",
            password="testpass"
        )
        
        # 2. 初始化数据库管理器
        db_manager = DatabaseManager(db_config)
        db_manager.initialize()
        print(f"✓ 成功连接到数据库: {db_config.host}:{db_config.port}/{db_config.database}")
        
        # 3. 创建schema_extraction工具
        schema_tool = SchemaExtractionTool(db_manager=db_manager)
        print("✓ 成功创建 SchemaExtractionTool")
        
        # 5. 创建记忆和回调处理器
        memory = DatabaseAnalysisMemory()
        trajectory_recorder = TrajectoryRecorder()
        callback_handler = TrajectoryCallbackHandler(trajectory_recorder)
        
        # 设置回调处理器的memory引用
        object.__setattr__(callback_handler, 'memory', memory)
        
        # 创建一个模拟的执行对象
        from uuid import uuid4
        from datetime import datetime
        from models.schemas import AgentStep, AgentStepType, AgentExecution
        
        execution = AgentExecution(
            agent_id="test_agent",
            task_id="test_task",
            start_time=datetime.now()
        )
        callback_handler.current_execution = execution
        
        print("✓ 成功创建记忆和回调处理器")
        
        # 6. 测试工具执行
        print("\n--- 执行 schema_extraction 工具 ---")
        
        # 模拟LangChain工具调用流程
        run_id = uuid4()
        
        # 模拟工具开始
        callback_handler.on_tool_start(
            serialized={"name": "schema_extraction"},
            input_str='{"database_name": "testdb"}',
            run_id=run_id
        )
        
        # 执行工具
        result = schema_tool._run(database_name="testdb")
        print(f"工具返回类型: {type(result)}")
        print(f"工具返回内容（前200字符）: {str(result)[:200]}...")
        
        # 确保current_step存在并设置工具名称
        if callback_handler.current_step:
            callback_handler.current_step.tool_name = "schema_extraction"
        
        # 模拟工具结束
        callback_handler.on_tool_end(
            output=result,
            run_id=run_id
        )
        
        # 7. 检查记忆中是否保存了结果
        print("\n--- 检查记忆状态 ---")
        memory_vars = memory.load_memory_variables({})
        print(f"记忆变量键: {list(memory_vars.keys())}")
        
        if 'db_analysis' in memory_vars:
            db_analysis = memory_vars['db_analysis']
            print(f"db_analysis 键: {list(db_analysis.keys()) if isinstance(db_analysis, dict) else 'Not a dict'}")
            
            if isinstance(db_analysis, dict) and 'schema_info' in db_analysis:
                schema_info = db_analysis['schema_info']
                print(f"✓ schema_info 已保存到记忆")
                print(f"  - 数据库名: {schema_info.get('database_name', 'N/A')}")
                print(f"  - 表数量: {schema_info.get('table_count', 'N/A')}")
                if 'tables' in schema_info:
                    table_names = list(schema_info['tables'].keys())[:3]
                    print(f"  - 前3个表: {table_names}")
            else:
                print("✗ schema_info 未找到在记忆中")
        else:
            print("✗ db_analysis 未找到在记忆中")
        
        # 8. 检查轨迹记录
        print("\n--- 检查轨迹记录 ---")
        trajectories = callback_handler.get_trajectories()
        print(f"轨迹数量: {len(trajectories)}")
        
        for i, traj in enumerate(trajectories):
            print(f"轨迹 {i+1}:")
            print(f"  - 类型: {traj.get('type', 'N/A')}")
            print(f"  - 工具名: {traj.get('tool_name', 'N/A')}")
            print(f"  - 输出类型: {type(traj.get('output', 'N/A'))}")
            if 'output' in traj and isinstance(traj['output'], dict):
                output_keys = list(traj['output'].keys())[:5]
                print(f"  - 输出键（前5个）: {output_keys}")
        
        print("\n=== 测试完成 ===")
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if 'db_manager' in locals():
            db_manager.close()

if __name__ == "__main__":
    success = test_schema_extraction_with_callback()
    sys.exit(0 if success else 1)