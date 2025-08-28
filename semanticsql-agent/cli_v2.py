"""优化后的 SemanticSQL Agent CLI（基于 trae_agent 设计）"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional, Dict, Any

import click
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from dotenv import load_dotenv

from semanticsql_agent.agent.sql_agent_v2 import SQLAgentV2
from semanticsql_agent.utils.config import Config, SQLAgentConfig
from semanticsql_agent.utils.cli import ConsoleFactory, ConsoleMode, ConsoleType

# 加载环境变量
load_dotenv()

console = Console()


def resolve_config_file(config_file: str) -> str:
    """解析配置文件路径（支持向后兼容）"""
    if config_file.endswith(".yaml") or config_file.endswith(".yml"):
        yaml_path = Path(config_file)
        json_path = Path(config_file.replace(".yaml", ".json").replace(".yml", ".json"))
        
        if yaml_path.exists():
            return str(yaml_path)
        elif json_path.exists():
            console.print(f"[yellow]YAML 配置未找到，使用 JSON 配置: {json_path}[/yellow]")
            return str(json_path)
        else:
            # 如果都不存在，尝试在 examples 目录查找
            examples_yaml = Path("examples") / config_file
            examples_json = Path("examples") / config_file.replace(".yaml", ".json").replace(".yml", ".json")
            
            if examples_yaml.exists():
                return str(examples_yaml)
            elif examples_json.exists():
                return str(examples_json)
            else:
                console.print(
                    "[red]错误: 配置文件未找到。请指定有效的配置文件路径。[/red]"
                )
                sys.exit(1)
    else:
        return config_file


def load_config(config_file: str) -> Dict[str, Any]:
    """加载配置文件"""
    config_path = Path(resolve_config_file(config_file))
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            if config_path.suffix in ['.yaml', '.yml']:
                return yaml.safe_load(f)
            elif config_path.suffix == '.json':
                return json.load(f)
            else:
                console.print("[red]错误: 配置文件必须是 .yaml/.yml 或 .json 格式[/red]")
                sys.exit(1)
    except Exception as e:
        console.print(f"[red]错误: 加载配置文件失败: {e}[/red]")
        sys.exit(1)


@click.group()
@click.version_option(version="0.4.0")
def cli():
    """SemanticSQL Agent V2 - 优化的 NL2SQL 智能体"""
    pass


@cli.command()
@click.argument("query", required=False)
@click.option("--file", "-f", "file_path", help="包含查询的文件路径")
@click.option("--config", "-c", "config_file", default="config.yaml", help="配置文件路径")
@click.option("--output", "-o", help="输出文件路径")
@click.option("--format", "output_format", type=click.Choice(['json', 'yaml', 'table']), 
              default='table', help="输出格式")
@click.option("--verbose", "-v", is_flag=True, help="详细输出")
@click.option("--execute/--no-execute", default=True, help="是否执行生成的SQL")
def query(
    query: Optional[str],
    file_path: Optional[str],
    config_file: str,
    output: Optional[str],
    output_format: str,
    verbose: bool,
    execute: bool
):
    """执行自然语言查询"""
    # 加载配置
    config_data = load_config(config_file)
    
    # 创建 SQL 智能体配置
    if "agent" in config_data:
        # 新格式配置
        sql_config = Config.from_sql_agent_dict(config_data["agent"])
    else:
        # 兼容旧格式
        sql_config = Config.from_dict(config_data).to_sql_agent_config()
    
    # 设置详细模式
    if verbose:
        sql_config.verbose = True
    
    # 获取查询内容
    if not query and not file_path:
        console.print("[red]错误: 必须提供查询内容或文件路径[/red]")
        sys.exit(1)
    
    if file_path:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                query = f.read().strip()
        except Exception as e:
            console.print(f"[red]错误: 读取文件失败: {e}[/red]")
            sys.exit(1)
    
    # 显示查询
    console.print(Panel(query, title="查询", border_style="cyan"))
    
    # 创建并执行智能体
    try:
        agent = SQLAgentV2(sql_config)
        
        # 根据是否执行调整工具列表
        if not execute and "sql_execution" in sql_config.tools:
            sql_config.tools.remove("sql_execution")
        
        # 执行查询
        with console.status("[bold green]正在处理查询..."):
            result = agent.query(query)
        
        # 显示结果
        display_result(result, output_format, output)
        
    except Exception as e:
        console.print(f"[red]错误: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option("--config", "-c", "config_file", default="config.yaml", help="配置文件路径")
@click.option("--mode", "-m", type=click.Choice(['multiline', 'single']), 
              default='multiline', help="输入模式")
def interactive(config_file: str, mode: str):
    """交互式查询模式"""
    # 加载配置
    config_data = load_config(config_file)
    
    # 创建 SQL 智能体配置
    if "agent" in config_data:
        sql_config = Config.from_sql_agent_dict(config_data["agent"])
    else:
        sql_config = Config.from_dict(config_data).to_sql_agent_config()
    
    # 创建控制台
    console_mode = ConsoleMode.MULTILINE if mode == 'multiline' else ConsoleMode.SINGLE_LINE
    cli_console = ConsoleFactory.create_console(ConsoleType.RICH, console_mode)
    
    # 显示欢迎信息
    console.print(Panel(
        "[bold cyan]SemanticSQL Agent V2 交互模式[/bold cyan]\n\n"
        "输入自然语言查询，输入 'exit' 或 'quit' 退出\n"
        "输入 'help' 查看帮助信息",
        title="欢迎",
        border_style="green"
    ))
    
    # 创建智能体
    try:
        agent = SQLAgentV2(sql_config)
        
        while True:
            # 获取用户输入
            query = cli_console.prompt("\n[bold green]查询[/bold green]")
            
            # 检查退出命令
            if query.lower() in ['exit', 'quit', 'q']:
                console.print("[yellow]再见！[/yellow]")
                break
            
            # 检查帮助命令
            if query.lower() == 'help':
                show_help()
                continue
            
            # 执行查询
            try:
                with console.status("[bold green]正在处理查询..."):
                    result = agent.query(query)
                
                # 显示结果
                display_result(result, 'table')
                
            except Exception as e:
                console.print(f"[red]错误: {e}[/red]")
            
            # 重置智能体状态
            agent.reset()
    
    except Exception as e:
        console.print(f"[red]初始化失败: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option("--config", "-c", "config_file", default="config.yaml", help="配置文件路径")
def validate(config_file: str):
    """验证配置文件"""
    try:
        # 加载配置
        config_data = load_config(config_file)
        
        # 尝试创建配置对象
        if "agent" in config_data:
            sql_config = Config.from_sql_agent_dict(config_data["agent"])
        else:
            sql_config = Config.from_dict(config_data).to_sql_agent_config()
        
        # 显示配置信息
        table = Table(title="配置信息", show_header=True, header_style="bold cyan")
        table.add_column("配置项", style="cyan")
        table.add_column("值", style="green")
        
        # 模型配置
        table.add_row("LLM 模型", sql_config.model.model)
        table.add_row("API URL", sql_config.model.base_url)
        table.add_row("温度", str(sql_config.model.temperature))
        table.add_row("最大令牌数", str(sql_config.model.max_tokens))
        
        # 数据库配置
        table.add_row("数据库类型", sql_config.database.type)
        table.add_row("数据库主机", f"{sql_config.database.host}:{sql_config.database.port}")
        table.add_row("数据库名", sql_config.database.database)
        
        # 智能体配置
        table.add_row("最大步数", str(sql_config.max_steps))
        table.add_row("工具数量", str(len(sql_config.tools)))
        table.add_row("启用思考工具", "是" if sql_config.enable_thinking_tool else "否")
        
        console.print(table)
        console.print("[green]✓ 配置文件验证成功[/green]")
        
    except Exception as e:
        console.print(f"[red]✗ 配置文件验证失败: {e}[/red]")
        sys.exit(1)


@cli.command()
def list_tools():
    """列出所有可用工具"""
    from semanticsql_agent.tools import tools_registry
    
    table = Table(title="可用工具", show_header=True, header_style="bold cyan")
    table.add_column("工具名称", style="cyan")
    table.add_column("工具类", style="green")
    table.add_column("描述", style="white")
    
    for tool_name, tool_class in tools_registry.items():
        # 创建临时实例获取描述
        try:
            # 某些工具需要参数，这里只显示类名
            description = getattr(tool_class, 'description', '无描述')
            table.add_row(tool_name, tool_class.__name__, description)
        except:
            table.add_row(tool_name, tool_class.__name__, "无法获取描述")
    
    console.print(table)


def display_result(result, output_format: str, output_file: Optional[str] = None):
    """显示查询结果"""
    if output_format == 'json':
        output_data = {
            "success": result.success,
            "question": result.question,
            "sql": result.sql,
            "answer": result.answer,
            "steps": result.steps
        }
        
        if result.execution_result:
            output_data["execution_result"] = result.execution_result
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            console.print(f"[green]结果已保存到 {output_file}[/green]")
        else:
            console.print_json(data=output_data)
    
    elif output_format == 'yaml':
        output_data = {
            "success": result.success,
            "question": result.question,
            "sql": result.sql,
            "answer": result.answer,
            "steps": result.steps
        }
        
        if result.execution_result:
            output_data["execution_result"] = result.execution_result
        
        yaml_str = yaml.dump(output_data, allow_unicode=True, default_flow_style=False)
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(yaml_str)
            console.print(f"[green]结果已保存到 {output_file}[/green]")
        else:
            console.print(yaml_str)
    
    else:  # table format
        # 显示 SQL
        if result.sql:
            console.print(Panel(
                result.sql,
                title="生成的 SQL",
                border_style="green"
            ))
        
        # 显示答案
        if result.answer:
            console.print(Panel(
                result.answer,
                title="回答",
                border_style="blue"
            ))
        
        # 显示执行结果
        if result.execution_result and isinstance(result.execution_result, dict):
            if result.execution_result.get("success"):
                # 显示结果表格
                rows = result.execution_result.get("data", [])
                if rows:
                    # 创建表格
                    table = Table(title="查询结果", show_header=True)
                    
                    # 添加列
                    for col in rows[0].keys():
                        table.add_column(col)
                    
                    # 添加数据（最多显示10行）
                    for row in rows[:10]:
                        table.add_row(*[str(v) for v in row.values()])
                    
                    if len(rows) > 10:
                        table.add_row(*["..." for _ in rows[0].keys()])
                    
                    console.print(table)
                    console.print(f"[dim]共 {len(rows)} 行[/dim]")
        
        # 显示统计信息
        status_color = "green" if result.success else "red"
        console.print(f"\n[{status_color}]状态: {'成功' if result.success else '失败'}[/{status_color}]")
        console.print(f"[dim]执行步数: {result.steps}[/dim]")


def show_help():
    """显示帮助信息"""
    help_text = """
[bold cyan]SemanticSQL Agent V2 帮助[/bold cyan]

[bold]基本命令:[/bold]
- 直接输入自然语言查询来生成和执行 SQL
- exit/quit/q: 退出程序
- help: 显示此帮助信息

[bold]查询示例:[/bold]
- "查询所有订单的总金额"
- "找出销售额最高的前10个产品"
- "统计每个月的用户注册数量"

[bold]高级功能:[/bold]
- 支持复杂的多表查询
- 自动分析数据库结构和关系
- 智能字段分类和实体识别
- SQL 验证和优化建议
"""
    console.print(Panel(help_text, border_style="blue"))


if __name__ == "__main__":
    cli()