"""测试导入是否正常"""

import sys
from pathlib import Path

# 添加项目路径到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_imports():
    """测试所有模块是否可以正常导入"""
    print("测试模块导入...")
    
    modules = [
        "config",
        "config.settings",
        "config.database",
        "models",
        "models.schemas",
        "tools",
        "tools.base",
        "tools.analysis_tools",
        "tools.generation_tools", 
        "tools.validation_tools",
        "tools.thinking_tools",
        "prompts",
        "prompts.manager",
        "agent",
        "agent.sql_agent",
        "agent.callbacks",
        "utils",
        "utils.database",
        "utils.trajectory"
    ]
    
    success = True
    for module_name in modules:
        try:
            __import__(module_name)
            print(f"✓ {module_name}")
        except ImportError as e:
            print(f"✗ {module_name}: {e}")
            success = False
        except Exception as e:
            print(f"✗ {module_name}: {type(e).__name__}: {e}")
            success = False
    
    if success:
        print("\n✅ 所有模块导入成功！")
    else:
        print("\n❌ 部分模块导入失败")
    
    return success

if __name__ == "__main__":
    test_imports()