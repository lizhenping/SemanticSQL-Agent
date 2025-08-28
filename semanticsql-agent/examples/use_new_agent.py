"""新架构的使用示例

展示如何使用重新设计的 SQL Agent。
"""

import asyncio
import logging
from pathlib import Path

from config import SQLAgentConfig, ModelConfig, DatabaseConfig
from agent import SQLAgent, SQLAgentExecutor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


async def basic_example():
    """基础使用示例"""
    print("=== 基础使用示例 ===\n")
    
    # 创建配置
    config = SQLAgentConfig(
        model=ModelConfig(
            provider="openai",
            model="gpt-4",
            temperature=0.1
        ),
        database=DatabaseConfig(
            dialect="mysql",
            host="localhost",
            port=3306,
            username="root",
            password="password",
            database="test_db"
        ),
        max_steps=10,
        auto_analyze=True
    )
    
    # 创建智能体
    agent = SQLAgent(config)
    
    # 执行简单查询
    result = await agent.query("查询用户表中的总用户数")
    
    print(f"查询: {result.question}")
    print(f"生成的 SQL: {result.sql}")
    print(f"答案: {result.answer}")
    print(f"执行步骤: {result.steps}")
    print()


async def complex_example():
    """复杂查询示例"""
    print("=== 复杂查询示例 ===\n")
    
    # 创建配置（启用所有分析工具）
    config = SQLAgentConfig(
        model=ModelConfig(
            provider="openai",
            model="gpt-4",
            temperature=0.1
        ),
        database=DatabaseConfig(
            dialect="mysql",
            connection_string="mysql://user:pass@localhost/ecommerce"
        ),
        tools=[
            "extract_database_schema",
            "analyze_business_domain",
            "classify_table_fields",
            "analyze_entity_relationships",
            "deep_thinking",
            "generate_sql",
            "validate_sql",
            "execute_sql"
        ],
        enable_reflection=True
    )
    
    # 创建智能体和执行器
    agent = SQLAgent(config)
    executor = SQLAgentExecutor(agent)
    
    # 复杂查询
    complex_query = """
    分析过去6个月的销售趋势，找出：
    1. 销售额增长最快的前5个产品类别
    2. 每个类别的月度销售额变化
    3. 识别可能的季节性模式
    """
    
    result = await executor.execute(complex_query)
    
    print(f"查询: {result.question}")
    print(f"成功: {result.success}")
    if result.sql:
        print(f"\n生成的 SQL:\n{result.sql}")
    if result.answer:
        print(f"\n分析结果:\n{result.answer}")
    print(f"\n总步骤数: {result.steps}")


async def trajectory_example():
    """轨迹记录示例"""
    print("=== 轨迹记录示例 ===\n")
    
    # 创建配置（指定轨迹目录）
    config = SQLAgentConfig(
        model=ModelConfig(provider="openai", model="gpt-3.5-turbo"),
        database=DatabaseConfig(connection_string="sqlite:///example.db"),
        trajectory_dir="./my_trajectories",
        verbose=True
    )
    
    # 创建智能体
    agent = SQLAgent(config)
    
    # 执行查询
    result = await agent.query("列出所有包含 'product' 的表")
    
    # 获取最新的轨迹
    recent_trajectories = agent.trajectory_recorder.get_recent_trajectories(1)
    
    if recent_trajectories:
        trajectory = recent_trajectories[0]
        print(f"轨迹文件: {trajectory['filename']}")
        print(f"任务: {trajectory['task']}")
        print(f"步骤数: {trajectory['total_steps']}")
        print(f"执行时间: {trajectory['execution_time']:.2f}秒")
        
        # 打印每个步骤
        print("\n执行步骤:")
        for step in trajectory['steps']:
            print(f"  步骤 {step['step_number']}: {step['state']}")
            if step['thought']:
                print(f"    思考: {step['thought'][:100]}...")
            if step['action']:
                print(f"    动作: {step['action']['tool']}")


def sync_example():
    """同步执行示例"""
    print("=== 同步执行示例 ===\n")
    
    # 创建配置
    config = SQLAgentConfig(
        model=ModelConfig(provider="openai", model="gpt-3.5-turbo"),
        database=DatabaseConfig(connection_string="sqlite:///example.db")
    )
    
    # 创建智能体和执行器
    agent = SQLAgent(config)
    executor = SQLAgentExecutor(agent)
    
    # 同步执行
    result = executor.execute_sync("数据库中有多少张表？")
    
    print(f"查询: {result.question}")
    print(f"结果: {result.answer}")


async def main():
    """运行所有示例"""
    print("SemanticSQL Agent 新架构示例\n")
    print("基于 TRAEAgent 的设计理念\n")
    print("-" * 50 + "\n")
    
    # 运行示例
    try:
        await basic_example()
    except Exception as e:
        print(f"基础示例失败: {e}\n")
    
    try:
        await complex_example()
    except Exception as e:
        print(f"复杂示例失败: {e}\n")
    
    try:
        await trajectory_example()
    except Exception as e:
        print(f"轨迹示例失败: {e}\n")
    
    try:
        sync_example()
    except Exception as e:
        print(f"同步示例失败: {e}\n")


if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(main())