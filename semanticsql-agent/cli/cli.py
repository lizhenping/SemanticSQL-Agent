"""
同步版本的CLI命令行接口
"""

import json
import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

import click
import yaml
from click.testing import CliRunner

from config.trae_config import TraeConfig, DEFAULT_CONFIG_TEMPLATE
from agent.sql_agent import SQLAgent
from agent.smart_sql_agent import SmartSQLAgent
from database.connection_manager import DatabaseManager


# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


@click.group()
@click.version_option(version="2.0.0")
@click.option('--config', '-c', default='trae_config.yaml', help='配置文件路径')
@click.option('--verbose', '-v', is_flag=True, help='详细输出')
@click.pass_context
def cli(ctx, config: str, verbose: bool):
    """SemanticSQL Agent - 同步版本"""
    ctx.ensure_object(dict)
    ctx.obj['config_path'] = config
    ctx.obj['verbose'] = verbose
    
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@click.option('--output', '-o', default='trae_config.yaml', help='输出配置文件路径')
@click.option('--database-type', default='mysql', help='数据库类型')
@click.option('--host', default='192.168.200.216', help='数据库主机')
@click.option('--port', default=13306, help='数据库端口')
@click.option('--database', default='testdb', help='数据库名称')
@click.option('--username', default='testuser', help='数据库用户名')
@click.option('--password', default='testpass', help='数据库密码')
@click.option('--model', default='Qwen3-14B', help='LLM模型')
@click.option('--base-url', default='http://192.168.200.216:9009/v1', help='LLM基础URL')
def init(output: str, database_type: str, host: str, port: int, database: str, 
         username: str, password: str, model: str, base_url: str):
    """生成配置文件"""
    
    config_data = {
        **DEFAULT_CONFIG_TEMPLATE,
        "llm": {
            **DEFAULT_CONFIG_TEMPLATE["llm"],
            "model": model,
            "base_url": base_url
        },
        "database": {
            **DEFAULT_CONFIG_TEMPLATE["database"],
            "type": database_type,
            "host": host,
            "port": port,
            "database": database,
            "username": username,
            "password": password
        }
    }
    
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
        
        click.echo(f"✓ 配置文件已创建: {output}")
        click.echo(f"\n请根据需要修改配置文件，然后运行:")
        click.echo(f"  semanticsql run '你的查询' --config {output}")
        
    except Exception as e:
        click.echo(f"错误: 创建配置文件失败: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("query", required=False)
@click.option('--file', '-f', help='包含查询的文件路径')
@click.option('--config', '-c', default='trae_config.yaml', help='配置文件路径')
@click.option('--model', '-m', help='使用的模型')
@click.option('--database', '-d', help='数据库连接信息')
@click.option('--max-steps', type=int, help='最大执行步数')
@click.option('--save-result', '-s', help='保存结果到文件')
@click.option('--verbose', '-v', is_flag=True, help='详细输出')
@click.option('--save-trajectory', '-t', help='保存执行轨迹')
@click.pass_context
def run(ctx, query: Optional[str], file: Optional[str], config: str, 
        model: Optional[str], database: Optional[str], max_steps: Optional[int],
        save_result: Optional[str], verbose: bool, save_trajectory: Optional[str]):
    """执行自然语言查询"""
    
    # 获取查询内容
    if file:
        if query:
            click.echo("错误: 不能同时使用查询字符串和 --file 参数", err=True)
            sys.exit(1)
        try:
            query = Path(file).read_text(encoding='utf-8').strip()
        except FileNotFoundError:
            click.echo(f"错误: 文件不存在: {file}", err=True)
            sys.exit(1)
    elif not query:
        query = click.prompt("请输入查询")
    
    # 加载配置
    try:
        trae_config = TraeConfig.load_config(config)
        
        # 命令行参数覆盖
        if model:
            trae_config.llm.model = model
        if max_steps:
            trae_config.agent.max_steps = max_steps
        if verbose:
            trae_config.agent.verbose = True
        
        # 数据库连接覆盖
        if database:
            # 简化的数据库连接字符串解析
            if "://" in database:
                import re
                match = re.match(r'(.+?)://(.+?):(.+?)@(.+?):(\d+)/(.+)', database)
                if match:
                    db_type, username, password, host, port, db_name = match.groups()
                    trae_config.database.type = db_type
                    trae_config.database.username = username
                    trae_config.database.password = password
                    trae_config.database.host = host
                    trae_config.database.port = int(port)
                    trae_config.database.database = db_name
    
    except Exception as e:
        click.echo(f"错误: 配置加载失败: {e}", err=True)
        sys.exit(1)
    
    click.echo(f"查询: {query}")
    click.echo("=" * 50)
    
    try:
        # 初始化数据库连接
        from database.connection_manager import DatabaseManager
        db_manager = DatabaseManager(trae_config.database)
        if not db_manager.initialize():
            click.echo("错误: 数据库连接失败", err=True)
            sys.exit(1)
        
        # 创建SQL智能体
        agent = SQLAgent(trae_config)
        
        # 执行查询
        result = agent.query(query)
        
        # 显示结果
        if result.success:
            click.echo("✓ 查询成功")
            if result.sql:
                click.echo(f"\nSQL:\n{result.sql}")
            if result.answer:
                click.echo(f"\n结果: {result.answer}")
            if result.data and len(result.data) > 0:
                click.echo(f"\n数据 ({result.row_count} 条):")
                for i, row in enumerate(result.data[:5]):  # 显示前5条
                    click.echo(f"  {i+1}: {row}")
                if result.row_count > 5:
                    click.echo(f"  ... 还有 {result.row_count - 5} 条")
        else:
            click.echo("✗ 查询失败")
            click.echo(f"错误: {result.error}")
        
        # 保存结果
        if save_result:
            output_data = {
                "query": query,
                "success": result.success,
                "sql": result.sql,
                "answer": result.answer,
                "data": result.data,
                "row_count": result.row_count,
                "execution_time": result.execution_time,
                "error": result.error
            }
            
            save_path = Path(save_result)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            
            click.echo(f"\n结果已保存到: {save_result}")
        
        # 保存轨迹
        if save_trajectory:
            trajectory = agent.get_trajectory()
            if trajectory:
                trajectory_path = Path(save_trajectory)
                trajectory_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(trajectory_path, 'w', encoding='utf-8') as f:
                    json.dump(trajectory, f, ensure_ascii=False, indent=2)
                
                click.echo(f"\n轨迹已保存到: {save_trajectory}")
        
        db_manager.close()
        
    except Exception as e:
        click.echo(f"错误: 执行查询失败: {e}", err=True)
        if trae_config.agent.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.option('--config', '-c', default='trae_config.yaml', help='配置文件路径')
@click.option('--save-history', is_flag=True, help='保存历史记录')
@click.pass_context
def interactive(ctx, config: str, save_history: bool):
    """交互式查询模式"""
    
    try:
        trae_config = TraeConfig.load_config(config)
        
        # 初始化数据库连接
        db_manager = DatabaseManager(trae_config.database)
        if not db_manager.initialize():
            click.echo("错误: 数据库连接失败", err=True)
            sys.exit(1)
        
        # 创建SQL智能体
        agent = SQLAgent(trae_config)
        
        click.echo("SemanticSQL Agent 交互式模式")
        click.echo("输入 'help' 查看帮助，输入 'exit' 退出")
        click.echo("=" * 50)
        
        history = []
        
        while True:
            try:
                query = click.prompt("\n查询", type=str)
                
                if query.lower() == 'exit' or query.lower() == 'quit':
                    break
                elif query.lower() == 'help':
                    _show_interactive_help()
                    continue
                elif query.lower() == 'clear':
                    click.clear()
                    continue
                elif query.lower() == 'config':
                    click.echo(f"当前配置: {agent.get_config()}")
                    continue
                elif query.lower() == 'schema':
                    schema = agent.explain_schema()
                    click.echo(f"数据库Schema: {schema}")
                    continue
                
                if not query.strip():
                    continue
                
                # 执行查询
                result = agent.query(query)
                
                # 保存历史
                if save_history:
                    history.append({
                        "query": query,
                        "result": result.to_dict(),
                        "timestamp": datetime.now().isoformat()
                    })
                
                # 显示结果
                if result.success:
                    click.echo("✓ 成功")
                    if result.sql:
                        click.echo(f"SQL: {result.sql}")
                    if result.answer:
                        click.echo(f"答案: {result.answer}")
                    if result.data and len(result.data) > 0:
                        click.echo(f"数据 ({result.row_count} 条):")
                        for i, row in enumerate(result.data[:3]):
                            click.echo(f"  {i+1}: {row}")
                        if result.row_count > 3:
                            click.echo(f"  ... 还有 {result.row_count - 3} 条")
                else:
                    click.echo("✗ 失败")
                    click.echo(f"错误: {result.error}")
            
            except KeyboardInterrupt:
                click.echo("\n再见！")
                break
            except Exception as e:
                click.echo(f"错误: {e}")
        
        if save_history and history:
            history_file = Path("query_history.json")
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
            click.echo(f"\n历史记录已保存到: {history_file}")
        
        db_manager.close()
        
    except Exception as e:
        click.echo(f"错误: 启动交互模式失败: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--config', '-c', default='trae_config.yaml', help='配置文件路径')
@click.option('--table', '-t', help='指定表名')
@click.pass_context
def schema(ctx, config: str, table: Optional[str]):
    """查看数据库Schema"""
    
    try:
        trae_config = TraeConfig.load_config(config)
        
        # 初始化数据库连接
        db_manager = DatabaseManager(trae_config.database)
        if not db_manager.initialize():
            click.echo("错误: 数据库连接失败", err=True)
            sys.exit(1)
        
        if table:
            # 显示指定表的信息
            table_info = db_manager.get_table_info(table)
            click.echo(f"表信息: {table}")
            click.echo(json.dumps(table_info, ensure_ascii=False, indent=2))
        else:
            # 显示所有表
            tables = db_manager.get_tables()
            click.echo(f"数据库: {trae_config.database.database}")
            click.echo(f"表 ({len(tables)} 个):")
            
            for table_name in tables:
                click.echo(f"  - {table_name}")
        
        db_manager.close()
        
    except Exception as e:
        click.echo(f"错误: 获取Schema失败: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--config', '-c', default='trae_config.yaml', help='配置文件路径')
@click.pass_context
def test(ctx, config: str):
    """测试数据库连接"""
    
    try:
        trae_config = TraeConfig.load_config(config)
        
        click.echo("测试数据库连接...")
        
        db_manager = DatabaseManager(trae_config.database)
        if db_manager.initialize():
            click.echo("✓ 数据库连接成功")
            
            # 获取数据库信息
            info = db_manager.get_database_info()
            click.echo(f"数据库: {info['database']}")
            click.echo(f"类型: {info['type']}")
            click.echo(f"版本: {info['version']}")
            click.echo(f"表数量: {info['tables_count']}")
            
        else:
            click.echo("✗ 数据库连接失败")
        
        db_manager.close()
        
    except Exception as e:
        click.echo(f"错误: 测试连接失败: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("request", required=False, default="请分析这个数据库")
@click.option('--config', '-c', default='trae_config.yaml', help='配置文件路径')
@click.option('--save-result', '-s', help='保存结果到文件')
@click.option('--verbose', '-v', is_flag=True, help='详细输出')
@click.option('--stage-by-stage', is_flag=True, help='分阶段显示结果')
@click.pass_context
def smart_analyze(ctx, request: str, config: str, save_result: Optional[str], 
                 verbose: bool, stage_by_stage: bool):
    """智能分析数据库 - 自动执行完整6步流程"""
    
    click.echo("🤖 启动智能数据库分析...")
    click.echo(f"📋 分析请求: {request}")
    click.echo("=" * 60)
    
    try:
        # 加载配置
        trae_config = TraeConfig.load_config(config)
        
        if verbose:
            trae_config.agent.verbose = True
            logging.getLogger().setLevel(logging.DEBUG)
        
        # 创建智能SQL Agent
        smart_agent = SmartSQLAgent(trae_config)
        
        # 显示开始信息
        click.echo("📊 开始执行智能分析流程:")
        click.echo("   1️⃣ 连接数据库")
        click.echo("   2️⃣ 分析数据库领域") 
        click.echo("   3️⃣ 字段分类分析")
        click.echo("   4️⃣ 表结构分析")
        click.echo("   5️⃣ ER关系分析")
        click.echo("   6️⃣ 场景问题生成")
        click.echo()
        
        # 执行智能分析
        if stage_by_stage:
            # 分阶段显示进度
            result = smart_agent.smart_analyze(request)
        else:
            # 正常执行
            with click.progressbar(length=6, label='分析进度') as bar:
                result = smart_agent.smart_analyze(request)
                for _ in range(6):
                    bar.update(1)
        
        # 显示结果
        if result.success:
            click.echo("✅ 智能分析完成!")
            click.echo(f"⏱️  总执行时间: {result.execution_time:.2f}秒")
            click.echo(f"📈 完成阶段: {len(result.stages_completed)}/6")
            click.echo()
            
            # 显示各阶段结果摘要
            _display_analysis_summary(result)
            
            # 显示生成的场景问题
            if result.generated_scenarios:
                click.echo("🎯 生成的查询场景:")
                for i, scenario in enumerate(result.generated_scenarios[:5], 1):
                    click.echo(f"  {i}. {scenario.get('name', '未命名场景')}")
                    if scenario.get('question'):
                        click.echo(f"     问题: {scenario['question']}")
                    click.echo()
            
        else:
            click.echo("❌ 智能分析失败")
            click.echo(f"错误: {result.error}")
        
        # 保存结果
        if save_result:
            save_path = Path(save_result)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
            
            click.echo(f"💾 结果已保存到: {save_result}")
        
    except Exception as e:
        click.echo(f"❌ 智能分析失败: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _display_analysis_summary(result):
    """显示分析结果摘要"""
    click.echo("📋 分析结果摘要:")
    click.echo("-" * 40)
    
    # 数据库信息
    if result.database_info:
        db_info = result.database_info
        click.echo(f"📊 数据库: {db_info.get('database', 'N/A')} ({db_info.get('type', 'N/A')})")
        click.echo(f"📁 表数量: {db_info.get('tables_count', 0)}")
    
    # 领域分析
    if result.domain_analysis:
        click.echo(f"🏢 业务领域: 已识别")
    
    # 字段分类
    if result.field_classification:
        click.echo(f"🏷️  字段分类: 已完成")
    
    # 表结构
    if result.table_analysis:
        table_count = result.table_analysis.get('total_tables', 0)
        click.echo(f"📋 表结构: 分析了{table_count}个表")
    
    # ER关系
    if result.er_analysis:
        click.echo(f"🔗 ER关系: 已分析")
    
    # 场景生成
    if result.generated_scenarios:
        scenario_count = len(result.generated_scenarios)
        click.echo(f"💡 场景问题: 生成了{scenario_count}个场景")
    
    click.echo()


def _show_interactive_help():
    """显示交互模式帮助"""
    help_text = """
可用命令:
  help       - 显示此帮助
  clear      - 清屏
  config     - 显示当前配置
  schema     - 显示数据库Schema
  exit/quit  - 退出程序

查询示例:
  - 查询所有用户的数量
  - 找出最近一周的订单总额
  - 显示销量最高的前10个产品
  - 统计每个用户的订单数量

提示:
  - 使用自然语言描述查询需求
  - 智能体会自动分析数据库并生成SQL
  - 如果查询失败，尝试提供更多细节
"""
    click.echo(help_text)


# CLI入口点
if __name__ == "__main__":
    cli()