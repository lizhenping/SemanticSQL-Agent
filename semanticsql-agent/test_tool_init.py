#!/usr/bin/env python3
"""
测试工具初始化
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.database import DatabaseManager, DatabaseType
from tools.analysis_tools import SchemaExtractionTool

# 创建数据库管理器
db_config = {
    "type": DatabaseType.MYSQL,
    "host": "192.168.200.216",
    "port": 13306,
    "database": "testdb",
    "user": "root",
    "password": "Zijin@2024"
}

try:
    print("创建数据库管理器...")
    db_manager = DatabaseManager(db_config)
    
    print("初始化SchemaExtractionTool...")
    tool = SchemaExtractionTool(db_manager=db_manager)
    
    print(f"工具名称: {tool.name}")
    print(f"工具描述: {tool.description}")
    print("初始化成功!")
    
except Exception as e:
    print(f"错误: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()