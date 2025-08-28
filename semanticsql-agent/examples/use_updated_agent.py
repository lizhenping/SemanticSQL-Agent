"""更新后的 Agent 架构使用示例

展示如何使用参考 TRAEAgent 重新设计的架构。
"""

import asyncio
import logging
from pathlib import Path

from config import SQLAgentConfig, ModelConfig, DatabaseConfig
from agent import SQLAgent, AgentState, AgentStepState

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def basic_example():
    """基础使用示例 - 简单查询"""
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
        max_steps=5,
        auto_analyze=False,  # 简单查询不需要完整分析
        tools=["extract_database_schema", "generate_sql", "execute_sql"]
    )
    
    # 创建智能体
    agent = SQLAgent(config)
    
    # 创建任务
    agent.new_task("查询产品表中的总产品数")
    
    # 执行任务
    execution = await agent.execute_task()
    
    # 打印结果
    print(f"任务: {execution.task}")
    print(f"状态: {execution.agent_state.value}")
    print(f"成功: {execution.success}")
    print(f"步骤数: {execution.total_steps}")
    
    if execution.total_tokens:
        print(f"\nToken 使用:")
        print(f"  输入: {execution.total_tokens.input_tokens}")
        print(f"  输出: {execution.total_tokens.output_tokens}")
        print(f"  总计: {execution.total_tokens.total_tokens}")
    
    if execution.final_result:
        print(f"\n最终结果:")
        print(execution.final_result)
    
    # 打印执行步骤
    print("\n执行步骤:")
    for step in execution.steps:
        print(f"\n步骤 {step.step_number}: {step.state.value}")
        if step.thought:
            print(f"  思考: {step.thought[:100]}...")
        if step.tool_calls:
            for tool_call in step.tool_calls:
                print(f"  工具调用: {tool_call.name}")
        if step.tool_results:
            for tool_result in step.tool_results:
                print(f"  工具结果: {tool_result.name} - {'成功' if tool_result.success else '失败'}")
        if step.reflection:
            print(f"  反思: {step.reflection}")


async def complex_example():
    """复杂查询示例 - 需要深度分析"""
    print("\n\n=== 复杂查询示例 ===\n")
    
    # 创建配置（启用所有工具）
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
        max_steps=15,
        auto_analyze=True,
        enable_reflection=True,
        tools=[
            "extract_database_schema",
            "analyze_business_domain",
            "classify_table_fields",
            "analyze_entity_relationships",
            "deep_thinking",
            "generate_sql",
            "validate_sql",
            "execute_sql"
        ]
    )
    
    # 创建智能体
    agent = SQLAgent(config)
    
    # 复杂查询
    complex_query = """
    分析最近3个月的销售数据，找出：
    1. 销售额环比增长最快的前5个产品类别
    2. 这些类别中的畅销产品TOP3
    3. 预测下个月的销售趋势
    """
    
    # 执行查询
    result = await agent.query(complex_query)
    
    print(f"查询: {result.question}")
    print(f"成功: {result.success}")
    print(f"步骤数: {result.steps}")
    
    if result.sql:
        print(f"\n生成的 SQL:")
        print(result.sql)
    
    if result.answer:
        print(f"\n查询结果:")
        print(result.answer)
    
    if hasattr(result, 'token_usage') and result.token_usage:
        print(f"\nToken 使用统计:")
        print(f"  输入: {result.token_usage['input_tokens']}")
        print(f"  输出: {result.token_usage['output_tokens']}")
        print(f"  总计: {result.token_usage['total_tokens']}")


