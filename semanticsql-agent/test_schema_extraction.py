#!/usr/bin/env python3
"""
测试schema_extraction工具
"""

from config.database import DatabaseConfig
from utils.database import DatabaseManager
from tools.analysis_tools.schema_extraction_tool import SchemaExtractionTool

def test_schema_extraction():
    """测试schema_extraction工具"""
    try:
        # 创建数据库配置
        config = DatabaseConfig(
            host='192.168.200.216',
            port=13306,
            database='testdb',
            username='testuser',
            password='testpass'
        )
        
        print(f"连接数据库: {config.host}:{config.port}/{config.database}")
        
        # 创建数据库管理器
        db = DatabaseManager(config)
        
        # 初始化连接
        if not db.initialize():
            print("✗ 数据库连接失败")
            return False
        
        print("✓ 数据库连接成功")
        
        # 创建schema_extraction工具
        schema_tool = SchemaExtractionTool(db_manager=db)
        
        print("\n正在执行schema_extraction...")
        
        # 执行工具
        result = schema_tool._run(
            database_name='testdb',
            include_views=False,
            include_indexes=True,
            sample_data=False,
            tables=None
        )
        
        # 解析JSON字符串为字典
        import json
        if isinstance(result, str):
            result = json.loads(result)
        
        print("\n=== Schema Extraction 结果 ===")
        print(f"数据库名: {result.get('database_name')}")
        print(f"表数量: {result.get('table_count')}")
        
        if 'tables' in result:
            print("\n表信息:")
            tables = result['tables']
            print(f"Tables 类型: {type(tables)}")
            if isinstance(tables, dict):
                for table_name, table_info in tables.items():
                    print(f"  - {table_name}: {len(table_info.get('columns', []))} 个字段")
            elif isinstance(tables, list):
                print(f"  Tables 是列表，包含 {len(tables)} 个元素")
                for i, table in enumerate(tables[:3]):  # 只显示前3个
                    print(f"  - 表 {i}: {table}")
        
        print("\n✓ Schema extraction 执行成功！")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"✗ Schema extraction 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_schema_extraction()