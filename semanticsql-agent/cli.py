"""SemanticSQL Agent 命令行接口"""

import json
import sys
from pathlib import Path
from typing import Optional

import click
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agent import SQLAgent
from .config import Config

console = Console()


def load_config(config_file: str) -> dict:
    """加载配置文件"""
    config_path = Path(config_file)
    
    if not config_path.exists():
        console.print(f"[red]错误: 配置文件不存在: {config_file}[/red]")
        sys.exit(1)
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            if config_file.endswith('.yaml') or config_file.endswith('.yml'):
                return yaml.safe_load(f)
            elif config_file.endswith('.json'):
                return json.load(f)
            else:
                console.print("[red]错误: 配置文件必须是 .yaml/.yml 或 .json 格式[/red]")
                sys.exit(1)
    except Exception as e:
        console.print(f"[red]错误: 加载配置文件失败: {e}[/red]")
        sys.exit(1)


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """SemanticSQL Agent - 基于 LangChain 的 NL2SQL 智能体"""
    pass


@cli.command()
@click.argument("query", required=False)
@click.option("--file", "-f", "file_path", help="包含查询的文件路径")
@click.option("--config", "-c", "config_file", default="config.yaml", help="配置文件路径")
@click.option("--model", "-m", help="使用的模型")
@click.option("--provider", "-p", help="LLM 提供商")
@click.option("--database", "-d", help="数据库连接字符串")
@click.option("--max-steps", type=int, help="最大执行步数")
@click.option("--save-trajectory", "-s", help="保存轨迹到文件")
@click.option("--verbose", "-v", is_flag=True, help="详细输出")
def run(
    query: Optional[str],
    file_path: Optional[str],
    config_file: str,
    model: Optional[str],
    provider: Optional[str],
    database: Optional[str],
    max_steps: Optional[int],
    save_trajectory: Optional[str],
    verbose: bool
):
    """执行自然语言查询"""
    
    # 获取查询内容
    if file_path:
        if query:
            console.print("[red]错误: 不能同时使用查询字符串和 --file 参数[/red]")
            sys.exit(1)
        try:
            query = Path(file_path).read_text(encoding='utf-8').strip()
        except FileNotFoundError:
            console.print(f"[red]错误: 文件不存在: {file_path}[/red]")
            sys.exit(1)
    elif not query:
        console.print("[red]错误: 必须提供查询字符串或使用 --file 参数[/red]")
        sys.exit(1)
    
    # 加载配置
    console.print("[cyan]加载配置...[/cyan]")
    config_data = load_config(config_file)
    
    # 命令行参数覆盖配置文件
    if model:
        config_data.setdefault('llm', {})['model'] = model
    if provider:
        config_data.setdefault('llm', {})['provider'] = provider
    if database:
        config_data['database']['connection_string'] = database
    if max_steps:
        config_data.setdefault('agent', {})['max_steps'] = max_steps
    
    # 创建配置对象
    try:
        config = Config(**config_data)
    except Exception as e:
        console.print(f"[red]错误: 配置无效: {e}[/red]")
        sys.exit(1)
    
    # 显示查询
    console.print("\n" + Panel(query, title="[bold cyan]查询[/bold cyan]", expand=False))
    
    # 创建并运行智能体
    try:
        console.print("\n[cyan]初始化智能体...[/cyan]")
        agent = SQLAgent(config)
        
        console.print("[cyan]执行查询...[/cyan]")
        result = agent.run(query)
        
        # 显示结果
        if result.success:
            console.print("\n[green]✓ 查询成功[/green]")
            
            # 显示 SQL
            if result.sql:
                console.print("\n" + Panel(result.sql, title="[bold]生成的 SQL[/bold]", expand=False))
            
            # 显示答案
            if result.answer:
                console.print("\n" + Panel(result.answer, title="[bold]答案[/bold]", expand=False))
            
            # 显示执行结果
            if result.execution_result and verbose:
                _display_execution_result(result.execution_result)
        else:
            console.print("\n[red]✗ 查询失败[/red]")
            if result.error:
                console.print(f"[red]错误: {result.error}[/red]")
        
        # 保存轨迹
        if save_trajectory:
            _save_trajectory(agent, save_trajectory)
            console.print(f"\n[green]轨迹已保存到: {save_trajectory}[/green]")
        
    except Exception as e:
        console.print(f"\n[red]执行出错: {e}[/red]")
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.option("--config", "-c", "config_file", default="config.yaml", help="配置文件路径")
def interactive(config_file: str):
    """交互式查询模式"""
    # 加载配置
    console.print("[cyan]加载配置...[/cyan]")
    config_data = load_config(config_file)
    
    try:
        config = Config(**config_data)
        agent = SQLAgent(config)
    except Exception as e:
        console.print(f"[red]错误: 初始化失败: {e}[/red]")
        sys.exit(1)
    
    console.print("\n[bold cyan]SemanticSQL Agent 交互模式[/bold cyan]")
    console.print("输入 'exit' 或 'quit' 退出，'help' 查看帮助\n")
    
    while True:
        try:
            # 获取用户输入
            query = console.input("[bold]查询>[/bold] ").strip()
            
            if not query:
                continue
            
            if query.lower() in ['exit', 'quit']:
                console.print("\n[yellow]再见！[/yellow]")
                break
            
            if query.lower() == 'help':
                _show_help()
                continue
            
            # 执行查询
            console.print("\n[cyan]执行中...[/cyan]")
            result = agent.run(query)
            
            # 显示结果
            if result.success:
                if result.sql:
                    console.print("\n[bold]SQL:[/bold]")
                    console.print(result.sql)
                if result.answer:
                    console.print("\n[bold]答案:[/bold]")
                    console.print(result.answer)
            else:
                console.print(f"\n[red]错误: {result.error}[/red]")
            
            console.print("")  # 空行
            
        except KeyboardInterrupt:
            console.print("\n\n[yellow]使用 'exit' 或 'quit' 退出[/yellow]")
        except Exception as e:
            console.print(f"\n[red]错误: {e}[/red]")


