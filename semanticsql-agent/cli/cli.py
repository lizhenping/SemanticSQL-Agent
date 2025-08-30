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
# 只需要SmartSQLAgent即可
from agent.smart_sql_agent import SmartSQLAgent
from database.connection_manager import DatabaseManager


# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


@click.group()
@click.version_option(version="2.0.0")
@click.option('--config', '-c', default='configs/config.yaml', help='配置文件路径')
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
@click.option('--output', '-o', default='configs/config.yaml', help='输出配置文件路径')
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
@click.option('--config', '-c', default='configs/config.yaml', help='配置文件路径')
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
        
        # 创建智能SQL Agent
        agent = SmartSQLAgent(trae_config)
        
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
@click.option('--config', '-c', default='configs/config.yaml', help='配置文件路径')
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
        
        # 创建智能SQL Agent
        agent = SmartSQLAgent(trae_config)
        
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
@click.option('--config', '-c', default='configs/config.yaml', help='配置文件路径')
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
@click.option('--config', '-c', default='configs/config.yaml', help='配置文件路径')
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
@click.option('--config', '-c', default='configs/config.yaml', help='配置文件路径')
@click.option('--count', '-n', default=100, type=int, help='生成数据条数')
@click.option('--output', '-o', help='输出文件路径')
@click.option('--format', '-f', default='json', 
              type=click.Choice(['json', 'jsonl', 'csv', 'openai', 'huggingface']), 
              help='输出格式')
@click.option('--model', '-m', help='使用的LLM模型')
@click.option('--base-url', help='模型API基础URL')
@click.option('--api-key', help='模型API密钥')
@click.option('--host', help='数据库主机')
@click.option('--port', type=int, help='数据库端口')
@click.option('--user', help='数据库用户名')
@click.option('--password', help='数据库密码')
@click.option('--database', '-d', help='数据库名称')
@click.option('--verbose', '-v', is_flag=True, help='详细输出')
@click.option('--batch-size', default=10, type=int, help='批处理大小')
@click.option('--difficulty', default='mixed', 
              type=click.Choice(['easy', 'medium', 'hard', 'mixed']), 
              help='生成难度')
