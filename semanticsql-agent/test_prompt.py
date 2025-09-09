#!/usr/bin/env python3
"""
测试提示词管理器
"""

from prompts.manager import PromptManager

def test_prompt_manager():
    """测试提示词管理器"""
    pm = PromptManager()
    
    print("📂 测试模板文件存在性...")
    try:
        # 测试获取系统提示词
        system_prompt = pm.get_system_prompt("semantic_sql_agent")
        print(f"✅ 系统提示词内容长度: {len(system_prompt)}")
        print(f"内容预览: {system_prompt[:200]}...")
        
        # 测试创建模板
        template = pm.create_agent_prompt_template("semantic_sql_agent")
        print(f"✅ 模板创建成功")
        print(f"输入变量: {template.input_variables}")
        print(f"模板内容长度: {len(template.template)}")
        
        return True
        
    except Exception as e:
        print(f"❌ 提示词管理器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_prompt_manager()