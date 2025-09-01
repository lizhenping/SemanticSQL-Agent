#!/usr/bin/env python3
"""
调试脚本：分析智能体流程问题
"""

import logging
import json
import os
from datetime import datetime

# 设置详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 导入必要的模块
from config.settings import Settings
from config.database import DatabaseConfig
from agent.data_generation_agent import DataGenerationAgent
from tools.generation_tools.scenario_tool import ScenarioTool
from tools.generation_tools.question_generation_tool import QuestionGenerationTool

def test_tools_individually():
    """单独测试工具，确保它们正常工作"""
    print("\n=== 测试工具独立功能 ===\n")
    
    # 测试 ScenarioTool
    print("1. 测试 ScenarioTool:")
    scenario_tool = ScenarioTool()
    result = scenario_tool._run({"iteration": 0})
    print(f"   结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
    
    # 测试 QuestionGenerationTool
    print("\n2. 测试 QuestionGenerationTool:")
    settings = Settings()
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        openai_api_base=settings.llm_base_url,
        openai_api_key=settings.llm_api_key
    )
    
    question_tool = QuestionGenerationTool(llm=llm)
    question_result = question_tool._run({
        "scenario_id": "scenario_0_test",
        "operations": ["SELECT", "GROUP"],
        "business_purpose": "统计销售数据"
    })
    print(f"   结果: {json.dumps(question_result, ensure_ascii=False, indent=2)}")

def analyze_agent_execution():
    """分析智能体执行流程"""
    print("\n=== 分析智能体执行流程 ===\n")
    
    # 查看最近的轨迹文件
    trajectory_dir = "trajectories"
    if os.path.exists(trajectory_dir):
        files = sorted([f for f in os.listdir(trajectory_dir) if f.endswith('.json')])
        if files:
            latest_file = os.path.join(trajectory_dir, files[-1])
            print(f"分析最新轨迹文件: {latest_file}")
            
            with open(latest_file, 'r', encoding='utf-8') as f:
                trajectory = json.load(f)
            
            print("\n执行步骤分析:")
            for i, step in enumerate(trajectory.get('steps', [])):
                print(f"\n步骤 {i+1}:")
                print(f"  类型: {step.get('step_type')}")
                print(f"  工具: {step.get('tool_name')}")
                print(f"  内容: {step.get('content')}")
                if step.get('tool_output'):
                    print(f"  输出: {step.get('tool_output')[:200]}...")

def create_minimal_test():
    """创建最小化测试用例"""
    print("\n=== 创建最小化测试 ===\n")
    
    settings = Settings()
    db_config = DatabaseConfig()
    
    # 创建智能体
    agent = DataGenerationAgent(settings, db_config)
    
    # 打印工具列表
    print("已加载的工具:")
    for tool in agent.tools:
        print(f"  - {tool.name}: {tool.description}")
    
    # 创建简单任务
    simple_task = """
    请执行以下步骤：
    1. 使用 scenario_tool 选择一个场景（iteration=0）
    2. 使用 operation_selection 选择操作
    3. 停止并报告结果
    """
    
    print(f"\n执行任务: {simple_task}")
    
    try:
        result = agent.run(simple_task)
        print(f"\n执行结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"\n执行错误: {e}")
        import traceback
        traceback.print_exc()

def check_prompt_format():
    """检查提示词格式"""
    print("\n=== 检查提示词格式 ===\n")
    
    from prompts.manager import PromptManager
    prompt_manager = PromptManager()
    
    # 创建示例工具名称
    tool_names = ["scenario_tool", "operation_selection", "question_generation"]
    
    # 生成提示词
    prompt = prompt_manager.create_agent_prompt(
        tool_names=", ".join(tool_names),
        tools="- scenario_tool: 选择场景\n- operation_selection: 选择操作\n- question_generation: 生成问题"
    )
    
    print("生成的提示词:")
    print(prompt.format(
        input="测试任务",
        agent_scratchpad=""
    ))

if __name__ == "__main__":
    print("=" * 60)
    print("智能体流程调试分析")
    print("=" * 60)
    
    # 1. 测试工具
    test_tools_individually()
    
    # 2. 分析执行轨迹
    analyze_agent_execution()
    
    # 3. 检查提示词
    check_prompt_format()
    
    # 4. 最小化测试
    create_minimal_test()