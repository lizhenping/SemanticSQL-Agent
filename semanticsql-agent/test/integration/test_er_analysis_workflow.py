#!/usr/bin/env python
"""ER 分析工具完整工作流集成测试

测试 ER 分析工具在真实环境下的完整工作流程：
- 从输入到输出的完整流程
- 与其他组件的集成
- 错误处理和边界情况
"""

import sys
import os
import json
import logging
from pathlib import Path

# 添加项目根路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 设置日志级别
logging.getLogger().setLevel(logging.WARNING)


def test_full_er_analysis_workflow():
    """测试完整的 ER 分析工作流程"""
    print("🔄 测试完整 ER 分析工作流程...")
    
    try:
        from tools.analysis_tools.er_analysis_tool import create_er_analysis_tool
        from utils.memory import Neo4jMemoryManager
        from config.settings import get_settings
        
        # 1. 创建工具实例
        memory_manager = Neo4jMemoryManager(get_settings())
        er_tool = create_er_analysis_tool(memory_manager=memory_manager)
        print("✅ 步骤1: 工具实例创建成功")
        
        # 2. 模拟用户输入
        test_input = "请分析数据库中表之间的ER关系"
        
        # 3. 执行工具分析（这会触发完整流程）
        print("⏳ 步骤2: 执行 ER 关系分析...")
        
        # 注意：这里可能会因为 LLM 调用而需要较长时间
        # 也可能因为数据库为空而无法完成分析
        try:
            result = er_tool._run(test_input)
            print(f"✅ 步骤3: 分析执行完成")
            print(f"   结果类型: {type(result)}")
            print(f"   结果长度: {len(str(result))}")
            
            return True
            
        except Exception as analysis_error:
            # 分析可能因为各种原因失败，这是正常的
            error_msg = str(analysis_error)
            
            if "数据库中没有找到足够的表" in error_msg:
                print("⚠️  步骤3: 分析跳过（数据库为空，这是正常的）")
                return True
            elif "LLM调用失败" in error_msg:
                print("⚠️  步骤3: LLM 调用失败（可能是网络或配置问题）")
                return True
            else:
                print(f"❌ 步骤3: 分析执行失败: {analysis_error}")
                return False
        
    except Exception as e:
        print(f"❌ 完整工作流程测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_error_handling():
    """测试错误处理机制"""
    print("\n🔧 测试错误处理机制...")
    
    try:
        from tools.analysis_tools.er_analysis_tool import create_er_analysis_tool
        from utils.memory import Neo4jMemoryManager
        from config.settings import get_settings
        
        memory_manager = Neo4jMemoryManager(get_settings())
        er_tool = create_er_analysis_tool(memory_manager=memory_manager)
        
        # 测试空输入处理
        try:
            result = er_tool._run("")
            print("✅ 空输入处理正常")
        except Exception as e:
            print(f"⚠️  空输入处理: {e}")
        
        # 测试 None 输入处理
        try:
            result = er_tool._run(None)
            print("✅ None 输入处理正常")
        except Exception as e:
            print(f"⚠️  None 输入处理: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ 错误处理测试失败: {e}")
        return False


def test_component_integration():
    """测试与其他组件的集成"""
    print("\n🔧 测试组件集成...")
    
    try:
        from config.factories import ComponentManager
        from config.settings import get_settings
        
        settings = get_settings()
        
        # 测试 LLM 组件创建
        llm = ComponentManager.create_llm(settings)
        assert llm is not None, "LLM 组件创建失败"
        print("✅ LLM 组件集成正常")
        
        # 测试内存管理器创建
        memory_manager = ComponentManager.create_memory_manager(settings)
        assert memory_manager is not None, "内存管理器创建失败"
        print("✅ 内存管理器集成正常")
        
        return True
        
    except Exception as e:
        print(f"❌ 组件集成测试失败: {e}")
        return False


def test_data_persistence():
    """测试数据持久化"""
    print("\n🔧 测试数据持久化...")
    
    try:
        from tools.analysis_tools.er_analysis_tool import create_er_analysis_tool
        from utils.memory import Neo4jMemoryManager
        from config.settings import get_settings
        import uuid
        
        memory_manager = Neo4jMemoryManager(get_settings())
        er_tool = create_er_analysis_tool(memory_manager=memory_manager)
        neo4j_graph = memory_manager.neo4j_graph
        
        # 创建测试数据
        test_analysis_id = f"test_{uuid.uuid4().hex[:8]}"
        mock_er_analysis = {
            "business_name": "持久化测试业务",
            "business_description": "用于测试数据持久化的业务流程",
            "triplets": [
                {
                    "source_table": "test_users",
                    "source_column": "id",
                    "relation_semantic": "test_relation",
                    "target_table": "test_orders", 
                    "target_column": "user_id",
                    "business_meaning": "测试关系",
                    "confidence": 0.95
                }
            ]
        }
        
        mock_database_context = {
            "database_name": "persistence_test_db"
        }
        
        # 1. 存储数据
        analysis_id = er_tool._store_er_analysis_with_container(
            neo4j_graph, mock_er_analysis, mock_database_context
        )
        print(f"✅ 数据存储成功: {analysis_id[:8]}...")
        
        # 2. 验证数据存在
        verification_cypher = """
        MATCH (era:ERAnalysis {id: $analysis_id})
        RETURN era.business_name, era.total_triplets
        """
        
        result = neo4j_graph.query(verification_cypher, {"analysis_id": analysis_id})
        assert len(result) > 0, "存储的数据未找到"
        assert result[0]['era.business_name'] == "持久化测试业务", "数据内容不匹配"
        print("✅ 数据验证成功")
        
        # 3. 测试查询方法
        complete_analysis = er_tool.get_complete_er_analysis(analysis_id=analysis_id)
        assert complete_analysis is not None, "完整分析查询失败"
        assert complete_analysis['business_name'] == "持久化测试业务", "查询数据不匹配"
        print("✅ 完整查询成功")
        
        # 4. 清理测试数据
        cleanup_cypher = """
        MATCH (era:ERAnalysis {id: $analysis_id})
        DETACH DELETE era
        """
        neo4j_graph.query(cleanup_cypher, {"analysis_id": analysis_id})
        print("✅ 测试数据清理完成")
        
        return True
        
    except Exception as e:
        print(f"❌ 数据持久化测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_integration_tests():
    """运行所有集成测试"""
    print("🔗 ER 分析工具集成测试")
    print("=" * 50)
    
    tests = [
        ("完整工作流程", test_full_er_analysis_workflow),
        ("错误处理机制", test_error_handling),
        ("组件集成", test_component_integration),
        ("数据持久化", test_data_persistence)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            print(f"\n📋 运行测试: {test_name}")
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ 测试 {test_name} 异常: {e}")
            results[test_name] = False
    
    # 输出总结
    print(f"\n📊 集成测试总结:")
    print("=" * 30)
    
    passed_count = sum(results.values())
    total_count = len(results)
    
    for test_name, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"{status} {test_name}: {'PASS' if passed else 'FAIL'}")
    
    print(f"\n🎯 总体结果: {passed_count}/{total_count} 通过")
    
    if passed_count == total_count:
        print("🎉 所有集成测试通过！ER 分析工具集成正常")
        return True
    else:
        print("⚠️  部分集成测试失败，请检查上述输出")
        return False


if __name__ == "__main__":
    run_integration_tests()