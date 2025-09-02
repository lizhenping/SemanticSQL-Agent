#!/usr/bin/env python3
"""
测试简化后的schema_extraction_tool
验证是否采用了pipeline的简洁设计方法
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.database import DatabaseManager
from config.database import DatabaseConfig
from tools.analysis_tools.schema_extraction_tool import SchemaExtractionTool
import json

def test_simplified_schema_extraction():
    """测试简化后的schema extraction工具"""
    print("=== 测试简化后的Schema Extraction Tool ===")
    
    try:
        # 初始化数据库配置和管理器
        db_config = DatabaseConfig()
        db_manager = DatabaseManager(config=db_config)
        
        # 初始化数据库连接
        if not db_manager.initialize():
            print("数据库连接失败")
            return False
        
        # 创建工具实例
        tool = SchemaExtractionTool(db_manager=db_manager)
        
        print(f"工具名称: {tool.name}")
        print(f"工具描述: {tool.description}")
        
        # 测试参数
        test_params = {
            "database_name": "testdb",
            "include_views": False,
            "include_indexes": False,
            "sample_data": True,
            "tables": None  # 提取所有表
        }
        
        print(f"\n测试参数: {json.dumps(test_params, ensure_ascii=False, indent=2)}")
        
        # 执行工具
        print("\n开始执行schema extraction...")
        result = tool._run(**test_params)
        
        # 解析结果
        result_data = json.loads(result)
        
        print(f"\n提取结果概览:")
        print(f"- 数据库名: {result_data['database_name']}")
        print(f"- 表数量: {result_data['table_count']}")
        print(f"- 提取参数: {json.dumps(result_data['extraction_params'], ensure_ascii=False)}")
        
        # 显示前3个表的信息
        tables = result_data['tables']
        table_names = list(tables.keys())[:3]
        
        print(f"\n前3个表的详细信息:")
        for table_name in table_names:
            table_info = tables[table_name]
            print(f"\n表名: {table_name}")
            print(f"  注释: {table_info.get('comment', '无')}")
            print(f"  列数: {len(table_info.get('columns', []))}")
            print(f"  主键: {table_info.get('primary_key', [])}")
            
            # 显示前3列的信息
            columns = table_info.get('columns', [])[:3]
            if columns:
                print(f"  前3列:")
                for col in columns:
                    print(f"    - {col['name']} ({col['type']}) - {col.get('comment', '无注释')}")
            
            # 显示样本数据
            sample_data = table_info.get('sample_data', [])
            if sample_data:
                print(f"  样本数据行数: {len(sample_data)}")
        
        print("\n=== Schema Extraction 测试完成 ===")
        return True
        
    except Exception as e:
        print(f"测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_simplified_schema_extraction()
    sys.exit(0 if success else 1)