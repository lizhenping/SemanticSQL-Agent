#!/usr/bin/env python3
"""SemanticSQL Agent 工作版 CLI"""

import json
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# 尝试导入必要的模块
try:
    import click
except ImportError:
    print("错误: 需要安装 click: pip install click")
    sys.exit(1)

try:
    import yaml
except ImportError:
    yaml = None
    logger.warning("警告: PyYAML 未安装，将无法使用 YAML 配置文件")

# 内部导入 - 使用绝对导入
sys.path.insert(0, str(Path(__file__).parent))

try:
    from utils.config import Config, LLMConfig, DatabaseConfig, AgentConfig
    from utils.llm_clients import LLMClient, LLMMessage
    from agent.sql_agent import SQLAgent
    IMPORTS_OK = True
except ImportError as e:
    logger.warning(f"警告: 部分模块导入失败 ({e})，将使用模拟模式")
    IMPORTS_OK = False
    
    # 定义模拟类
    from dataclasses import dataclass, field
    
    @dataclass
    class LLMConfig:
        model: str = "Qwen3-14B"
        base_url: str = "http://192.168.200.216:9009/v1"
        temperature: float = 0.1
        max_tokens: int = 2000
    
    @dataclass
    class DatabaseConfig:
        type: str = "mysql"
        host: str = "localhost"
        port: int = 3306
        user: str = "root"
        password: str = ""
        database: str = "test"
    
    @dataclass
    class AgentConfig:
        max_steps: int = 10
        enable_thinking: bool = True
        verbose: bool = False
    
    @dataclass
    class Config:
        llm: LLMConfig = field(default_factory=LLMConfig)
        database: DatabaseConfig = field(default_factory=DatabaseConfig)
        agent: AgentConfig = field(default_factory=AgentConfig)
        
        @classmethod
        def from_dict(cls, data: dict) -> 'Config':
            return cls(
                llm=LLMConfig(**data.get('llm', {})),
                database=DatabaseConfig(**data.get('database', {})),
                agent=AgentConfig(**data.get('agent', {}))
            )


def load_config(config_file: str) -> Config:
    """加载配置文件"""
    config_path = Path(config_file)
    
    if not config_path.exists():
        click.echo(f"错误: 配置文件不存在: {config_file}", err=True)
        sys.exit(1)
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            if config_file.endswith('.yaml') or config_file.endswith('.yml'):
                if yaml is None:
                    click.echo("错误: 需要安装 PyYAML 来读取 YAML 文件: pip install pyyaml", err=True)
                    sys.exit(1)
                data = yaml.safe_load(f)
            elif config_file.endswith('.json'):
                data = json.load(f)
            else:
                click.echo("错误: 配置文件必须是 .yaml/.yml 或 .json 格式", err=True)
                sys.exit(1)
        
        return Config.from_dict(data)
    except Exception as e:
        click.echo(f"错误: 加载配置文件失败: {e}", err=True)
        sys.exit(1)


def simulate_query(query: str, config: Config):
    """模拟查询（当无法导入真实模块时）"""
    click.echo("\n" + "="*60)
    click.echo("🤖 SemanticSQL Agent (模拟模式)")
    click.echo("="*60)
    
    click.echo(f"\n📝 查询: {query}")
    click.echo(f"🔧 模型: {config.llm.model}")
    click.echo(f"🗄️  数据库: {config.database.type}://{config.database.host}/{config.database.database}")
    
    # 模拟生成 SQL
    click.echo("\n✅ 生成的 SQL:")
    if "销售额" in query and "产品" in query:
        sql = """SELECT 
    p.product_name,
    SUM(s.amount) as total_sales
FROM products p
JOIN sales s ON p.product_id = s.product_id
GROUP BY p.product_id, p.product_name
ORDER BY total_sales DESC
LIMIT 10;"""
    elif "用户" in query and "总数" in query:
        sql = "SELECT COUNT(*) as total_users FROM users;"
    else:
        sql = f"-- 将 '{query}' 转换为 SQL"
    
    click.echo(f"```sql\n{sql}\n```")
    click.echo("\n" + "="*60)


@click.group()
@click.version_option(version="0.3.0")
def cli():
    """SemanticSQL Agent - 简化的 NL2SQL 智能体
    
    将自然语言查询转换为 SQL 语句。
    """
    pass


