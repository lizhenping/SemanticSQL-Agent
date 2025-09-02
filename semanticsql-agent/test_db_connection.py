#!/usr/bin/env python3
"""
测试数据库连接
"""

from config.database import DatabaseConfig
from utils.database import DatabaseManager

def test_database_connection():
    """测试数据库连接"""
    try:
        # 创建数据库配置
        config = DatabaseConfig(
            host='192.168.200.216',
            port=13306,
            database='testdb',
            username='testuser',
            password='testpass'
        )
        
        print(f"尝试连接数据库: {config.host}:{config.port}/{config.database}")
        
        # 创建数据库管理器
        db = DatabaseManager(config)
        
        # 初始化连接
        print("正在初始化数据库连接...")
        result = db.initialize()
        
        if result:
            print("✓ 数据库连接成功！")
            
            # 获取表列表
            print("正在获取表列表...")
            tables = db.get_tables()
            print(f"找到 {len(tables)} 个表: {tables}")
            
            # 测试一个简单查询
            if tables:
                table_name = tables[0]
                print(f"\n正在获取表 '{table_name}' 的信息...")
                table_info = db.get_table_info(table_name)
                print(f"表 '{table_name}' 有 {len(table_info.get('columns', []))} 个字段")
            
            db.close()
            print("\n数据库连接已关闭")
            return True
        else:
            print("✗ 数据库连接失败")
            return False
            
    except Exception as e:
        print(f"✗ 连接测试出错: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_database_connection()