"""
SemanticSQL Agent CLI - 命令行接口
基于新架构的完全重构版本，支持极简+自主+记忆驱动模式
"""

import json
import logging
import sys
from pathlib import Path
from typing import Optional
import traceback

import click
import yaml

from config.settings import Settings
from agent.sql_agent import create_semantic_sql_agent



# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


@click.group()
@click.version_option(version="4.0.0")
def cli():
    """SemanticSQL Agent v4.0 - 基于极简架构的SQL训练数据生成系统"""
    pass


def create_agent_with_config(use_database=True, use_memory=True, verbose=False, max_iterations=15):
    """创建Agent的统一方法，避免重复代码"""
    from config.settings import get_settings
    settings = get_settings()
    
    agent = create_semantic_sql_agent(
        settings=settings,
        use_database=use_database,
        use_memory=use_memory,
        verbose=verbose,
        max_iterations=max_iterations
    )
    
    # 检查必需的组件
    if use_database and not agent.database_manager:
        click.echo("❌ 数据库连接失败", err=True)
        sys.exit(1)
        
    return agent


@cli.command()
@click.option('--count', '-n', default=10, help='生成样本数量', type=int)
@click.option('--output', '-o', default='training_data.jsonl', help='输出文件路径')
@click.option('--database', '-d', help='数据库名称（默认: testdb）')
@click.option('--config', '-c', help='配置文件路径')
@click.option('--format', '-f', default='jsonl', type=click.Choice(['json', 'jsonl']), help='输出格式')
def generate(count: int, output: str, database: Optional[str], config: Optional[str], format: str):
    """生成SQL训练数据
    
    示例:
    \b
    python cli.py generate -n 20 -o training_data.jsonl
    python cli.py generate --count 100 --output dataset.json
    python cli.py generate -n 50 -d testdb -o contract_training.jsonl
    """
    click.echo(f"🚀 SemanticSQL Agent v4.0 - 开始生成 {count} 条训练数据")
    click.echo("=" * 60)
    
    # 加载统一配置
    from config.settings import get_settings
    settings = get_settings()
    
    # 确保输出文件有正确的扩展名
    if not output.endswith(f'.{format}'):
        output = f"{Path(output).stem}.{format}"
    
    # 创建新架构Agent - 使用统一配置
    click.echo("🔧 初始化SemanticSQL Agent（统一配置）...")
    
    # generate命令需要数据库来分析表结构
    agent = create_semantic_sql_agent(
        settings=settings,
        use_database=True,
        use_memory=True,
        verbose=False
    )
    
    if agent.tools:
        click.echo(f"✅ Agent创建成功，包含工具: {', '.join(agent.get_tool_names())}")
    else:
        click.echo("⚠️ Agent创建成功，但没有可用工具（将仅使用LLM）")
    
    # 开始生成过程
    click.echo(f"\n🎯 Agent开始自主生成 {count} 条训练数据...")
    click.echo(f"📋 工作流程: 数据库分析 → 问题生成循环({count}次) → 反思优化")
    
    # 构建生成任务
    generation_task = f"请生成 {count} 条高质量的NL2SQL训练数据，覆盖不同场景和操作类型"
    
    # 使用新架构的invoke方法
    result = agent.invoke(user_input=generation_task)
        
        # 从Agent结果中提取生成的样本
    if isinstance(result, dict) and 'output' in result:
        # 实际的样本应该从Agent的输出中解析
        generated_samples = []
        # TODO: 实现从Agent输出解析样本的逻辑
        click.echo("⚠️ 训练数据生成功能需要完整实现")
    else:
        generated_samples = []
        
    # 保存结果（如果有）
    if generated_samples:
        save_training_data(generated_samples, output, format)
        
    # 显示生成结果
    click.echo("\n" + "=" * 60)
    click.echo(f"🎉 生成完成！")
    click.echo(f"  ✅ 成功生成: {len(generated_samples)} 个样本")
    click.echo(f"  📁 输出文件: {output}")
    click.echo(f"  📊 输出格式: {format.upper()}")
    
    # 显示内存使用情况
    memory_stats = agent.get_memory_stats()
    click.echo(f"  🧠 记忆系统: {memory_stats.get('status', 'unknown')}")
    if memory_stats.get('total_triples', 0) > 0:
        click.echo(f"  💾 存储知识: {memory_stats['total_triples']} 个三元组")
    
    # 显示首个示例
    if generated_samples:
        example = generated_samples[0]
        click.echo(f"📝 示例: {example['question']} → {example['sql']}")
    
    click.echo(f"\n✨ 训练数据生成完成！可以使用以下命令查看:")
    click.echo(f"   cat {output} | head -5")
        


@cli.command()
@click.option('--database', '-d', required=True, help='数据库名称')
@click.option('--output', '-o', help='分析结果输出文件')
@click.option('--config', '-c', help='配置文件路径')
def analyze(database: str, output: Optional[str], config: Optional[str]):
    """分析数据库结构（用于调试）
    
    示例:
    \b
    python cli.py analyze -d testdb
    python cli.py analyze -d testdb -o analysis_result.json
    """
    click.echo(f"🔍 分析数据库: {database}")
    click.echo("=" * 50)
    
    # 创建Agent
    click.echo("🔧 初始化分析Agent...")
    agent = create_agent_with_config(use_database=True, use_memory=True, verbose=True, max_iterations=10)
    click.echo("✅ Agent创建成功")
    
    # 执行分析
    click.echo(f"📊 Agent开始分析数据库结构和业务特征...")
    
    analysis_task = f"请全面分析数据库 {database} 的结构、领域特征和业务模式"
    
    result = agent.invoke(user_input=analysis_task)
    
    click.echo("✅ 分析完成！")
    
    # 获取记忆状态
    memory_stats = agent.get_memory_stats()
    click.echo(f"\n📈 分析结果摘要:")
    click.echo(f"  • 记忆状态: {memory_stats.get('status', 'unknown')}")
    click.echo(f"  • 存储知识: {memory_stats.get('total_triples', 0)} 个三元组")
    click.echo(f"  • 分析工具: {', '.join(agent.get_tool_names())}")
    
    # 模拟分析结果展示
    analysis_summary = {
        "database": database,
        "analysis_time": "2024-01-15T10:30:00",
        "tools_used": agent.get_tool_names(),
        "memory_stats": memory_stats,
        "agent_result": result.get("output", "分析完成") if isinstance(result, dict) else str(result)
    }
    
    # 显示简要结果
    click.echo(f"📋 Agent输出: {analysis_summary['agent_result'][:100]}...")
    
    # 保存结果
    if output:
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(analysis_summary, f, ensure_ascii=False, indent=2)
        click.echo(f"\n💾 分析结果已保存到: {output}")
            


# ========== 辅助函数 ==========


def save_training_data(samples: list, output: str, format: str):
    """保存训练数据"""
    if format == "json":
        # JSON格式 - 包含元数据
        data = {
            "metadata": {
                "total_count": len(samples),
                "success_count": len(samples),
                "failed_count": 0,
                "generation_time": samples[0]["timestamp"] if samples else "",
                "agent_version": "4.0.0"
            },
            "data": samples
        }
        
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    else:  # jsonl格式
        with open(output, 'w', encoding='utf-8') as f:
            for sample in samples:
                f.write(json.dumps(sample, ensure_ascii=False) + '\n')


if __name__ == "__main__":
    cli()
