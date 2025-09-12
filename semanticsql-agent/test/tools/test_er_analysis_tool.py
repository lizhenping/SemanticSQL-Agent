#!/usr/bin/env python
"""ER 分析工具完整功能测试

测试 ER 分析工具的核心功能：
- 工具创建和初始化
- 数据库上下文收集
- ER 关系分析执行
- Neo4j 存储和查询
- 一次性完整分析获取
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


class ERAnalysisTestSuite:
    """ER 分析工具测试套件"""
    
    def __init__(self):
        self.test_results = {}
        self.er_tool = None
        
    def setup(self):
        """测试环境设置"""
        print("🔧 设置测试环境...")
        
        try:
            from tools.analysis_tools.er_analysis_tool import create_er_analysis_tool
            from utils.memory import Neo4jMemoryManager
            from config.settings import get_settings
            
            # 创建组件
            memory_manager = Neo4jMemoryManager(get_settings())
            self.er_tool = create_er_analysis_tool(memory_manager=memory_manager)
            
            print("✅ 测试环境设置完成")
            return True
            
        except Exception as e:
            print(f"❌ 测试环境设置失败: {e}")
            return False
    
    def test_tool_creation(self):
        """测试工具创建和基本属性"""
        print("\n🔧 测试工具创建...")
        
        try:
            assert self.er_tool is not None, "工具实例为空"
            assert hasattr(self.er_tool, 'name'), "缺少 name 属性"
            assert hasattr(self.er_tool, 'description'), "缺少 description 属性"
            assert hasattr(self.er_tool, 'memory_manager'), "缺少 memory_manager"
            assert hasattr(self.er_tool, 'llm'), "缺少 llm 属性"
            assert hasattr(self.er_tool, 'prompt_manager'), "缺少 prompt_manager"
            
            print(f"✅ 工具创建成功: {self.er_tool.name}")
            print(f"   描述: {self.er_tool.description}")
            
            return True
            
        except Exception as e:
            print(f"❌ 工具创建测试失败: {e}")
            return False
    
    def test_database_context_gathering(self):
        """测试数据库上下文收集"""
        print("\n🔧 测试数据库上下文收集...")
        
        try:
            neo4j_graph = self.er_tool.memory_manager.neo4j_graph
            context = self.er_tool._gather_database_context_from_neo4j(neo4j_graph)
            
            assert isinstance(context, dict), "上下文不是字典类型"
            
            # 检查关键字段
            expected_fields = ['formatted_schema', 'fk_info', 'tables']
            for field in expected_fields:
                assert field in context, f"缺少关键字段: {field}"
            
            print(f"✅ 数据库上下文收集成功")
            print(f"   表数量: {len(context.get('tables', {}))}")
            print(f"   外键信息长度: {len(context.get('fk_info', ''))}")
            
            return True
            
        except Exception as e:
            print(f"❌ 数据库上下文收集失败: {e}")
            return False
    
    def test_neo4j_storage_methods(self):
        """测试 Neo4j 存储方法"""
        print("\n🔧 测试 Neo4j 存储方法...")
        
        try:
            # 测试模拟数据
            mock_er_analysis = {
                "business_name": "测试业务流程",
                "business_description": "这是一个测试的业务流程描述",
                "triplets": [
                    {
                        "source_table": "users",
                        "source_column": "id", 
                        "relation_semantic": "user_order_relation",
                        "target_table": "orders",
                        "target_column": "user_id",
                        "business_meaning": "用户拥有订单的关系",
                        "confidence": 0.9
                    }
                ]
            }
            
            mock_database_context = {
                "database_name": "test_db",
                "tables": {"users": {}, "orders": {}}
            }
            
            neo4j_graph = self.er_tool.memory_manager.neo4j_graph
            
            # 测试存储
            analysis_id = self.er_tool._store_er_analysis_with_container(
                neo4j_graph, mock_er_analysis, mock_database_context
            )
            
            assert analysis_id is not None, "存储后未返回分析ID"
            assert isinstance(analysis_id, str), "分析ID不是字符串类型"
            
            print(f"✅ Neo4j 存储成功, 分析ID: {analysis_id[:8]}...")
            
            # 清理测试数据
            cleanup_cypher = """
            MATCH (era:ERAnalysis {id: $analysis_id})
            DETACH DELETE era
            """
            neo4j_graph.query(cleanup_cypher, {"analysis_id": analysis_id})
            print("✅ 测试数据清理完成")
            
            return True
            
        except Exception as e:
            print(f"❌ Neo4j 存储测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_query_methods(self):
        """测试查询方法"""
        print("\n🔧 测试查询方法...")
        
        try:
            # 测试列表分析方法
            analyses = self.er_tool.list_er_analyses()
            assert isinstance(analyses, list), "列表分析结果不是列表类型"
            print(f"✅ 列出分析记录: {len(analyses)} 条")
            
            # 如果有数据，测试获取最新分析
            if analyses:
                latest = self.er_tool.get_latest_er_analysis("testdb")
                if latest:
                    print(f"✅ 获取最新分析成功")
                else:
                    print("⚠️  未找到最新分析（正常，可能没有该数据库的分析）")
            
            return True
            
        except Exception as e:
            print(f"❌ 查询方法测试失败: {e}")
            return False
    
    def test_prompt_template_loading(self):
        """测试提示词模板加载"""
        print("\n🔧 测试提示词模板加载...")
        
        try:
            # 测试模板文件存在
            template_path = project_root / "prompts/templates/tools/er_analysis_conceptual.j2"
            assert template_path.exists(), f"提示词模板不存在: {template_path}"
            
            # 测试模板内容
            with open(template_path, 'r') as f:
                template_content = f.read()
            
            # 检查关键元素
            required_elements = [
                "business_name",
                "business_description", 
                "triplets",
                "relation_semantic",
                "confidence"
            ]
            
            for element in required_elements:
                assert element in template_content, f"模板缺少关键元素: {element}"
            
            print("✅ 提示词模板检查通过")
            
            # 测试 PromptManager 渲染
            mock_context = {
                "formatted_schema": "CREATE TABLE test...",
                "fk_info": "外键信息",
                "tables": {"test": {"comment": "测试表"}}
            }
            
            prompt = self.er_tool.prompt_manager.render(
                'tools/er_analysis_conceptual.j2', 
                **mock_context
            )
            
            assert len(prompt) > 0, "渲染后的提示词为空"
            print(f"✅ 提示词渲染成功，长度: {len(prompt)}")
            
            return True
            
        except Exception as e:
            print(f"❌ 提示词模板测试失败: {e}")
            return False
    
    def run_all_tests(self):
        """运行所有测试"""
        print("🧪 ER 分析工具完整功能测试")
        print("=" * 50)
        
        # 设置测试环境
        if not self.setup():
            return False
        
        # 运行各项测试
        tests = [
            ("tool_creation", self.test_tool_creation),
            ("database_context", self.test_database_context_gathering), 
            ("neo4j_storage", self.test_neo4j_storage_methods),
            ("query_methods", self.test_query_methods),
            ("prompt_template", self.test_prompt_template_loading)
        ]
        
        for test_name, test_method in tests:
            try:
                self.test_results[test_name] = test_method()
            except Exception as e:
                print(f"❌ 测试 {test_name} 异常: {e}")
                self.test_results[test_name] = False
        
        # 输出总结
        self.print_summary()
        
        return all(self.test_results.values())
    
    def print_summary(self):
        """输出测试总结"""
        print(f"\n📊 测试总结:")
        print("=" * 30)
        
        passed_count = sum(self.test_results.values())
        total_count = len(self.test_results)
        
        for test_name, passed in self.test_results.items():
            status = "✅" if passed else "❌"
            print(f"{status} {test_name}: {'PASS' if passed else 'FAIL'}")
        
        print(f"\n🎯 总体结果: {passed_count}/{total_count} 通过")
        
        if passed_count == total_count:
            print("🎉 所有测试通过！ER 分析工具功能正常")
        else:
            print("⚠️  部分测试失败，请检查上述输出")


if __name__ == "__main__":
    test_suite = ERAnalysisTestSuite()
    test_suite.run_all_tests()