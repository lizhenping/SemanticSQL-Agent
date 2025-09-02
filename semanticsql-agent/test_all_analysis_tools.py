#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全面测试所有分析工具
"""

from config.database import DatabaseConfig
from utils.database import DatabaseManager
from tools.analysis_tools.schema_extraction_tool import SchemaExtractionTool
from tools.analysis_tools.domain_analysis_tool import DomainAnalysisTool
from tools.analysis_tools.field_classification_tool import FieldClassificationTool
from tools.analysis_tools.column_meaning_tool import ColumnMeaningTool
from utils.memory import DatabaseAnalysisMemory
import json

def test_all_analysis_tools():
    """测试所有分析工具的完整流程"""
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
        print("\n=== 步骤1: Schema Extraction ===")
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
            
        print(f"✓ Schema extraction 完成，发现 {schema_data.get('table_count')} 个表")
        
        # 验证内存中的数据
        saved_schema = memory.get_analysis('schema_info')
        if saved_schema:
            print("✓ Schema info 已正确保存到内存")
        else:
            print("✗ Schema info 未能保存到内存")
            return False
        
        # 步骤2: Domain Analysis
        print("\n=== 步骤2: Domain Analysis ===")
        domain_tool = DomainAnalysisTool()
        domain_tool.set_memory_reference(memory)
        
        try:
            domain_result = domain_tool._run()
            
            if isinstance(domain_result, str):
                domain_data = json.loads(domain_result)
            else:
                domain_data = domain_result
                
            print(f"✓ Domain analysis 完成")
            print(f"  主要领域: {domain_data.get('primary_domain', '未识别')}")
            print(f"  领域置信度: {domain_data.get('domain_confidence', 0.0)}")
            
            # 验证内存中的数据
            saved_domain = memory.get_analysis('domain_info')
            if saved_domain:
                print("✓ Domain info 已正确保存到内存")
            else:
                print("✗ Domain info 未能保存到内存")
                return False
            
        except Exception as e:
            print(f"✗ Domain analysis 失败: {e}")
            return False
        
        # 步骤3: Field Classification
        print("\n=== 步骤3: Field Classification ===")
        field_tool = FieldClassificationTool()
        field_tool.set_memory_reference(memory)
        
        try:
            field_result = field_tool._run()
            
            if isinstance(field_result, str):
                field_data = json.loads(field_result)
            else:
                field_data = field_result
                
            print(f"✓ Field classification 完成")
            
            # 验证内存中的数据
            saved_field = memory.get_analysis('field_classification')
            if saved_field:
                print("✓ Field classification 已正确保存到内存")
            else:
                print("✗ Field classification 未能保存到内存")
                return False
            
        except Exception as e:
            print(f"✗ Field classification 失败: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # 步骤4: Column Meaning Analysis
        print("\n=== 步骤4: Column Meaning Analysis ===")
        column_tool = ColumnMeaningTool()
        column_tool.set_memory_reference(memory)
        
        try:
            column_result = column_tool._run()
            
            if isinstance(column_result, str):
                column_data = json.loads(column_result)
            else:
                column_data = column_result
                
            print(f"✓ Column meaning analysis 完成")
            
            # 验证内存中的数据
            saved_column = memory.get_analysis('column_meanings')
            if saved_column:
                print("✓ Column meanings 已正确保存到内存")
            else:
                print("✗ Column meanings 未能保存到内存")
                return False
            
        except Exception as e:
            print(f"✗ Column meaning analysis 失败: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # 最终验证
        print("\n=== 最终验证 ===")
        print(f"内存中的分析结果: {list(memory.memories.keys())}")
        
        required_analyses = ['schema_info', 'domain_info', 'field_classification', 'column_meanings']
        missing = [analysis for analysis in required_analyses if analysis not in memory.memories]
        
        if missing:
            print(f"✗ 缺少分析结果: {missing}")
            return False
        else:
            print("✓ 所有分析工具都正常工作并保存了数据到内存")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_all_analysis_tools()
    if success:
        print("\n🎉 所有分析工具测试通过！")
    else:
        print("\n❌ 测试失败，请检查错误信息")