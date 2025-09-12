#!/usr/bin/env python
"""Neo4j 接口诊断测试

测试所有工具与 Neo4j 的连接和接口兼容性
确保不同工具使用一致的数据库访问模式
"""

import sys
import os
import logging
from pathlib import Path

# 添加项目根路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 设置日志级别避免过多输出
logging.getLogger().setLevel(logging.WARNING)


def test_neo4j_memory_manager():
    """测试 Neo4jMemoryManager 基础功能"""
    print("🔧 测试 Neo4jMemoryManager...")
    
    try:
        from utils.memory import Neo4jMemoryManager
        from config.settings import get_settings
        
        settings = get_settings()
        memory_manager = Neo4jMemoryManager(settings)
        
        print("✅ Neo4jMemoryManager 实例化成功")
        
        # 检查关键属性
        assert hasattr(memory_manager, 'neo4j_graph'), "❌ 缺少 neo4j_graph 属性"
        assert memory_manager.neo4j_graph is not None, "❌ neo4j_graph 为空"
        print("✅ neo4j_graph 属性正常")
        
        # 测试连接
        result = memory_manager.neo4j_graph.query("MATCH (n) RETURN count(n) LIMIT 1")
        print(f"✅ Neo4j 连接正常，节点数: {result[0]['count(n)']}")
        
        return memory_manager
        
    except Exception as e:
        print(f"❌ Neo4jMemoryManager 测试失败: {e}")
        return None


def test_table_analysis_pattern():
    """测试 table_analysis_tool 的访问模式（参考实现）"""
    print("\n🔧 测试 table_analysis_tool 访问模式...")
    
    try:
        from utils.memory import Neo4jMemoryManager
        from config.settings import get_settings
        
        memory_manager = Neo4jMemoryManager(get_settings())
        
        # 模拟 table_analysis_tool 的访问方式
        cypher = "MATCH (t:Table) RETURN count(t) as count LIMIT 1"
        result = memory_manager.neo4j_graph.query(cypher)
        
        print(f"✅ table_analysis_tool 模式工作正常: {result}")
        return True
        
    except Exception as e:
        print(f"❌ table_analysis_tool 模式失败: {e}")
        return False


def test_er_analysis_neo4j_access():
    """测试修复后的 ER 分析工具 Neo4j 访问"""
    print("\n🔧 测试 ER 分析工具 Neo4j 访问...")
    
    try:
        # 直接读取文件检查修复
        er_tool_path = project_root / "tools/analysis_tools/er_analysis_tool.py"
        with open(er_tool_path, 'r') as f:
            content = f.read()
        
        # 确认没有 get_graph() 调用
        get_graph_count = content.count('get_graph()')
        assert get_graph_count == 0, f"❌ 仍有 {get_graph_count} 处 get_graph() 调用"
        print("✅ 已清除所有 get_graph() 调用")
        
        # 确认有正确的 neo4j_graph 访问
        neo4j_graph_count = content.count('self.memory_manager.neo4j_graph')
        print(f"✅ 找到 {neo4j_graph_count} 处正确的 neo4j_graph 访问")
        
        return True
        
    except Exception as e:
        print(f"❌ ER 分析工具访问测试失败: {e}")
        return False


def test_er_analysis_tool_instantiation():
    """测试 ER 分析工具实例化（绕过循环导入）"""
    print("\n🔧 测试 ER 分析工具实例化...")
    
    try:
        # 使用工厂函数避免循环导入
        from tools.analysis_tools.er_analysis_tool import create_er_analysis_tool
        from utils.memory import Neo4jMemoryManager
        from config.settings import get_settings
        
        memory_manager = Neo4jMemoryManager(get_settings())
        er_tool = create_er_analysis_tool(memory_manager=memory_manager)
        
        print("✅ ER 分析工具实例化成功")
        
        # 检查关键属性
        assert hasattr(er_tool, 'memory_manager'), "❌ 缺少 memory_manager 属性"
        assert er_tool.memory_manager is not None, "❌ memory_manager 为空"
        assert hasattr(er_tool.memory_manager, 'neo4j_graph'), "❌ memory_manager 缺少 neo4j_graph"
        
        print("✅ ER 工具属性检查通过")
        return True
        
    except Exception as e:
        print(f"❌ ER 工具实例化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_comprehensive_test():
    """运行综合测试"""
    print("🔍 Neo4j 接口综合诊断测试")
    print("=" * 60)
    
    results = {}
    
    # 1. 基础连接测试
    memory_manager = test_neo4j_memory_manager()
    results['memory_manager'] = memory_manager is not None
    
    # 2. 参考实现测试
    results['table_pattern'] = test_table_analysis_pattern()
    
    # 3. ER 工具修复验证
    results['er_access_fix'] = test_er_analysis_neo4j_access()
    
    # 4. ER 工具实例化测试
    results['er_instantiation'] = test_er_analysis_tool_instantiation()
    
    # 总结
    print(f"\n📊 测试总结:")
    print("=" * 30)
    for test_name, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"{status} {test_name}: {'PASS' if passed else 'FAIL'}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print(f"\n🎉 所有测试通过！Neo4j 接口修复成功")
        return True
    else:
        print(f"\n⚠️  部分测试失败，请检查上述输出")
        return False


if __name__ == "__main__":
    run_comprehensive_test()