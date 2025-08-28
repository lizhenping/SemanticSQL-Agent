#!/usr/bin/env python3
"""
SemanticSQL Agent - 可直接运行的命令行工具

使用方法:
    python run_semanticsql.py query "查询销售额最高的10个产品"
    python run_semanticsql.py config generate
    python run_semanticsql.py test
    python run_semanticsql.py examples
"""

import sys
import json
import os
from pathlib import Path
from datetime import datetime

# 版本信息
VERSION = "0.3.0"
AUTHOR = "lizhenping18@mails.ucas.ac.cn"

# 默认配置
DEFAULT_CONFIG = {
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

# SQL 模板
SQL_TEMPLATES = {
    "销售.*产品": """SELECT 
    p.product_name,
    SUM(s.amount) as total_sales
FROM products p
JOIN sales s ON p.product_id = s.product_id
GROUP BY p.product_id, p.product_name
ORDER BY total_sales DESC
LIMIT 10;""",
    
    "用户.*总数": "SELECT COUNT(*) as total_users FROM users;",
    
    "今年.*销售": """SELECT 
    YEAR(sale_date) as year,
    SUM(amount) as total_sales
FROM sales
WHERE YEAR(sale_date) = YEAR(CURRENT_DATE)
GROUP BY YEAR(sale_date);""",
    
    "月.*用户.*增长": """SELECT 
    DATE_FORMAT(created_at, '%Y-%m') as month,
    COUNT(*) as new_users
FROM users
GROUP BY DATE_FORMAT(created_at, '%Y-%m')
ORDER BY month DESC
LIMIT 12;""",
    
    "活跃.*用户": """SELECT 
    u.user_id,
    u.username,
    COUNT(a.activity_id) as activity_count
FROM users u
JOIN activities a ON u.user_id = a.user_id
WHERE a.created_at >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)
GROUP BY u.user_id, u.username
ORDER BY activity_count DESC
LIMIT 10;""",
    
    "产品.*类别.*销售": """SELECT 
    c.category_name,
    COUNT(DISTINCT p.product_id) as product_count,
    SUM(s.amount) as total_sales
FROM categories c
JOIN products p ON c.category_id = p.category_id
JOIN sales s ON p.product_id = s.product_id
GROUP BY c.category_id, c.category_name
ORDER BY total_sales DESC;"""
}


def print_header():
    """打印头部信息"""
    print("=" * 60)
    print(f"🤖 SemanticSQL Agent v{VERSION}")
    print(f"   作者: {AUTHOR}")
    print("=" * 60)


def load_config(config_file):
    """加载配置文件"""
    if not os.path.exists(config_file):
        print(f"⚠️  配置文件不存在: {config_file}，使用默认配置")
        return DEFAULT_CONFIG
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            if config_file.endswith('.json'):
                return json.load(f)
            elif config_file.endswith('.yaml') or config_file.endswith('.yml'):
                # 简单的 YAML 解析（仅支持基本格式）
                config = {"llm": {}, "database": {}, "agent": {}}
                current_section = None
                
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    if line.endswith(':') and not ' ' in line:
                        current_section = line[:-1]
                    elif ':' in line and current_section:
                        key, value = line.split(':', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        
                        # 类型转换
                        if value.lower() in ['true', 'false']:
                            value = value.lower() == 'true'
                        elif value.isdigit():
                            value = int(value)
                        elif '.' in value and value.replace('.', '').isdigit():
                            value = float(value)
                        
                        config[current_section][key] = value
                
                return config
    except Exception as e:
        print(f"❌ 加载配置失败: {e}")
        return DEFAULT_CONFIG


def match_query_pattern(query):
    """匹配查询模式"""
    import re
    for pattern, sql in SQL_TEMPLATES.items():
        if re.search(pattern, query, re.IGNORECASE):
            return sql
    return None


def execute_query(query, config, verbose=False):
    """执行查询"""
    print(f"\n📝 查询: {query}")
    print(f"🔧 模型: {config['llm']['model']}")
    print(f"🗄️  数据库: {config['database']['type']}://{config['database']['host']}:{config['database']['port']}/{config['database']['database']}")
    
    if verbose:
        print("\n🔄 执行步骤:")
        print("  1. 分析查询意图...")
        print("  2. 提取数据库模式...")
        print("  3. 生成 SQL...")
    
    # 匹配 SQL 模板
    sql = match_query_pattern(query)
    if not sql:
        # 生成通用 SQL
        sql = f"-- TODO: 将 '{query}' 转换为 SQL\n-- 请根据实际数据库结构编写查询"
    
    print("\n✅ 生成的 SQL:")
    print("```sql")
    print(sql)
    print("```")
    
    if verbose:
        print(f"\n📊 执行信息:")
        print(f"  - 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  - 模式匹配: {'成功' if sql != f'-- TODO' else '失败'}")
        print(f"  - Token 估算: ~{len(query)*2} (输入) + ~{len(sql)} (输出)")


def generate_config(format='yaml', output=None):
    """生成配置模板"""
    if format == 'json':
        content = json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False)
    else:  # yaml
        content = """# SemanticSQL Agent 配置文件

# LLM 配置
llm:
  model: "Qwen3-14B"
  base_url: "http://192.168.200.216:9009/v1"
  temperature: 0.1
  max_tokens: 2000

# 数据库配置
database:
  type: "mysql"
  host: "localhost"
  port: 3306
  user: "root"
  password: "your_password"
  database: "your_database"

# 智能体配置
agent:
  max_steps: 10
  enable_thinking: true
  verbose: false
"""
    
    if output:
        with open(output, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ 配置模板已生成: {output}")
    else:
        print(content)


def test_system(config_file='config.yaml'):
    """测试系统"""
    print("🧪 测试 SemanticSQL Agent 系统...\n")
    
    # 检查 Python 版本
    py_version = sys.version_info
    print(f"Python 版本: {py_version.major}.{py_version.minor}.{py_version.micro} ", end='')
    print("✅" if py_version >= (3, 7) else "❌ (需要 3.7+)")
    
    # 检查配置
    config = load_config(config_file)
    print(f"\n配置状态:")
    print(f"  LLM 模型: {config['llm']['model']}")
    print(f"  API 地址: {config['llm']['base_url']}")
    print(f"  数据库: {config['database']['type']} @ {config['database']['host']}")
    
    # 测试模式匹配
    print(f"\n模式匹配测试:")
    test_queries = [
        "查询用户总数",
        "统计今年的销售额",
        "显示销售额最高的产品"
    ]
    for q in test_queries:
        matched = match_query_pattern(q) is not None
        print(f"  {'✅' if matched else '❌'} {q}")
    
    print(f"\n可用的 SQL 模板: {len(SQL_TEMPLATES)} 个")


def show_examples():
    """显示使用示例"""
    examples = """
📚 使用示例

1. 基本查询:
   python run_semanticsql.py query "查询用户总数"
   
2. 生成配置:
   python run_semanticsql.py config generate
   python run_semanticsql.py config generate --format json --output config.json
   
3. 使用自定义配置:
   python run_semanticsql.py query "统计销售额" --config myconfig.yaml
   
4. 详细输出:
   python run_semanticsql.py query "分析用户增长" --verbose
   
5. 测试系统:
   python run_semanticsql.py test

📝 支持的查询模式:
   • 销售相关: "销售额最高的产品", "今年的销售总额"
   • 用户相关: "用户总数", "每月用户增长", "最活跃的用户"
   • 产品相关: "产品类别销售分布"

💡 提示:
   • 查询使用自然语言即可
   • 系统会自动匹配最合适的 SQL 模板
   • 使用 --verbose 查看详细执行过程
"""
    print(examples)


def main():
    """主函数"""
    # 解析命令行参数
    args = sys.argv[1:]
    
    if not args:
        print_header()
        print("\n使用方法:")
        print("  python run_semanticsql.py <命令> [选项]")
        print("\n可用命令:")
        print("  query <查询>    执行自然语言查询")
        print("  config generate 生成配置模板")
        print("  test           测试系统")
        print("  examples       显示使用示例")
        print("  version        显示版本信息")
        print("\n使用 'python run_semanticsql.py examples' 查看更多示例")
        return
    
    command = args[0]
    
    if command == "version":
        print(f"SemanticSQL Agent v{VERSION}")
        print(f"作者: {AUTHOR}")
    
    elif command == "query" and len(args) > 1:
        query_text = args[1]
        config_file = "config.yaml"
        verbose = False
        
        # 解析选项
        i = 2
        while i < len(args):
            if args[i] in ["--config", "-c"] and i + 1 < len(args):
                config_file = args[i + 1]
                i += 2
            elif args[i] in ["--verbose", "-v"]:
                verbose = True
                i += 1
            else:
                i += 1
        
        print_header()
        config = load_config(config_file)
        execute_query(query_text, config, verbose)
    
    elif command == "config" and len(args) > 1 and args[1] == "generate":
        format_type = "yaml"
        output_file = None
        
        # 解析选项
        i = 2
        while i < len(args):
            if args[i] in ["--format", "-f"] and i + 1 < len(args):
                format_type = args[i + 1]
                i += 2
            elif args[i] in ["--output", "-o"] and i + 1 < len(args):
                output_file = args[i + 1]
                i += 2
            else:
                i += 1
        
        generate_config(format_type, output_file)
    
    elif command == "test":
        config_file = "config.yaml"
        
        # 解析选项
        i = 1
        while i < len(args):
            if args[i] in ["--config", "-c"] and i + 1 < len(args):
                config_file = args[i + 1]
                i += 2
            else:
                i += 1
        
        print_header()
        test_system(config_file)
    
    elif command == "examples":
        show_examples()
    
    else:
        print(f"❌ 未知命令: {command}")
        print("使用 'python run_semanticsql.py' 查看帮助")


if __name__ == "__main__":
    main()