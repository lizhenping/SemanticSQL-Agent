#!/usr/bin/env python
"""
SemanticSQL Agent 功能测试脚本
测试核心功能是否正常工作
"""

import sys
import os
import json
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from config.trae_config import TraeConfig
from database.connection_manager import DatabaseManager
from agent.smart_sql_agent import SmartSQLAgent


def test_database_connection():
    """测试数据库连接"""
    print("=" * 60)
    print("测试数据库连接...")
    
    try:
        # 使用默认配置
        config = TraeConfig.load_config('configs/config.yaml')
        
        # 创建数据库管理器
        db_manager = DatabaseManager(config.database)
        
        # 初始化连接
        if db_manager.initialize():
            print("✅ 数据库连接成功!")
            
            # 获取数据库信息
            info = db_manager.get_database_info()
            print(f"  数据库: {info.get('database')}")
            print(f"  类型: {info.get('type')}")
            print(f"  版本: {info.get('version')}")
            print(f"  表数量: {info.get('tables_count')}")
            
            # 列出表
            tables = db_manager.get_tables()
            if tables:
                print(f"  表列表: {', '.join(tables[:5])}")
                if len(tables) > 5:
                    print(f"    ... 还有 {len(tables) - 5} 个表")
            
            db_manager.close()
            return True
        else:
            print("❌ 数据库连接失败")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def test_simple_query():
    """测试简单查询"""
    print("=" * 60)
    print("测试简单查询功能...")
    
    try:
        # 加载配置
        config = TraeConfig.load_config('configs/config.yaml')
        
        # 初始化数据库连接
        db_manager = DatabaseManager(config.database)
        if not db_manager.initialize():
            print("❌ 数据库连接失败")
            return False
        
        # 创建智能体
        agent = SmartSQLAgent(config)
        
        # 测试查询
        test_queries = [
            "显示所有表",
            "统计数据库中有多少个表"
        ]
        
        for query in test_queries:
            print(f"\n查询: {query}")
            result = agent.query(query)
            
            if result.success:
                print("✅ 查询成功")
                if result.sql:
                    print(f"  SQL: {result.sql}")
                if result.answer:
                    print(f"  答案: {result.answer}")
            else:
                print(f"❌ 查询失败: {result.error}")
        
        db_manager.close()
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def test_smart_analysis():
    """测试智能分析功能"""
    print("=" * 60)
    print("测试智能分析功能...")
    
    try:
        # 加载配置
        config = TraeConfig.load_config('configs/config.yaml')
        
        # 创建智能体
        agent = SmartSQLAgent(config)
        
        # 执行智能分析
        print("开始智能分析数据库...")
        result = agent.smart_analyze("分析这个数据库的基本信息")
        
        if result.get("success"):
            print("✅ 智能分析成功!")
            print(f"  执行步数: {result.get('steps_taken', 0)}")
            print(f"  执行时间: {result.get('execution_time', 0):.2f}秒")
            
            # 显示部分结果
            final_result = result.get("final_result", {})
            if final_result.get("database_connection"):
                db_info = final_result["database_connection"]
                print(f"  数据库: {db_info.get('database')}")
                print(f"  表数量: {db_info.get('total_tables')}")
            
            return True
        else:
            print(f"❌ 智能分析失败: {result.get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def test_config_loading():
    """测试配置加载"""
    print("=" * 60)
    print("测试配置加载...")
    
    try:
        # 测试加载YAML配置
        config = TraeConfig.load_config('configs/config.yaml')
        
        print("✅ 配置加载成功!")
        print(f"  应用名称: {config.app_name}")
        print(f"  版本: {config.app_version}")
        print(f"  数据库类型: {config.database.type}")
        print(f"  数据库主机: {config.database.host}:{config.database.port}")
        print(f"  LLM模型: {config.llm.model}")
        print(f"  LLM基础URL: {config.llm.base_url}")
        
        return True
        
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        return False


def main():
    """运行所有测试"""
    print("SemanticSQL Agent 功能测试")
    print("=" * 60)
    
    tests = [
        ("配置加载", test_config_loading),
        ("数据库连接", test_database_connection),
        ("简单查询", test_simple_query),
        ("智能分析", test_smart_analysis)
    ]
    
    results = []
    
    for name, test_func in tests:
        print(f"\n开始测试: {name}")
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"❌ 测试异常: {e}")
            results.append((name, False))
    
    # 显示测试结果总结
    print("\n" + "=" * 60)
    print("测试结果总结:")
    print("-" * 40)
    
    passed = 0
    failed = 0
    
    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"  {name}: {status}")
        if success:
            passed += 1
        else:
            failed += 1
    
    print("-" * 40)
    print(f"总计: {passed} 通过, {failed} 失败")
    
    if failed == 0:
        print("\n🎉 所有测试通过!")
    else:
        print(f"\n⚠️ 有 {failed} 个测试失败")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())