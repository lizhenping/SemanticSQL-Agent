#!/usr/bin/env python3
"""
测试Pydantic字段定义修复
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 测试基础工具
print("1. 测试基础工具初始化...")
try:
    from tools.analysis_tools.schema_extraction_tool import SchemaExtractionTool
    
    # 创建模拟的db_manager
    class MockDBManager:
        def initialize(self):
            return True
    
    db_manager = MockDBManager()
    
    # 创建工具
    tool = SchemaExtractionTool(db_manager=db_manager)
    print(f"   ✓ SchemaExtractionTool创建成功")
    print(f"     - name: {tool.name}")
    print(f"     - description: {tool.description}")
    print(f"     - db_manager set: {hasattr(tool, 'db_manager') and tool.db_manager is not None}")
    
except Exception as e:
    print(f"   ✗ 错误: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

# 测试LLM工具
print("\n2. 测试LLM工具初始化...")
try:
    from tools.analysis_tools.domain_analysis_tool import DomainAnalysisTool
    
    # 创建模拟的LLM
    class MockLLM:
        def invoke(self, *args, **kwargs):
            return None
    
    llm = MockLLM()
    
    # 创建工具
    tool = DomainAnalysisTool(llm=llm)
    print(f"   ✓ DomainAnalysisTool创建成功")
    print(f"     - name: {tool.name}")
    print(f"     - llm set: {hasattr(tool, 'llm') and tool.llm is not None}")
    print(f"     - prompt_manager set: {hasattr(tool, 'prompt_manager') and tool.prompt_manager is not None}")
    
except Exception as e:
    print(f"   ✗ 错误: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\n测试完成!")