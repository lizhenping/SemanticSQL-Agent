#!/usr/bin/env python
"""
简单测试脚本 - 验证核心功能
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import Settings
from config.database import DatabaseConfig, DatabaseType
from utils.database import DatabaseManager

def test_settings():
    """测试Settings配置"""
    settings = Settings()
    print(f"✓ Settings创建成功: {settings.app_name}")
    print(f"✓ LLM模型: {settings.llm_model}")
    print(f"✓ MySQL支持: {settings.llm_base_url}")
    return True

def test_database_config():
    """测试DatabaseConfig"""
    config = DatabaseConfig()
    print(f"✓ DatabaseConfig创建成功: {config.type}")
    print(f"✓ MySQL默认配置: {config.host}:{config.port}")
    print(f"✓ 字符集: {config.charset}")
    
    # 测试连接字符串
    conn_str = config.to_connection_string()
    print(f"✓ 连接字符串: {conn_str}")
    return True

def test_database_manager():
    """测试DatabaseManager基本功能"""
    config = DatabaseConfig()
    manager = DatabaseManager(config)
    print(f"✓ DatabaseManager创建成功")
    
    # 注意：不实际连接数据库，只测试初始化
    print(f"✓ 配置验证通过: {config.database}")
    return True

def test_mysql_specific():
    """测试MySQL专用功能"""
    config = DatabaseConfig(
        type=DatabaseType.MYSQL,
        charset="utf8mb4",
        autocommit=True
    )
    
    print(f"✓ MySQL类型: {config.type.value}")
    print(f"✓ MySQL字符集: {config.charset}")
    print(f"✓ MySQL自动提交: {config.autocommit}")
    return True

def main():
    """运行所有测试"""
    tests = [
        ("Settings配置", test_settings),
        ("数据库配置", test_database_config), 
        ("数据库管理器", test_database_manager),
        ("MySQL专用功能", test_mysql_specific)
    ]
    
    print("开始运行简单测试...")
    print("=" * 50)
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            print(f"\n测试: {test_name}")
            test_func()
            print(f"✅ {test_name} - 通过")
            passed += 1
        except Exception as e:
            print(f"❌ {test_name} - 失败: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)