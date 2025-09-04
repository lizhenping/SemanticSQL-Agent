#!/usr/bin/env python3
"""
测试prompt修复是否有效
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from prompts.manager import PromptManager
from langchain.prompts import ChatPromptTemplate

def test_prompt_creation():
    """测试prompt创建过程"""
    try:
        # 初始化PromptManager
        prompt_manager = PromptManager()
        
        # 模拟base_agent.py中的参数
        tool_descriptions = "- test_tool: A test tool for demonstration"
        tool_names = "test_tool"
        
        # 渲染系统提示词模板，包含iteration参数
        print(f"传入的参数:")
        print(f"  tools: {tool_descriptions}")
        print(f"  tool_names: {tool_names}")
        print(f"  database_name: test_db")
        print(f"  iteration: 0")
        
        system_prompt = prompt_manager.render_template(
            'system/main.j2',
            tools=tool_descriptions,
            tool_names=tool_names,
            database_name='test_db',
            count=1,
            memory_summary="初始状态",
            iteration=0  # 这是修复的关键
        )
        
        print("系统提示词渲染成功")
        print(f"系统提示词长度: {len(system_prompt)} 字符")
        
        # 检查渲染后的内容中是否包含问题变量
        if '{"iteration"}' in system_prompt:
            print("发现问题: 系统提示词中包含 {\"iteration\"}")
        if '{"database_name"}' in system_prompt:
            print("发现问题: 系统提示词中包含 {\"database_name\"}")
        if '{tool_names}' in system_prompt:
            print("发现问题: 系统提示词中包含 {tool_names}")
        if '{tools}' in system_prompt:
            print("发现问题: 系统提示词中包含 {tools}")
            
        # 查找Action Input行
        lines = system_prompt.split('\n')
        for i, line in enumerate(lines):
            if 'Action Input' in line:
                print(f"\n--- Action Input行 (第{i+1}行) ---")
                print(line)
                break
                
        # 输出部分内容用于调试
        print("\n--- 系统提示词片段 (前500字符) ---")
        print(system_prompt[:500])
        print("\n--- 系统提示词片段 (后500字符) ---")
        print(system_prompt[-500:])
        
        # 创建ChatPromptTemplate
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
            ("assistant", "{agent_scratchpad}")
        ])
        
        print("ChatPromptTemplate创建成功")
        print(f"输入变量: {prompt.input_variables}")
        
        # 检查是否还有意外的变量
        expected_vars = {'input', 'agent_scratchpad'}
        actual_vars = set(prompt.input_variables)
        unexpected_vars = actual_vars - expected_vars
        
        if unexpected_vars:
            print(f"警告: 发现意外的变量: {unexpected_vars}")
            return False
        else:
            print("✅ 修复成功! 没有发现意外的变量")
            return True
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_prompt_creation()
    sys.exit(0 if success else 1)