"""SemanticSQL Agent 命令行接口（使用新的控制台系统）"""

import json
import sys
from pathlib import Path
from typing import Optional

import click
import yaml

from agent import SQLAgent
from config import Config
from utils.cli import ConsoleFactory, ConsoleMode, ConsoleType
from utils.llm_clients import LLMClient


def load_config(config_file: str) -> dict:
    """加载配置文件"""
    config_path = Path(config_file)
    
    if not config_path.exists():
        click.echo(f"错误: 配置文件不存在: {config_file}", err=True)
        sys.exit(1)
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            if config_file.endswith('.yaml') or config_file.endswith('.yml'):
                return yaml.safe_load(f)
            elif config_file.endswith('.json'):
                return json.load(f)
            else:
                click.echo("错误: 配置文件必须是 .yaml/.yml 或 .json 格式", err=True)
                sys.exit(1)
    except Exception as e:
        click.echo(f"错误: 加载配置文件失败: {e}", err=True)
        sys.exit(1)


@click.group()
@click.version_option(version="0.3.0")
def cli():
    """SemanticSQL Agent - 简化的 NL2SQL 智能体"""
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
@click.option(
    "--console-type",
    type=click.Choice(["simple", "rich"], case_sensitive=False),
    default="simple",
    help="控制台类型"
)
def run(
    query: Optional[str],
    file_path: Optional[str],
    config_file: str,
    model: Optional[str],
    provider: Optional[str],
    database: Optional[str],
    max_steps: Optional[int],
    save_trajectory: Optional[str],
    verbose: bool,
    console_type: str
):
    """执行自然语言查询"""
    
    # 创建控制台
    console_type_enum = ConsoleType.RICH if console_type == "rich" else ConsoleType.SIMPLE
    console = ConsoleFactory.create_console(console_type_enum, ConsoleMode.RUN)
    console.start()
    
    # 获取查询内容
    if file_path:
        if query:
            console.print("错误: 不能同时使用查询字符串和 --file 参数", style="error")
            sys.exit(1)
        try:
            query = Path(file_path).read_text(encoding='utf-8').strip()
        except FileNotFoundError:
            console.print(f"错误: 文件不存在: {file_path}", style="error")
            sys.exit(1)
    elif not query:
        console.print("错误: 必须提供查询字符串或使用 --file 参数", style="error")
        sys.exit(1)
    
    # 加载配置
    console.print("加载配置...", style="info")
    config_data = load_config(config_file)
    
    # 命令行参数覆盖配置文件
    if model:
        config_data.setdefault('model', {})['model'] = model
    if provider:
        config_data.setdefault('model', {})['provider'] = provider
    if database:
        config_data.setdefault('database', {})['connection_string'] = database
    if max_steps:
        config_data['max_steps'] = max_steps
    
    # 创建配置对象
    try:
        config = Config.from_dict(config_data)
    except Exception as e:
        console.print(f"错误: 配置无效: {e}", style="error")
        sys.exit(1)
    
    # 显示查询
    console.print(f"\n查询: {query}\n", style="info")
    
    # 创建并运行智能体
    try:
        console.print_status("thinking", "初始化智能体...")
        
        # 创建 LLM 客户端
        llm_client = LLMClient(config.model)
        
        # 创建智能体
        agent = SQLAgent(config, llm_client)
        
        console.print_status("executing", "执行查询...")
        result = agent.run(query)
        
        # 显示结果
        if result.success:
            console.print_status("completed", "查询成功")
            
            # 显示 SQL
            if result.sql:
                console.print(f"\nSQL:\n{result.sql}", style="success")
            
            # 显示答案
            if result.answer:
                console.print(f"\n答案: {result.answer}", style="success")
            
            # 显示执行结果表格
            if result.execution_result and verbose:
                rows = result.execution_result.get('rows', [])
                if rows:
                    headers = list(rows[0].keys())
                    data = [[row.get(h, '') for h in headers] for row in rows]
                    console.print_table(data, headers)
        else:
            console.print_status("error", "查询失败")
            if result.error:
                console.print(f"错误: {result.error}", style="error")
        
        # 保存轨迹
        if save_trajectory:
            trajectory = agent.get_trajectory()
            with open(save_trajectory, 'w', encoding='utf-8') as f:
                if save_trajectory.endswith('.yaml') or save_trajectory.endswith('.yml'):
                    yaml.dump(trajectory, f, allow_unicode=True)
                else:
                    json.dump(trajectory, f, ensure_ascii=False, indent=2)
            console.print(f"\n轨迹已保存到: {save_trajectory}", style="success")
        
    except Exception as e:
        console.print_status("error", f"执行出错: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.option("--config", "-c", "config_file", default="config.yaml", help="配置文件路径")
@click.option(
    "--console-type",
    type=click.Choice(["simple", "rich"], case_sensitive=False),
    help="控制台类型（默认自动选择）"
)
def interactive(config_file: str, console_type: Optional[str]):
    """交互式查询模式"""
    # 自动选择控制台类型
    if not console_type:
        console_type_enum = ConsoleFactory.get_recommended_console_type(ConsoleMode.INTERACTIVE)
    else:
        console_type_enum = ConsoleType.RICH if console_type == "rich" else ConsoleType.SIMPLE
    
    # 创建控制台
    console = ConsoleFactory.create_console(console_type_enum, ConsoleMode.INTERACTIVE)
    console.start()
    
    # 加载配置
    console.print("加载配置...", style="info")
    config_data = load_config(config_file)
    
    try:
        config = Config.from_dict(config_data)
        llm_client = LLMClient(config.model)
        agent = SQLAgent(config, llm_client)
    except Exception as e:
        console.print(f"错误: 初始化失败: {e}", style="error")
        sys.exit(1)
    
    console.print("输入 'help' 查看帮助\n", style="info")
    
    while True:
        # 获取用户输入
        query = console.get_user_input("查询> ")
        
        if not query:
            console.print("\n再见！", style="info")
            break
        
        if query.lower() == 'help':
            _show_help(console)
            continue
        
        if query.lower() == 'clear':
            console.clear()
            continue
        
        # 执行查询
        try:
            console.print_status("executing", "执行中...")
            result = agent.run(query)
            
            # 显示结果
            if result.success:
                if result.sql:
                    console.print(f"\nSQL:\n{result.sql}", style="success")
                if result.answer:
                    console.print(f"\n答案: {result.answer}", style="success")
            else:
                console.print(f"\n错误: {result.error}", style="error")
            
        except Exception as e:
            console.print(f"\n错误: {e}", style="error")
        
        console.print("")  # 空行


@cli.command()
@click.option("--output", "-o", default="config.yaml", help="输出文件路径")
def init(output: str):
    """生成配置文件模板"""
    console = ConsoleFactory.create_console(ConsoleType.SIMPLE)
    
    template = {
        "model": {
            "provider": "openai",
            "model": "gpt-4",
            "temperature": 0,
            "api_key": "${OPENAI_API_KEY}",
            "max_tokens": 2000
        },
        "database": {
            "type": "mysql",
            "host": "localhost",
            "port": 3306,
            "database": "your_database",
            "username": "your_username",
            "password": "${DB_PASSWORD}"
        },
        "max_steps": 10,
        "verbose": True
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
        
        console.print(f"✓ 配置文件模板已创建: {output}", style="success")
        console.print("\n请根据实际情况修改配置文件", style="warning")
        
    except Exception as e:
        console.print(f"错误: 创建配置文件失败: {e}", style="error")
        sys.exit(1)


def _show_help(console):
    """显示帮助信息"""
    help_text = """
可用命令:
  help       - 显示此帮助
  clear      - 清屏
  exit/quit  - 退出程序

查询示例:
  - 查询所有用户的数量
  - 找出最近一周的订单总额
  - 显示销量最高的前10个产品

提示:
  - 使用自然语言描述你的查询需求
  - 智能体会自动分析数据库结构并生成 SQL
  - 如果查询失败，尝试提供更多细节
"""
    console.print(help_text, style="info")


if __name__ == "__main__":
    cli()