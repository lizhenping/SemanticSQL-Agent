#!/usr/bin/env python3
"""
SemanticSQL Agent 三步流程运行脚本
连接数据库 → 分析数据库 → 生成问题
"""

import sys
import json
import time
from pathlib import Path

# 添加路径
sys.path.insert(0, str(Path(__file__).parent))

from database.connection_manager import DatabaseManager
from tools.sql_tools import SyncSchemaExtractionTool, SyncSQLGenerationTool
from config.trae_config import TraeConfig


def connect_database(config_path='trae_config.yaml'):
    """第一步：连接数据库"""
    print("🔌 第一步：连接数据库")
    print("=" * 50)
    
    try:
        config = TraeConfig.load_config(config_path)
        db_manager = DatabaseManager(config.database)
        
        if db_manager.initialize():
            print("✅ 数据库连接成功")
            
            # 获取数据库基本信息
            info = db_manager.get_database_info()
            print(f"📊 数据库类型: {info['type']}")
            print(f"🗄️  数据库名称: {info['database']}")
            print(f"🔗 连接地址: {info['host']}")
            print(f"📋 表数量: {info['tables_count']}")
            
            return db_manager, config
        else:
            print("❌ 数据库连接失败")
            return None, None
            
    except Exception as e:
        print(f"❌ 连接错误: {e}")
        return None, None


def analyze_database(db_manager, config):
    """第二步：分析数据库"""
    print("\n🔍 第二步：分析数据库")
    print("=" * 50)
    
    try:
        # 使用SchemaExtractionTool分析数据库
        schema_tool = SyncSchemaExtractionTool(config.database)
        
        print("📊 正在提取数据库结构...")
        schema_result = schema_tool.execute()
        
        if schema_result.get("success"):
            schema_data = schema_result.get("data", {})
            
            print("✅ 数据库分析完成")
            print(f"📋 总表数: {schema_data.get('total_tables', 0)}")
            
            # 显示表信息
            tables = schema_data.get("tables", {})
            for table_name, table_info in tables.items():
                print(f"  📑 {table_name}: {len(table_info.get('columns', []))} 个字段")
                
            return schema_data
        else:
            print("❌ 数据库分析失败")
            return {}
            
    except Exception as e:
        print(f"❌ 分析错误: {e}")
        return {}


def generate_question(config, schema_data, question):
    """第三步：生成问题"""
    print(f"\n🤖 第三步：生成SQL查询")
    print("=" * 50)
    print(f"📝 用户问题: {question}")
    
    try:
        # 使用SQLGenerationTool生成查询
        sql_tool = SyncSQLGenerationTool(config.database, schema_data)
        
        print("🔄 正在生成SQL...")
        sql_result = sql_tool.execute(query=question)
        
        if sql_result.get("success"):
            sql_data = sql_result.get("data", {})
            
            print("✅ SQL生成成功")
            print(f"🗒️  生成SQL:\n{sql_data.get('sql', '未生成')}")
            
            return sql_data
        else:
            print("❌ SQL生成失败")
            return {}
            
    except Exception as e:
        print(f"❌ 生成错误: {e}")
        return {}


def interactive_mode():
    """交互式模式"""
    print("🚀 SemanticSQL Agent 三步流程演示")
    print("流程: 连接数据库 → 分析数据库 → 生成SQL查询")
    print()
    
    # 第一步：连接数据库
    db_manager, config = connect_database()
    if not db_manager:
        return
    
    try:
        # 第二步：分析数据库
        schema_data = analyze_database(db_manager, config)
        if not schema_data:
            return
        
        # 保存分析结果
        with open("database_analysis.json", "w", encoding="utf-8") as f:
            json.dump(schema_data, f, indent=2, ensure_ascii=False)
        print("💾 数据库分析结果已保存到: database_analysis.json")
        
        # 第三步：生成问题
        print("\n💡 请输入您的问题（输入 'exit' 退出）:")
        while True:
            question = input("\n问题: ").strip()
            if question.lower() == 'exit':
                break
            if not question:
                continue
                
            sql_data = generate_question(config, schema_data, question)
            if sql_data:
                # 保存查询结果
                result = {
                    "question": question,
                    "sql": sql_data.get("sql"),
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                
                with open("query_history.json", "a", encoding="utf-8") as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                    f.write("\n")
                print("💾 查询记录已保存")
    
    finally:
        db_manager.close()
        print("\n🔌 数据库连接已关闭")


def demo_mode():
    """演示模式"""
    print("🎭 演示模式：展示完整的三步流程")
    
    # 使用预设问题
    demo_questions = [
        "查询所有用户的数量",
        "找出最近一周创建的订单",
        "统计每个用户的订单总数"
    ]
    
    db_manager, config = connect_database()
    if not db_manager:
        return
    
    try:
        schema_data = analyze_database(db_manager, config)
        if not schema_data:
            return
        
        print("\n🎯 开始演示问题生成:")
        for i, question in enumerate(demo_questions, 1):
            print(f"\n--- 演示 {i}/{len(demo_questions)} ---")
            sql_data = generate_question(config, schema_data, question)
            time.sleep(1)  # 演示间隔
    
    finally:
        db_manager.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "demo":
            demo_mode()
        elif sys.argv[1] == "interactive":
            interactive_mode()
        else:
            print("使用方法:")
            print("  python3 run_flow.py              # 交互模式")
            print("  python3 run_flow.py demo         # 演示模式")
            print("  python3 run_flow.py interactive  # 交互模式")
    else:
        interactive_mode()