@click.pass_context
def generate(ctx, config: str, count: int, output: Optional[str], format: str,
            model: Optional[str], base_url: Optional[str], api_key: Optional[str],
            host: Optional[str], port: Optional[int], user: Optional[str],
            password: Optional[str], database: Optional[str], verbose: bool,
            batch_size: int, difficulty: str):
    """生成NL2SQL训练数据"""
    
    click.echo(f"🚀 开始生成 {count} 条NL2SQL训练数据...")
    click.echo("=" * 60)
    
    try:
        # 加载配置
        trae_config = TraeConfig.load_config(config)
        
        # 命令行参数覆盖配置
        if model:
            trae_config.llm.model = model
        if base_url:
            trae_config.llm.base_url = base_url
        if api_key:
            trae_config.llm.api_key = api_key
        if host:
            trae_config.database.host = host
        if port:
            trae_config.database.port = port
        if user:
            trae_config.database.username = user
        if password:
            trae_config.database.password = password
        if database:
            trae_config.database.database = database
        if verbose:
            trae_config.agent.verbose = True
            logging.getLogger().setLevel(logging.DEBUG)
        
        # 显示配置信息
        click.echo(f"📊 数据库: {trae_config.database.database}@{trae_config.database.host}:{trae_config.database.port}")
        click.echo(f"🤖 模型: {trae_config.llm.model}")
        click.echo(f"🎯 难度: {difficulty}")
        click.echo(f"📦 批处理大小: {batch_size}")
        click.echo()
        
        # 初始化数据库连接
        db_manager = DatabaseManager(trae_config.database)
        if not db_manager.initialize():
            click.echo("❌ 数据库连接失败", err=True)
            sys.exit(1)
        
        click.echo("✅ 数据库连接成功")
        
        # 使用增强版Agent生成数据
        from agent.enhanced_smart_sql_agent import EnhancedSmartSQLAgent
        agent = EnhancedSmartSQLAgent(trae_config)
        
        # 分批生成
        all_examples = []
        batches = (count + batch_size - 1) // batch_size  # 向上取整
        
        with click.progressbar(length=count, label='生成进度') as bar:
            for batch_idx in range(batches):
                batch_count = min(batch_size, count - batch_idx * batch_size)
                
                if verbose:
                    click.echo(f"\n处理批次 {batch_idx + 1}/{batches} ({batch_count} 条)...")
                
                # 调用同步方法
                examples = agent.generate_training_data(batch_count)
                
                all_examples.extend(examples)
                bar.update(batch_count)
        
        click.echo(f"\n✅ 生成完成! 成功生成 {len(all_examples)} 条数据")
        
        # 导出数据
        if output:
            # 设置导出的示例
            agent.generated_examples = all_examples
            
            # 根据格式导出
            if format == 'csv':
                # CSV格式需要特殊处理
                import csv
                from pathlib import Path
                
                output_path = Path(output)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(output_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=['question', 'sql', 'difficulty', 'quality_score'])
                    writer.writeheader()
                    for example in all_examples:
                        writer.writerow({
                            'question': example.question,
                            'sql': example.sql,
                            'difficulty': str(example.difficulty),
                            'quality_score': example.quality_score
                        })
            else:
                # 其他格式使用agent的导出方法
                export_data = agent.export_training_data(format)
                
                from pathlib import Path
                output_path = Path(output)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(export_data)
            
            click.echo(f"💾 数据已保存到: {output}")
        else:
            # 显示部分结果
            click.echo("\n📋 生成样例:")
            for i, example in enumerate(all_examples[:3], 1):
                click.echo(f"\n示例 {i}:")
                click.echo(f"  问题: {example.question}")
                click.echo(f"  SQL: {example.sql}")
                click.echo(f"  难度: {example.difficulty}")
                click.echo(f"  质量分数: {example.quality_score}")
            
            if len(all_examples) > 3:
                click.echo(f"\n... 还有 {len(all_examples) - 3} 条数据")
        
        # 显示统计信息
        if all_examples:
            avg_quality = sum(e.quality_score for e in all_examples) / len(all_examples)
            click.echo(f"\n📊 统计信息:")
            click.echo(f"  总数: {len(all_examples)}")
            click.echo(f"  平均质量分数: {avg_quality:.2f}")
            
            # 难度分布
            difficulty_dist = {}
            for e in all_examples:
                d = str(e.difficulty)
                difficulty_dist[d] = difficulty_dist.get(d, 0) + 1
            
            click.echo(f"  难度分布:")
            for d, c in difficulty_dist.items():
                click.echo(f"    {d}: {c} ({c*100/len(all_examples):.1f}%)")
        
        # 获取执行报告
        if verbose:
            report = agent.get_execution_report()
            report_file = output.replace('.json', '_report.md') if output else 'generation_report.md'
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)
            click.echo(f"\n📄 执行报告已保存到: {report_file}")
        
        db_manager.close()
        
    except Exception as e:
        click.echo(f"❌ 生成失败: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.argument("request", required=False, default="请分析这个数据库")
@click.option('--config', '-c', default='configs/config.yaml', help='配置文件路径')
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
        if result.get("success"):
            click.echo("✅ 智能分析完成!")
            click.echo(f"⏱️  总执行时间: {result.get('execution_time', 0):.2f}秒")
            click.echo(f"📈 完成步骤: {result.get('steps_taken', 0)}")
            click.echo()
            
            # 显示分析结果摘要
            if result.get("final_result"):
                _display_analysis_summary(result.get("final_result"))
            
            # 显示生成的场景问题（如果有）
            final_result = result.get("final_result", {})
            generated_scenarios = final_result.get("generated_scenarios", [])
            if generated_scenarios:
                click.echo("🎯 生成的查询场景:")
                for i, scenario in enumerate(generated_scenarios[:5], 1):
                    if isinstance(scenario, dict):
                        click.echo(f"  {i}. {scenario.get('name', '未命名场景')}")
                        if scenario.get('question'):
                            click.echo(f"     问题: {scenario['question']}")
                    else:
                        click.echo(f"  {i}. {scenario}")
                    click.echo()
            
        else:
            click.echo("❌ 智能分析失败")
            click.echo(f"错误: {result.get('error', '未知错误')}")
        
        # 保存结果
        if save_result:
            save_path = Path(save_result)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
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
    db_connection = result.get("database_connection")
    if db_connection:
        click.echo(f"📊 数据库: {db_connection.get('database', 'N/A')} ({db_connection.get('type', 'N/A')})")
        click.echo(f"📁 表数量: {db_connection.get('total_tables', 0)}")
    
    # 领域分析
    if result.get("domain_analysis"):
        click.echo(f"🏢 业务领域: 已识别")
    
    # 架构分析
    if result.get("schema_analysis"):
        click.echo(f"🏗️  架构分析: 已完成")
    
    # 查询结果
    query_results = result.get("query_results", [])
    if query_results:
        click.echo(f"📊 执行查询: {len(query_results)}个")
    
    # 数据洞察
    data_insights = result.get("data_insights", [])
    if data_insights:
        click.echo(f"💡 数据洞察: {len(data_insights)}个")
    
    # 分析摘要
    analysis_summary = result.get("analysis_summary", {})
    if analysis_summary.get("analysis_completed"):
        click.echo(f"✅ 分析状态: 已完成")
    
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