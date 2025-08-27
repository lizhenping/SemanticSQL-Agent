"""SemanticSQL Agent 命令行接口"""

import click
import yaml
import logging
from pathlib import Path
from datetime import datetime
import sys

from agent import SemanticSQLAgent
from utils.trajectory import TrajectoryAnalyzer

# 配置日志
def setup_logging(level: str = "INFO"):
    """设置日志配置"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


@click.group()
@click.option('--log-level', '-l', default='INFO', help='日志级别')
def cli(log_level: str):
    """SemanticSQL Agent - 自然语言到 SQL 查询工具"""
    setup_logging(log_level)


@cli.command()
@click.option('--config', '-c', type=click.Path(exists=True), help='配置文件路径')
@click.option('--query', '-q', help='直接执行查询')
@click.option('--save-trajectory', '-s', help='保存轨迹到文件')
def query(config: str, query: str, save_trajectory: str):
    """执行 SQL 查询"""
    # 加载配置
    config_data = None
    if config:
        with open(config, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
    
    # 创建智能体
    try:
        agent = SemanticSQLAgent(config_data)
    except Exception as e:
        click.echo(click.style(f"初始化失败: {e}", fg='red'))
        return
    
    if query:
        # 单次查询模式
        _execute_single_query(agent, query, save_trajectory)
    else:
        # 交互模式
        _interactive_mode(agent, save_trajectory)


def _execute_single_query(agent: SemanticSQLAgent, query_text: str, save_trajectory: str):
    """执行单个查询"""
    click.echo(f"\n查询: {query_text}")
    click.echo("-" * 60)
    
    try:
        result = agent.query(query_text)
        
        if result.success:
            # 显示 SQL
            if result.sql:
                click.echo("\n生成的 SQL:")
                click.echo(click.style(result.sql, fg='green'))
            
            # 显示结果
            click.echo(f"\n结果:")
            click.echo(result.answer)
            
            # 显示执行信息
            if result.execution_result:
                exec_result = result.execution_result
                click.echo(f"\n执行信息:")
                click.echo(f"  返回行数: {exec_result.get('row_count', 'N/A')}")
                if 'execution_time' in exec_result:
                    click.echo(f"  执行时间: {exec_result['execution_time']:.3f} 秒")
            
            click.echo(f"\n执行步骤数: {result.steps}")
        else:
            click.echo(click.style(f"\n错误: {result.error}", fg='red'))
        
        # 保存轨迹
        if save_trajectory:
            agent.trajectory_callback.save_trajectory(save_trajectory)
            click.echo(f"\n轨迹已保存到: {save_trajectory}")
            
    except Exception as e:
        click.echo(click.style(f"\n执行失败: {e}", fg='red'))


def _interactive_mode(agent: SemanticSQLAgent, save_trajectory_prefix: str):
    """交互模式"""
    click.echo("\n" + "="*60)
    click.echo("SemanticSQL Agent 交互模式")
    click.echo("="*60)
    click.echo("\n命令:")
    click.echo("  /help    - 显示帮助")
    click.echo("  /tables  - 显示所有表")
    click.echo("  /schema <table> - 显示表结构")
    click.echo("  /history - 显示查询历史")
    click.echo("  /exit    - 退出")
    click.echo("\n直接输入自然语言查询，例如: 查询所有用户信息")
    click.echo("-"*60 + "\n")
    
    history = []
    
    while True:
        try:
            # 获取用户输入
            user_input = click.prompt('SQL', type=str)
            
            # 处理命令
            if user_input.startswith('/'):
                if not _handle_command(agent, user_input, history):
                    break
                continue
            
            # 检查退出
            if user_input.lower() in ['exit', 'quit', 'q']:
                break
            
            # 执行查询
            start_time = datetime.now()
            result = agent.query(user_input)
            
            # 记录历史
            history.append({
                "time": start_time.isoformat(),
                "query": user_input,
                "success": result.success,
                "sql": result.sql if result.success else None
            })
            
            # 显示结果
            if result.success:
                if result.sql:
                    click.echo("\n生成的 SQL:")
                    click.echo(click.style(result.sql, fg='green'))
                
                click.echo(f"\n结果:")
                # 限制输出长度
                answer = result.answer
                if len(answer) > 1000:
                    answer = answer[:1000] + "\n... (输出已截断)"
                click.echo(answer)
                
                if result.execution_result:
                    click.echo(f"\n返回 {result.execution_result.get('row_count', 0)} 行")
            else:
                click.echo(click.style(f"\n错误: {result.error}", fg='red'))
            
            # 保存轨迹（如果指定）
            if save_trajectory_prefix:
                trajectory_file = f"{save_trajectory_prefix}_{len(history)}.json"
                agent.trajectory_callback.save_trajectory(trajectory_file)
            
            click.echo("\n" + "-"*60 + "\n")
            
        except KeyboardInterrupt:
            click.echo("\n使用 /exit 退出")
            continue
        except Exception as e:
            click.echo(click.style(f"\n发生错误: {e}", fg='red'))
            continue
    
    click.echo("\n再见!")


def _handle_command(agent: SemanticSQLAgent, command: str, history: list) -> bool:
    """处理特殊命令
    
    Returns:
        是否继续运行
    """
    parts = command.split()
    cmd = parts[0].lower()
    
    if cmd == '/help':
        click.echo("\n可用命令:")
        click.echo("  /tables - 显示所有表")
        click.echo("  /schema <table> - 显示表结构")
        click.echo("  /history - 显示查询历史")
        click.echo("  /exit - 退出")
        click.echo()
    
    elif cmd == '/tables':
        tables = agent.get_tables()
        click.echo(f"\n数据库包含 {len(tables)} 个表:")
        for i, table in enumerate(tables, 1):
            click.echo(f"  {i}. {table}")
            if i >= 20:
                click.echo(f"  ... 还有 {len(tables) - 20} 个表")
                break
        click.echo()
    
    elif cmd == '/schema' and len(parts) > 1:
        table_name = parts[1]
        try:
            schema = agent.get_table_info(table_name)
            click.echo(f"\n表 {table_name} 的结构:")
            click.echo(schema)
            click.echo()
        except Exception as e:
            click.echo(click.style(f"获取表结构失败: {e}", fg='red'))
    
    elif cmd == '/history':
        if not history:
            click.echo("\n暂无查询历史\n")
        else:
            click.echo(f"\n查询历史 (共 {len(history)} 条):")
            for i, h in enumerate(history[-10:], 1):  # 只显示最近10条
                status = "✓" if h['success'] else "✗"
                click.echo(f"{status} [{h['time']}] {h['query'][:50]}...")
            click.echo()
    
    elif cmd == '/exit':
        return False
    
    else:
        click.echo(click.style(f"未知命令: {cmd}", fg='yellow'))
        click.echo("使用 /help 查看帮助\n")
    
    return True


@cli.command()
@click.argument('trajectory_file', type=click.Path(exists=True))
@click.option('--export', '-e', help='导出时间线到文件')
def analyze(trajectory_file: str, export: str):
    """分析执行轨迹"""
    try:
        analyzer = TrajectoryAnalyzer.from_file(trajectory_file)
        
        # 打印摘要
        analyzer.print_summary()
        
        # 导出时间线
        if export:
            analyzer.export_timeline(export)
            
    except Exception as e:
        click.echo(click.style(f"分析失败: {e}", fg='red'))


@cli.command()
def version():
    """显示版本信息"""
    from semanticsql_agent import __version__
    click.echo(f"SemanticSQL Agent v{__version__}")


if __name__ == '__main__':
    cli()