@cli.command()
@click.option("--output", "-o", default="config.yaml", help="输出文件路径")
def init(output: str):
    """生成配置文件模板"""
    template = {
        "llm": {
            "provider": "openai",
            "model": "gpt-4",
            "temperature": 0,
            "api_key": "${OPENAI_API_KEY}"
        },
        "database": {
            "type": "mysql",
            "host": "localhost",
            "port": 3306,
            "database": "your_database",
            "username": "your_username",
            "password": "${DB_PASSWORD}"
        },
        "agent": {
            "max_steps": 10,
            "verbose": True
        }
    }
    
    output_path = Path(output)
    
    if output_path.exists():
        if not click.confirm(f"文件 {output} 已存在，是否覆盖？"):
            return
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            if output.endswith('.yaml') or output.endswith('.yml'):
                yaml.dump(template, f, default_flow_style=False, allow_unicode=True)
            else:
                json.dump(template, f, indent=2, ensure_ascii=False)
        
        console.print(f"[green]✓ 配置文件模板已创建: {output}[/green]")
        console.print("\n[yellow]请根据实际情况修改配置文件[/yellow]")
        
    except Exception as e:
        console.print(f"[red]错误: 创建配置文件失败: {e}[/red]")
        sys.exit(1)


def _display_execution_result(execution_result: dict):
    """显示执行结果表格"""
    if not execution_result.get('rows'):
        console.print("\n[yellow]查询结果为空[/yellow]")
        return
    
    rows = execution_result['rows']
    if not rows:
        return
    
    # 创建表格
    table = Table(title="查询结果", show_lines=True)
    
    # 添加列
    columns = list(rows[0].keys())
    for col in columns:
        table.add_column(col, style="cyan")
    
    # 添加行（最多显示10行）
    for row in rows[:10]:
        table.add_row(*[str(row.get(col, '')) for col in columns])
    
    if len(rows) > 10:
        table.add_row(*['...' for _ in columns])
    
    console.print("\n", table)
    console.print(f"\n[dim]共 {len(rows)} 行结果[/dim]")


def _save_trajectory(agent: SQLAgent, filepath: str):
    """保存执行轨迹"""
    trajectory = agent.get_trajectory()
    
    with open(filepath, 'w', encoding='utf-8') as f:
        if filepath.endswith('.yaml') or filepath.endswith('.yml'):
            yaml.dump(trajectory, f, default_flow_style=False, allow_unicode=True)
        else:
            json.dump(trajectory, f, indent=2, ensure_ascii=False)


def _show_help():
    """显示帮助信息"""
    help_text = """
[bold cyan]SemanticSQL Agent 交互模式帮助[/bold cyan]

[bold]基本命令:[/bold]
  exit/quit  - 退出程序
  help       - 显示此帮助

[bold]查询示例:[/bold]
  - 查询所有用户的数量
  - 找出最近一周的订单总额
  - 显示销量最高的前10个产品

[bold]提示:[/bold]
  - 使用自然语言描述你的查询需求
  - 智能体会自动分析数据库结构并生成 SQL
  - 如果查询失败，尝试提供更多细节
"""
    console.print(help_text)


if __name__ == "__main__":
    cli()