#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
集成测试：验证修复后的schema_extraction工具与LangChain Agent的完整集成
"""

import os
import sys
import json
from datetime import datetime
from uuid import uuid4

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.database import DatabaseConfig
from utils.database import DatabaseManager
from tools.analysis_tools.schema_extraction_tool import SchemaExtractionTool
from utils.memory import DatabaseAnalysisMemory
from utils.callbacks import TrajectoryCallbackHandler
from models.schemas import AgentExecution

def test_langchain_integration():
    """测试与LangChain的完整集成"""
    try:
        print("=== 集成测试：LangChain Agent + Schema Extraction ===\n")
        
        # 1. 数据库连接
        db_config = DatabaseConfig()
        db_manager = DatabaseManager(db_config)
        
        if not db_manager.initialize():
            print("✗ 数据库连接失败")
            return False
            
        print(f"✓ 数据库连接成功: {db_config.host}:{db_config.port}/{db_config.database}")
        
        # 2. 创建工具
        schema_tool = SchemaExtractionTool(db_manager=db_manager)
        print("✓ SchemaExtractionTool 创建成功")
        
        # 3. 创建记忆和回调处理器
        memory = DatabaseAnalysisMemory()
        callback_handler = TrajectoryCallbackHandler()
        object.__setattr__(callback_handler, 'memory', memory)
        
        # 设置执行上下文
        execution = AgentExecution(
            agent_id="integration_test_agent",
            task_id="schema_extraction_test",
            start_time=datetime.now()
        )
        callback_handler.current_execution = execution
        
        print("✓ 记忆和回调处理器创建成功")
        
        # 4. 模拟LangChain工具调用流程
        print("\n--- 模拟LangChain Agent执行 ---")
        
        run_id = uuid4()
        tool_input = '{"database_name": "testdb"}'
        
        # 工具开始
        callback_handler.on_tool_start(
            serialized={"name": "schema_extraction"},
            input_str=tool_input,
            run_id=run_id
        )
        print("✓ 工具开始回调执行")
        
        # 执行工具
        result = schema_tool._run(database_name="testdb")
        print(f"✓ 工具执行完成，返回类型: {type(result)}")
        
        # 验证返回结果是JSON字符串
        if isinstance(result, str):
            try:
                parsed_result = json.loads(result)
                print(f"✓ 工具返回有效JSON，包含 {len(parsed_result.get('tables', {}))} 个表")
            except json.JSONDecodeError:
                print("✗ 工具返回的不是有效JSON")
                return False
        else:
            print(f"✗ 工具返回类型错误: {type(result)}，期望: str")
            return False
        
        # 工具结束
        callback_handler.on_tool_end(
            output=result,
            run_id=run_id
        )
        print("✓ 工具结束回调执行")
        
        # 5. 验证记忆状态
        print("\n--- 验证记忆状态 ---")
        
        if 'schema_info' in memory.memories:
            schema_info = memory.memories['schema_info']
            print(f"✓ schema_info 已保存到记忆")
            print(f"  - 数据库: {schema_info.get('database_name')}")
            print(f"  - 表数量: {schema_info.get('table_count')}")
            
            # 验证数据结构
            if isinstance(schema_info, dict) and 'tables' in schema_info:
                print("✓ 记忆中的数据结构正确")
            else:
                print("✗ 记忆中的数据结构不正确")
                return False
        else:
            print("✗ schema_info 未保存到记忆")
            return False
        
        # 6. 验证轨迹记录
        print("\n--- 验证轨迹记录 ---")
        
        trajectories = callback_handler.get_trajectories()
        if trajectories:
            print(f"✓ 轨迹记录成功，共 {len(trajectories)} 条")
            
            # 检查最后一条轨迹
            last_trajectory = trajectories[-1]
            if (last_trajectory.get('type') == 'tool_end' and 
                last_trajectory.get('tool_name') == 'schema_extraction' and
                isinstance(last_trajectory.get('output'), dict)):
                print("✓ 轨迹记录格式正确")
            else:
                print("✗ 轨迹记录格式不正确")
                print(f"  实际格式键: {list(last_trajectory.keys())}")
                print(f"  类型: {last_trajectory.get('type')}")
                print(f"  工具名: {last_trajectory.get('tool_name')}")
                print(f"  输出类型: {type(last_trajectory.get('output'))}")
                return False
        else:
            print("✗ 没有轨迹记录")
            return False
        
        # 7. 测试记忆的save_context方法
        print("\n--- 测试记忆的save_context方法 ---")
        
        # 解析JSON结果用于测试
        parsed_result = json.loads(result)
        test_inputs = {"tool_name": "schema_extraction"}
        test_outputs = parsed_result
        
        memory.save_context(test_inputs, test_outputs)
        
        # schema_extraction工具的输出会保存到'schema_info'键
        if "schema_info" in memory.memories:
            saved_data = memory.memories["schema_info"]
            if isinstance(saved_data, dict) and "tables" in saved_data:
                print("✓ save_context 方法工作正常")
                print(f"  保存的表数量: {saved_data.get('table_count', 0)}")
            else:
                print("✗ save_context 保存的数据格式不正确")
                return False
        else:
            print("✗ save_context 方法未正常工作")
            print(f"  当前记忆键: {list(memory.memories.keys())}")
            return False
        
        print("\n=== 集成测试完成：所有测试通过 ===\n")
        return True
        
    except Exception as e:
        print(f"✗ 集成测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 清理资源
        if 'db_manager' in locals():
            db_manager.close()

if __name__ == "__main__":
    success = test_langchain_integration()
    sys.exit(0 if success else 1)