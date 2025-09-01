#!/usr/bin/env python3
"""
测试修复后的智能体流程
"""

import logging
import json
import sys
from datetime import datetime

# 设置日志级别
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_single_sample_generation():
    """测试生成单个样本的流程"""
    print("\n" + "="*60)
    print("测试修复后的智能体流程")
    print("="*60 + "\n")
    
    try:
        from config.settings import Settings
        from config.database import DatabaseConfig
        from agent.data_generation_agent import DataGenerationAgent
        
        # 初始化配置
        settings = Settings()
        db_config = DatabaseConfig()
        
        # 创建智能体
        print("初始化智能体...")
        agent = DataGenerationAgent(settings, db_config)
        
        # 先执行数据库分析
        print("\n执行数据库分析...")
        analysis_result = agent.analyze_database("testdb")
        if not analysis_result["success"]:
            print(f"数据库分析失败: {analysis_result}")
            return
        
        print("数据库分析完成!")
        
        # 生成1个训练样本进行测试
        print("\n开始生成训练数据（1个样本）...")
        print("注意观察是否按照7个步骤顺序执行：")
        print("1. scenario_tool")
        print("2. operation_selection")
        print("3. question_generation")
        print("4. sql_generation")
        print("5. sql_validation")
        print("6. sql_execution")
        print("7. sql_reflection")
        print("\n" + "-"*60 + "\n")
        
        result = agent.generate_training_data(
            count=1,
            output_file="test_fix_output.jsonl"
        )
        
        print("\n" + "-"*60)
        print(f"\n生成结果:")
        print(f"  成功: {result.successful}")
        print(f"  失败: {result.failed}")
        print(f"  输出文件: {result.output_file}")
        
        if result.successful > 0 and result.examples:
            print(f"\n生成的样本示例:")
            example = result.examples[0]
            print(f"  问题: {example.get('question', 'N/A')}")
            print(f"  SQL: {example.get('sql', 'N/A')}")
            print(f"  场景: {example.get('scenario', {}).get('category', 'N/A')}")
        
        # 检查轨迹文件
        import os
        trajectory_dir = "trajectories"
        if os.path.exists(trajectory_dir):
            files = sorted([f for f in os.listdir(trajectory_dir) if f.endswith('.json')])
            if files:
                latest_file = os.path.join(trajectory_dir, files[-1])
                print(f"\n轨迹文件: {latest_file}")
                
                with open(latest_file, 'r', encoding='utf-8') as f:
                    trajectory = json.load(f)
                
                # 统计工具调用
                tool_calls = {}
                for step in trajectory.get('steps', []):
                    tool_name = step.get('tool_name')
                    if tool_name:
                        tool_calls[tool_name] = tool_calls.get(tool_name, 0) + 1
                
                print("\n工具调用统计:")
                for tool, count in tool_calls.items():
                    print(f"  {tool}: {count}次")
                
                # 检查是否执行了所有必要的步骤
                required_tools = [
                    'scenario_tool', 'operation_selection', 'question_generation',
                    'sql_generation', 'sql_validation', 'sql_execution', 'sql_reflection'
                ]
                
                missing_tools = [tool for tool in required_tools if tool not in tool_calls]
                if missing_tools:
                    print(f"\n⚠️  警告：以下工具未被调用: {', '.join(missing_tools)}")
                else:
                    print("\n✅ 所有必要的工具都已被调用!")
        
        return result.successful > 0
        
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_single_sample_generation()
    sys.exit(0 if success else 1)