#!/usr/bin/env python3
"""
调试field_classification工具的测试脚本
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tools.analysis_tools.field_classification_tool import FieldClassificationTool
from tools.analysis_tools.schema_extraction_tool import SchemaExtractionTool
from tools.analysis_tools.domain_analysis_tool import DomainAnalysisTool
from utils.database import DatabaseManager
from config.database import DatabaseConfig, DatabaseType
from utils.memory import DatabaseAnalysisMemory
import json

def test_field_classification_debug():
    """调试field_classification工具"""
    
    # 创建数据库配置
    db_config = DatabaseConfig(
        type=DatabaseType.SQLITE,
        database="testdb",
        host="localhost",
        port=5432,
        username="test",
        password="test"
    )
    
    # 创建数据库管理器
    db_manager = DatabaseManager(db_config)
    
    # 创建内存
    memory = DatabaseAnalysisMemory()
    
    # 创建工具
    schema_tool = SchemaExtractionTool(db_manager=db_manager)
    domain_tool = DomainAnalysisTool()
    field_tool = FieldClassificationTool()
    
    # 设置内存引用
    domain_tool.set_memory_reference(memory)
    field_tool.set_memory_reference(memory)
    
    print("=== 步骤1: 使用模拟数据库结构 ===")
    # 使用模拟的schema数据
    schema_data = {
        "database_name": "testdb",
        "tables": {
            "users": {
                "table_name": "users",
                "columns": [
                    {"name": "id", "type": "INTEGER", "nullable": False},
                    {"name": "username", "type": "VARCHAR(50)", "nullable": False},
                    {"name": "email", "type": "VARCHAR(100)", "nullable": False},
                    {"name": "created_at", "type": "TIMESTAMP", "nullable": False}
                ],
                "primary_keys": ["id"],
                "foreign_keys": [],
                "indexes": [],
                "comment": "User information table",
                "column_count": 4
            },
            "orders": {
                "table_name": "orders",
                "columns": [
                    {"name": "id", "type": "INTEGER", "nullable": False},
                    {"name": "user_id", "type": "INTEGER", "nullable": False},
                    {"name": "total_amount", "type": "DECIMAL(10,2)", "nullable": False},
                    {"name": "order_date", "type": "DATE", "nullable": False}
                ],
                "primary_keys": ["id"],
                "foreign_keys": [{"column": "user_id", "referenced_table": "users", "referenced_column": "id"}],
                "indexes": [],
                "comment": "Order information table",
                "column_count": 4
            }
        },
        "table_count": 2,
        "extraction_params": {
            "include_views": False,
            "include_indexes": False,
            "sample_data": False
        }
    }
    
    print(f"Mock schema data type: {type(schema_data)}")
    print(f"Schema data keys: {list(schema_data.keys())}")
    print(f"Tables type: {type(schema_data['tables'])}")
    print(f"Table names: {list(schema_data['tables'].keys())}")
    
    # 保存到内存
    memory.update_analysis("schema_info", schema_data)
    print("Schema info saved to memory")
    
    print("\n=== 步骤2: 检查内存状态 ===")
    print(f"Memory object: {memory}")
    print(f"Memory type: {type(memory)}")
    if hasattr(memory, 'memories'):
        print(f"Memory.memories: {memory.memories}")
    if hasattr(memory, 'get_analysis'):
        schema_from_memory = memory.get_analysis('schema_info')
        print(f"Schema from memory: {type(schema_from_memory)} - {schema_from_memory}")
    
    print("\n=== 步骤3: 领域分析 ===")
    try:
        # 不传递参数，让工具从内存中自动获取
        domain_result = domain_tool._run()
        print(f"Domain analysis result: {domain_result}")
        
        # 保存到内存
        memory.update_analysis("domain_info", domain_result)
        print("Domain info saved to memory")
        
    except Exception as e:
        print(f"Domain analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n=== 步骤4: 字段分类 ===")
    try:
        # 不传递参数，让工具从内存中自动获取
        field_result = field_tool._run()
        print(f"Field classification result: {field_result}")
        
    except Exception as e:
        print(f"Field classification failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_field_classification_debug()