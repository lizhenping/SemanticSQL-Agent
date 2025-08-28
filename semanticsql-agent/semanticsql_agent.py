#!/usr/bin/env python3
"""SemanticSQL Agent V2 简化入口脚本"""

import sys
import os
import asyncio
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import click
import yaml
from rich.console import Console
from rich.panel import Panel

# 导入核心组件
from agent.sql_agent_v2 import SQLAgentV2
from utils.config import Config, SQLAgentConfig

console = Console()


def load_config(config_path: str) -> SQLAgentConfig:
    """加载配置文件"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        # 尝试新格式
        if "agent" in data:
            return Config.from_sql_agent_dict(data["agent"])
        else:
            # 兼容旧格式
            return Config.from_dict(data).to_sql_agent_config()
    except Exception as e:
        console.print(f"[red]配置加载失败: {e}[/red]")
        sys.exit(1)


@click.command()
@click.argument("query")
@click.option("--config", "-c", default="examples/config.yaml", help="配置文件路径")
@click.option("--execute/--no-execute", default=True, help="是否执行SQL")
@click.option("--verbose", "-v", is_flag=True, help="详细输出")
def main(query: str, config: str, execute: bool, verbose: bool):
    """SemanticSQL Agent - 自然语言转SQL查询"""
    
    # 显示查询
    console.print(Panel(query, title="查询", border_style="cyan"))
    
    # 加载配置
    sql_config = load_config(config)
    
    # 调整配置
    if verbose:
        sql_config.verbose = True
    
    if not execute and "sql_execution" in sql_config.tools:
        sql_config.tools.remove("sql_execution")
    
    try:
        # 创建智能体
        agent = SQLAgentV2(sql_config)
        
        # 执行查询
        with console.status("[bold green]正在处理查询..."):
            result = agent.query(query)
        
        # 显示结果
        if result.success:
            if result.sql:
                console.print(Panel(
                    result.sql,
                    title="生成的 SQL",
                    border_style="green"
                ))
            
            if result.answer:
                console.print(Panel(
                    result.answer,
                    title="回答",
                    border_style="blue"
                ))
            
            console.print(f"[green]✓ 查询成功[/green] (步数: {result.steps})")
        else:
            console.print(f"[red]✗ 查询失败: {result.error}[/red]")
    
    except Exception as e:
        console.print(f"[red]错误: {e}[/red]")
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()