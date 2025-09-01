"""
SemanticSQL Agent CLI - 命令行接口
专注于批量训练数据生成
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
from config.database import DatabaseConfig
from agent.data_generation_agent import DataGenerationAgent
from models.exceptions import (
    DatabaseConnectionError,
    LLMError,
    AgentExecutionError,
    SemanticSQLException
)


# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def handle_errors(func):
    """统一的错误处理装饰器"""
    import functools
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except DatabaseConnectionError as e:
            click.echo(f"数据库连接失败 [{e.error_code}]: {e.message}", err=True)
            if e.details:
                click.echo(f"详情: {e.details}", err=True)
            sys.exit(1)
        except LLMError as e:
            click.echo(f"LLM错误 [{e.error_code}]: {e.message}", err=True)
            sys.exit(2)
        except AgentExecutionError as e:
            click.echo(f"执行失败 [{e.error_code}]: {e.message}", err=True)
            sys.exit(3)
        except SemanticSQLException as e:
            # 处理所有其他已知异常
            click.echo(f"错误 [{e.error_code}]: {e.message}", err=True)
            sys.exit(4)
        except Exception as e:
            # 未预期的错误
            if click.get_current_context().obj.get('verbose'):
                click.echo(traceback.format_exc(), err=True)
            else:
                click.echo(f"未预期的错误: {e}", err=True)
            sys.exit(5)
    return wrapper


@click.group()
@click.version_option(version="3.0.0")
@click.option('--config', '-c', help='配置文件路径')
@click.option('--verbose', '-v', is_flag=True, help='详细输出')
@click.pass_context
def cli(ctx, config: Optional[str], verbose: bool):
    """SemanticSQL Agent - SQL训练数据生成系统"""
    ctx.ensure_object(dict)
    ctx.obj['config_path'] = config
    ctx.obj['verbose'] = verbose
    
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@click.option('--count', '-n', type=int, default=100, help='生成的问题数量')
@click.option('--output', '-o', default='training_data.jsonl', help='输出文件路径')
@click.option('--database', '-d', help='数据库名称')
@click.option('--format', '-f', type=click.Choice(['json', 'jsonl']), default='jsonl', help='输出格式')
@click.option('--config', '-c', help='配置文件路径')
@click.pass_context
@handle_errors
def generate(ctx, count: int, output: str, database: Optional[str], 
             format: str, config: Optional[str]):
    """生成SQL训练数据"""
    click.echo(f"开始生成 {count} 个SQL训练样本...")
    click.echo("=" * 50)
    
    # 加载配置
    config_path = config or ctx.obj.get('config_path')
    
    if config_path and Path(config_path).exists():
        # 从配置文件加载
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        settings = Settings(**config_data.get('settings', {}))
        db_config = DatabaseConfig(**config_data.get('database', {}))
    else:
        # 使用默认配置
        settings = Settings()
        db_config = DatabaseConfig()
    
    # 如果指定了数据库名，覆盖配置
    if database:
        db_config.database = database
    
    # 确保输出文件有正确的扩展名
    if not output.endswith(f'.{format}'):
        output = f"{output}.{format}"
    
    # 创建Agent
    click.echo("初始化数据生成Agent...")
    agent = DataGenerationAgent(settings, db_config)
    
    # 生成数据
    with click.progressbar(length=count, label='生成进度') as bar:
        try:
            result = agent.generate_training_data(
                count=count,
                output_file=output,
                database_name=database
            )
            
            # 更新进度条
            bar.update(result.successful)
            
        except Exception as e:
            bar.update(0)
            raise
    
    # 显示结果
    click.echo("\n" + "=" * 50)
    click.echo(f"生成完成！")
    click.echo(f"  成功: {result.successful} 个")
    click.echo(f"  失败: {result.failed} 个")
    click.echo(f"  输出文件: {result.output_file}")
    
    # 显示示例
    if result.examples and ctx.obj.get('verbose'):
        click.echo("\n生成示例:")
        for i, example in enumerate(result.examples[:3], 1):
            click.echo(f"\n示例 {i}:")
            click.echo(f"  问题: {example.get('question', 'N/A')}")
            click.echo(f"  SQL: {example.get('sql', 'N/A')}")


@cli.command()
@click.option('--database', '-d', required=True, help='数据库名称')
@click.option('--output', '-o', help='分析结果输出文件')
@click.option('--config', '-c', help='配置文件路径')
@click.pass_context
@handle_errors
def analyze(ctx, database: str, output: Optional[str], config: Optional[str]):
    """分析数据库结构（用于调试）"""
    click.echo(f"分析数据库: {database}")
    click.echo("=" * 50)
    
    # 加载配置
    config_path = config or ctx.obj.get('config_path')
    
    if config_path and Path(config_path).exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        settings = Settings(**config_data.get('settings', {}))
        db_config = DatabaseConfig(**config_data.get('database', {}))
    else:
        settings = Settings()
        db_config = DatabaseConfig()
    
    # 设置数据库名
    db_config.database = database
    
    # 创建Agent
    agent = DataGenerationAgent(settings, db_config)
    
    # 执行分析
    click.echo("执行数据库分析...")
    result = agent.analyze_database(database)
    
    if result["success"]:
        click.echo("分析完成！")
        
        # 显示分析结果摘要
        analysis = result["analysis"]
        if "schema_info" in analysis:
            schema = analysis["schema_info"]
            click.echo(f"\n表数量: {schema.get('table_count', 0)}")
        
        if "domain_info" in analysis:
            domain = analysis["domain_info"]
            click.echo(f"主要领域: {domain.get('primary_domain', 'Unknown')}")
        
        # 保存结果
        if output:
            with open(output, 'w', encoding='utf-8') as f:
                json.dump(analysis, f, ensure_ascii=False, indent=2)
            click.echo(f"\n分析结果已保存到: {output}")
    else:
        click.echo(f"分析失败: {result['error']}", err=True)


@cli.command()
def config_template():
    """生成配置文件模板"""
    template = {
        "settings": {
            "llm_model": "qwen-plus",
            "llm_temperature": 0.7,
            "llm_max_tokens": 2000,
            "max_steps": 15,
            "verbose": False
        },
        "database": {
            "host": "localhost",
            "port": 3306,
            "username": "root",
            "password": "",
            "database": "test_db"
        },
        "generation": {
            "scenarios_per_batch": 5,
            "max_retries": 3,
            "validation_enabled": True
        }
    }
    
    click.echo(yaml.dump(template, default_flow_style=False, allow_unicode=True))


if __name__ == "__main__":
    cli()