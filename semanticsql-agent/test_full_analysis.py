#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整分析流程测试
"""

from config.database import DatabaseConfig
from utils.database import DatabaseManager
from tools.analysis_tools.schema_extraction_tool import SchemaExtractionTool
from tools.analysis_tools.domain_analysis_tool import DomainAnalysisTool
from utils.memory import DatabaseAnalysisMemory
import json

def test_full_analysis():
    """测试完整的分析流程"""
    try:
        # 初始化数据库连接
        config = DatabaseConfig(
            host='192.168.200.216',
            port=13306,
            database='testdb',
            username='testuser',
            password='testpass'
        )
        
        print(f"连接数据库: {config.host}:{config.port}/{config.database}")
        
        db = DatabaseManager(config)
        
        # 初始化连接
        if not db.initialize():
            print("✗ 数据库连接失败")
            return False
        print("✓ 数据库连接成功")
        
        # 初始化内存
        memory = DatabaseAnalysisMemory()
        
        # 步骤1: Schema Extraction
        print("\n正在执行schema_extraction...")
        schema_tool = SchemaExtractionTool(db_manager=db)
        schema_tool.set_memory_reference(memory)
        
        schema_result = schema_tool._run(
            database_name='testdb',
            include_views=False,
            include_indexes=True,
            sample_data=False,
            tables=None
        )
        
        # 解析并保存schema结果
        if isinstance(schema_result, str):
            schema_data = json.loads(schema_result)
        else:
            schema_data = schema_result
            
        print(f"\n=== Schema Extraction 结果 ===")
        print(f"数据库名: {schema_data.get('database_name')}")
        print(f"表数量: {schema_data.get('table_count')}")
        
        # 手动保存到内存
        memory.update_analysis('schema_info', schema_data)
        print("✓ Schema info 已保存到内存")
        
        # 验证内存中的数据
        saved_schema = memory.get_analysis('schema_info')
        print(f"内存中的schema_info类型: {type(saved_schema)}")
        if saved_schema:
            tables = saved_schema.get('tables', {})
            print(f"内存中的tables类型: {type(tables)}")
            print(f"内存中的tables键数量: {len(tables) if isinstance(tables, dict) else 'N/A'}")
        
        # 步骤2: Domain Analysis
        print("\n正在执行domain_analysis...")
        domain_tool = DomainAnalysisTool()
        domain_tool.set_memory_reference(memory)
        
        try:
            domain_result = domain_tool._run()
            
            if isinstance(domain_result, str):
                domain_data = json.loads(domain_result)
            else:
                domain_data = domain_result
                
            print(f"\n=== Domain Analysis 结果 ===")
            print(f"主要领域: {domain_data.get('primary_domain')}")
            print(f"子领域: {domain_data.get('sub_domains')}")
            print(f"领域置信度: {domain_data.get('domain_confidence')}")
            
            print("\n✓ Domain analysis 执行成功！")
            
        except Exception as e:
            print(f"✗ Domain analysis 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        db.close()
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_full_analysis()