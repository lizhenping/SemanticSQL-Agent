#!/usr/bin/env python3
"""
测试 CLI 执行环境中的工具内存共享问题
"""

import sys
import os
import logging
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import Settings
from config.database import DatabaseConfig
from agent.data_generation_agent import DataGenerationAgent
from utils.database import DatabaseManager

# 设置简化日志，只显示错误
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_cli_execution():
    """测试 CLI 执行环境"""
    print("=" * 60)
    print("测试 CLI 执行环境中的工具内存共享")
    print("=" * 60)
    
    # 创建配置
    settings = Settings()
    db_config = DatabaseConfig()
    db_config.database = "testdb"
    
    print(f"数据库配置: {db_config.database}")
    
    try:
        # 创建 Agent
        print("\n1. 创建 DataGenerationAgent...")
        agent = DataGenerationAgent(settings, db_config)
        print("Agent 创建成功")
        
        # 检查工具的内存引用
        print("\n2. 检查工具的内存引用...")
        for tool in agent.tools:
            if hasattr(tool, '_agent_memory'):
                memory_status = "有内存引用" if tool._agent_memory else "无内存引用"
                print(f"  {tool.name}: {memory_status}")
            else:
                print(f"  {tool.name}: 没有 _agent_memory 属性")
        
        # 检查初始内存状态
        print("\n3. 检查初始内存状态...")
        memory_state = agent.get_memory_state()
        print(f"初始内存状态: {memory_state}")
        
        # 手动测试 schema_extraction 工具
        print("\n4. 手动测试 schema_extraction 工具...")
        schema_tool = None
        for tool in agent.tools:
            if tool.name == "schema_extraction":
                schema_tool = tool
                break
        
        if schema_tool:
            print("找到 schema_extraction 工具")
            print(f"Schema 工具内存引用: {hasattr(schema_tool, '_agent_memory') and schema_tool._agent_memory is not None}")
            
            # 确保工具有正确的内存引用
            if hasattr(schema_tool, 'set_memory_reference'):
                schema_tool.set_memory_reference(agent.memory)
                print("已设置 schema_extraction 工具的内存引用")
            
            try:
                # 直接调用工具
                schema_result = schema_tool._run(database_name="testdb")
                print(f"Schema 提取成功，结果长度: {len(str(schema_result))}")
                
                # 检查内存状态
                memory_state_after_schema = agent.get_memory_state()
                print(f"Schema 提取后内存状态: {memory_state_after_schema}")
                
                # 检查实际的 memories 内容
                actual_memories = agent.memory.memories
                print(f"实际内存内容: {actual_memories}")
                print(f"内存中的键: {list(actual_memories.keys()) if actual_memories else 'None'}")
                
                # 检查是否有 schema_info
                if 'schema_info' in actual_memories:
                    schema_info = actual_memories['schema_info']
                    print(f"Schema info 存在，类型: {type(schema_info)}")
                    if isinstance(schema_info, dict) and 'tables' in schema_info:
                        print(f"包含 {len(schema_info['tables'])} 个表")
                else:
                    print("Schema info 不存在于内存中")
                
            except Exception as e:
                print(f"Schema 提取失败: {e}")
        else:
            print("未找到 schema_extraction 工具")
        
        # 手动测试 domain_analysis 工具
        print("\n5. 手动测试 domain_analysis 工具...")
        domain_tool = None
        for tool in agent.tools:
            if tool.name == "domain_analysis":
                domain_tool = tool
                break
        
        if domain_tool:
            print("找到 domain_analysis 工具")
            print(f"Domain 工具内存引用: {hasattr(domain_tool, '_agent_memory') and domain_tool._agent_memory is not None}")
            
            # 确保工具有正确的内存引用
            if hasattr(domain_tool, 'set_memory_reference'):
                domain_tool.set_memory_reference(agent.memory)
                print("已设置 domain_analysis 工具的内存引用")
            
            try:
                # 直接调用工具
                domain_result = domain_tool._run(database_name="testdb")
                print(f"Domain 分析成功，结果长度: {len(str(domain_result))}")
                
            except Exception as e:
                print(f"Domain 分析失败: {e}")
        else:
            print("未找到 domain_analysis 工具")
        
        print("\n6. 跳过 LangChain Agent 执行，避免复杂的日志输出")
        
    except Exception as e:
        print(f"\n执行失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    test_cli_execution()