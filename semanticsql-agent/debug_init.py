"""调试初始化问题"""

# 最小化测试
try:
    print("1. 测试基础导入...")
    from tools.analysis_tools.schema_extraction_tool import SchemaExtractionTool
    print("   导入成功")
    
    print("\n2. 测试创建工具（不带参数）...")
    try:
        tool = SchemaExtractionTool()
        print("   错误：应该失败但成功了")
    except Exception as e:
        print(f"   预期的错误: {type(e).__name__}: {e}")
    
    print("\n3. 测试创建工具（带db_manager=None）...")
    try:
        tool = SchemaExtractionTool(db_manager=None)
        print("   成功创建")
        print(f"   工具名: {tool.name}")
    except Exception as e:
        print(f"   错误: {type(e).__name__}: {e}")
        
    print("\n4. 测试创建模拟db_manager...")
    class MockDBManager:
        pass
    
    mock_db = MockDBManager()
    
    print("\n5. 测试创建工具（带模拟db_manager）...")
    try:
        tool = SchemaExtractionTool(db_manager=mock_db)
        print("   成功创建")
        print(f"   工具名: {tool.name}")
        print(f"   db_manager设置: {hasattr(tool, 'db_manager')}")
    except Exception as e:
        print(f"   错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        
except Exception as e:
    print(f"\n总体错误: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()