@cli.command()
@click.argument("query")
@click.option("--config", "-c", "config_file", default="config.yaml", help="配置文件路径")
@click.option("--verbose", "-v", is_flag=True, help="详细输出")
@click.option("--rich", is_flag=True, help="使用 Rich 界面")
def query(query: str, config_file: str, verbose: bool, rich: bool):
    """执行自然语言查询"""
    # 加载配置
    config = load_config(config_file) if Path(config_file).exists() else Config()
    
    if IMPORTS_OK:
        try:
            # 创建 LLM 客户端
            llm_client = LLMClient(
                model=config.llm.model,
                base_url=config.llm.base_url,
                temperature=config.llm.temperature,
                max_tokens=config.llm.max_tokens
            )
            
            # 创建智能体
            agent = SQLAgent(config=config, llm_client=llm_client)
            
            # 执行查询
            click.echo(f"\n🔍 处理查询: {query}")
            result = agent.run(query)
            
            # 显示结果
            click.echo("\n✅ 生成的 SQL:")
            click.echo(f"```sql\n{result.sql}\n```")
            
            if result.explanation:
                click.echo(f"\n📖 解释: {result.explanation}")
                
        except Exception as e:
            click.echo(f"\n❌ 错误: {e}", err=True)
            # 降级到模拟模式
            simulate_query(query, config)
    else:
        # 使用模拟模式
        simulate_query(query, config)


@cli.group()
def config():
    """配置管理命令"""
    pass


@config.command()
@click.option("--format", "-f", type=click.Choice(["yaml", "json"]), default="yaml", help="配置文件格式")
@click.option("--output", "-o", help="输出文件路径")
def generate(format: str, output: Optional[str]):
    """生成配置模板"""
    template_data = {
        "llm": {
            "model": "Qwen3-14B",
            "base_url": "http://192.168.200.216:9009/v1",
            "temperature": 0.1,
            "max_tokens": 2000
        },
        "database": {
            "type": "mysql",
            "host": "localhost",
            "port": 3306,
            "user": "root",
            "password": "your_password",
            "database": "your_database"
        },
        "agent": {
            "max_steps": 10,
            "enable_thinking": True,
            "verbose": False
        }
    }
    
    if format == "yaml":
        if yaml is None:
            click.echo("错误: 需要安装 PyYAML: pip install pyyaml", err=True)
            return
        content = yaml.dump(template_data, default_flow_style=False, allow_unicode=True, sort_keys=False)
    else:
        content = json.dumps(template_data, indent=2, ensure_ascii=False)
    
    if output:
        with open(output, 'w', encoding='utf-8') as f:
            f.write(content)
        click.echo(f"✅ 配置模板已生成: {output}")
    else:
        click.echo(content)


@cli.command()
@click.option("--config", "-c", "config_file", default="config.yaml", help="配置文件路径")
def test(config_file: str):
    """测试连接和配置"""
    click.echo("🧪 测试 SemanticSQL Agent...")
    
    # 检查配置文件
    if Path(config_file).exists():
        try:
            config = load_config(config_file)
            click.echo(f"✅ 配置文件加载成功: {config_file}")
        except Exception as e:
            click.echo(f"❌ 配置文件加载失败: {e}", err=True)
            config = Config()
    else:
        click.echo(f"⚠️  配置文件不存在，使用默认配置")
        config = Config()
    
    # 测试组件
    click.echo("\n组件状态:")
    click.echo(f"  {'✅' if IMPORTS_OK else '❌'} 核心模块")
    click.echo(f"  {'✅' if yaml is not None else '⚠️'} YAML 支持")
    
    if IMPORTS_OK:
        try:
            # 测试 LLM 连接
            from utils.llm_clients import LLMClient
            client = LLMClient(
                model=config.llm.model,
                base_url=config.llm.base_url
            )
            click.echo(f"  ✅ LLM 客户端 ({config.llm.model})")
        except Exception as e:
            click.echo(f"  ❌ LLM 客户端: {e}")
    else:
        click.echo("  ⚠️  运行在模拟模式")
    
    click.echo(f"\n配置信息:")
    click.echo(f"  模型: {config.llm.model}")
    click.echo(f"  API: {config.llm.base_url}")
    click.echo(f"  数据库: {config.database.type}://{config.database.host}:{config.database.port}/{config.database.database}")


@cli.command()
def examples():
    """显示使用示例"""
    examples_text = """
📚 SemanticSQL Agent 使用示例

1. 生成配置文件:
   $ semanticsql config generate -o config.yaml
   
2. 执行查询:
   $ semanticsql query "查询销售额最高的10个产品" -c config.yaml
   
3. 使用详细模式:
   $ semanticsql query "统计每月用户增长" -v
   
4. 测试连接:
   $ semanticsql test -c config.yaml

5. 常见查询示例:
   - "查询用户总数"
   - "统计今年的销售总额"
   - "找出最活跃的10个用户"
   - "分析产品类别的销售分布"
   
6. 配置文件示例 (config.yaml):
   llm:
     model: "Qwen3-14B"
     base_url: "http://192.168.200.216:9009/v1"
   database:
     type: "mysql"
     host: "localhost"
     database: "sales_db"
"""
    click.echo(examples_text)


def main():
    """主入口"""
    try:
        cli()
    except Exception as e:
        click.echo(f"错误: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()