async def batch_tool_example():
    """批量工具调用示例"""
    print("\n\n=== 批量工具调用示例 ===\n")
    
    config = SQLAgentConfig(
        model=ModelConfig(
            provider="openai",
            model="gpt-4"
        ),
        database=DatabaseConfig(
            connection_string="sqlite:///example.db"
        ),
        max_steps=10
    )
    
    agent = SQLAgent(config)
    
    # 一个需要多个工具同时执行的查询
    agent.new_task(
        "分析数据库结构并识别所有的时间序列数据表",
        tool_names=[
            "extract_database_schema",
            "analyze_business_domain",
            "classify_table_fields"
        ]
    )
    
    execution = await agent.execute_task()
    
    # 查找批量工具调用
    for step in execution.steps:
        if step.tool_calls and len(step.tool_calls) > 1:
            print(f"步骤 {step.step_number} - 批量调用 {len(step.tool_calls)} 个工具:")
            for tool_call in step.tool_calls:
                print(f"  - {tool_call.name}")
            
            # 显示并行执行的结果
            if step.tool_results:
                print(f"  并行执行结果:")
                for result in step.tool_results:
                    status = "成功" if result.success else f"失败: {result.error}"
                    print(f"    - {result.name}: {status} (耗时: {result.execution_time:.2f}s)")


async def trajectory_analysis():
    """轨迹分析示例"""
    print("\n\n=== 轨迹分析示例 ===\n")
    
    config = SQLAgentConfig(
        model=ModelConfig(provider="openai", model="gpt-3.5-turbo"),
        database=DatabaseConfig(connection_string="sqlite:///test.db"),
        trajectory_dir="./my_trajectories"
    )
    
    agent = SQLAgent(config)
    
    # 执行查询
    await agent.query("统计每个部门的平均工资")
    
    # 获取最新的轨迹文件
    from agent import TrajectoryRecorder
    trajectories = TrajectoryRecorder.list_trajectories("./my_trajectories")
    
    if trajectories:
        latest = trajectories[0]
        print(f"最新轨迹文件: {latest.name}")
        
        # 加载并分析轨迹
        recorder = TrajectoryRecorder()
        trajectory_data = recorder.load_trajectory(str(latest))
        
        print(f"\n轨迹分析:")
        print(f"  任务: {trajectory_data.get('task')}")
        print(f"  模型: {trajectory_data.get('provider')}/{trajectory_data.get('model')}")
        print(f"  总步骤: {len(trajectory_data.get('agent_steps', []))}")
        print(f"  执行时间: {trajectory_data.get('execution_time', 0):.2f}秒")
        
        # Token 统计
        if trajectory_data.get('total_tokens'):
            tokens = trajectory_data['total_tokens']
            print(f"\n  Token 使用:")
            print(f"    输入: {tokens.get('input_tokens', 0)}")
            print(f"    输出: {tokens.get('output_tokens', 0)}")
            print(f"    总计: {tokens.get('total_tokens', 0)}")
            
            # 估算成本（以 GPT-4 为例）
            input_cost = tokens.get('input_tokens', 0) * 0.03 / 1000
            output_cost = tokens.get('output_tokens', 0) * 0.06 / 1000
            total_cost = input_cost + output_cost
            print(f"    估算成本: ${total_cost:.4f}")
        
        # LLM 交互统计
        llm_interactions = trajectory_data.get('llm_interactions', [])
        if llm_interactions:
            print(f"\n  LLM 交互次数: {len(llm_interactions)}")
            
            # 分析工具使用
            tool_usage = {}
            for step in trajectory_data.get('agent_steps', []):
                if step.get('tool_calls'):
                    for tool_call in step['tool_calls']:
                        tool_name = tool_call.get('name', 'unknown')
                        tool_usage[tool_name] = tool_usage.get(tool_name, 0) + 1
            
            if tool_usage:
                print(f"\n  工具使用统计:")
                for tool, count in sorted(tool_usage.items(), key=lambda x: x[1], reverse=True):
                    print(f"    {tool}: {count}次")


async def main():
    """运行所有示例"""
    print("SemanticSQL Agent - 基于 TRAEAgent 设计的新架构\n")
    print("=" * 60 + "\n")
    
    examples = [
        ("基础示例", basic_example),
        ("复杂查询", complex_example),
        ("批量工具调用", batch_tool_example),
        ("轨迹分析", trajectory_analysis)
    ]
    
    for name, example_func in examples:
        try:
            await example_func()
        except Exception as e:
            print(f"\n{name}执行失败: {e}")
            logger.error(f"{name}失败", exc_info=True)
        
        print("\n" + "-" * 60)
    
    print("\n所有示例执行完成！")


if __name__ == "__main__":
    # 运行示例
    asyncio.run(main())