#!/usr/bin/env python3
"""
测试新设计的代码修改
验证Agent完全自主模式是否正常工作
"""

import sys
import logging
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

# 设置日志
logging.basicConfig(level=logging.INFO)

def test_imports():
    """测试所有重要的导入"""
    print("🧪 测试导入...")
    
    try:
        # 测试工具导入
        from tools.generation_tools.scenario_operation_tool import ScenarioOperationTool
        print("✅ ScenarioOperationTool 导入成功")
        
        from tools.analysis_tools.field_analysis_tool import FieldAnalysisTool
        print("✅ FieldAnalysisTool 导入成功")
        
        from tools.analysis_tools.column_analysis_tool import ColumnAnalysisTool
        print("✅ ColumnAnalysisTool 导入成功")
        
        from tools.analysis_tools.table_analysis_tool import TableAnalysisTool
        print("✅ TableAnalysisTool 导入成功")
        
        # 测试记忆管理
        from utils.memory import DatabaseAnalysisMemory
        print("✅ DatabaseAnalysisMemory 导入成功")
        
        print("✅ 所有导入测试通过！")
        return True
        
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        return False

def test_scenario_operation_tool():
    """测试ScenarioOperationTool的基本功能"""
    print("\n🧪 测试ScenarioOperationTool...")
    
    try:
        from tools.generation_tools.scenario_operation_tool import ScenarioOperationTool
        
        tool = ScenarioOperationTool()
        
        # 测试获取所有组合
        result = tool._run(mode="get_all_combinations")
        
        if result.get("success"):
            combinations = result.get("combinations", [])
            print(f"✅ 成功生成 {len(combinations)} 个场景组合")
            
            if combinations:
                first_combo = combinations[0]
                print(f"✅ 第一个组合: {first_combo.get('combination_id')}")
                print(f"   场景: {first_combo.get('scenario', {}).get('main_name')}")
                print(f"   操作: {first_combo.get('operations')}")
                print(f"   有专用提示词: {'generated_prompt' in first_combo}")
        else:
            print(f"❌ 生成失败: {result.get('error')}")
            return False
            
        print("✅ ScenarioOperationTool 测试通过！")
        return True
        
    except Exception as e:
        print(f"❌ ScenarioOperationTool 测试失败: {e}")
        return False

def test_memory_system():
    """测试记忆系统的映射"""
    print("\n🧪 测试记忆系统...")
    
    try:
        from utils.memory import DatabaseAnalysisMemory
        
        memory = DatabaseAnalysisMemory()
        
        # 模拟工具调用
        test_inputs = {"tool_name": "scenario_operation_generation"}
        test_outputs = {"output": {"total_combinations": 5, "combinations": []}}
        
        memory.save_context(test_inputs, test_outputs)
        
        # 检查是否正确保存
        loaded = memory.load_memory_variables({})
        db_analysis = loaded.get("db_analysis", {})
        
        if "all_scenario_combinations" in db_analysis:
            print("✅ 场景组合正确保存到记忆")
            print(f"   记忆键: all_scenario_combinations")
            print(f"   数据: {db_analysis['all_scenario_combinations']}")
        else:
            print("❌ 场景组合未正确保存")
            return False
            
        print("✅ 记忆系统测试通过！")
        return True
        
    except Exception as e:
        print(f"❌ 记忆系统测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 开始测试新设计的代码修改...")
    print("=" * 50)
    
    all_passed = True
    
    # 测试导入
    if not test_imports():
        all_passed = False
    
    # 测试ScenarioOperationTool
    if not test_scenario_operation_tool():
        all_passed = False
    
    # 测试记忆系统
    if not test_memory_system():
        all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 所有测试通过！代码修改成功符合新设计。")
    else:
        print("❌ 部分测试失败，需要进一步检查。")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)