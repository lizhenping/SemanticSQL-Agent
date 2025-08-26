"""命令行参数解析器

兼容que_gen_ddd的参数格式
"""

import argparse
from typing import Dict, Any


DEFAULT_MODEL = "gpt-4"
DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_DATABASE_PORT = 3306


class ArgumentParser:
    """命令行参数解析器"""
    
    def __init__(self):
        self._parser = self._create_parser()
    
    def parse(self, args: list) -> Dict[str, Any]:
        """解析命令行参数并返回字典"""
        parsed_args = self._parser.parse_args(args)
        return vars(parsed_args)
    
    def _create_parser(self) -> argparse.ArgumentParser:
        """创建命令行参数解析器"""
        parser = argparse.ArgumentParser(
            description='NL2SQL问题生成工具',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
示例用法:
  %(prog)s --model "model_path" --host "localhost" --user "user" --password "pass" --database "db" generate --count 5
  %(prog)s --host "localhost" --user "user" --password "pass" --database "db" analyze
  %(prog)s cache list
            """
        )
        
        # 全局参数 - LLM配置
        parser.add_argument(
            '--model', 
            default=DEFAULT_MODEL,
            help=f'LLM模型名称 (默认: {DEFAULT_MODEL})'
        )
        parser.add_argument(
            '--api-key', 
            default='not-needed',
            help='API密钥 (默认: not-needed)'
        )
        parser.add_argument(
            '--base-url', 
            default=DEFAULT_BASE_URL,
            help=f'LLM服务基础URL (默认: {DEFAULT_BASE_URL})'
        )
        
        # 全局参数 - 数据库连接配置
        parser.add_argument(
            '--host', 
            help='数据库主机地址'
        )
        parser.add_argument(
            '--port', 
            type=int, 
            default=DEFAULT_DATABASE_PORT,
            help=f'数据库端口 (默认: {DEFAULT_DATABASE_PORT})'
        )
        parser.add_argument(
            '--user', 
            help='数据库用户名'
        )
        parser.add_argument(
            '--password', 
            help='数据库密码'
        )
        parser.add_argument(
            '--database', 
            help='数据库名称'
        )
        
        # 创建子命令
        subparsers = parser.add_subparsers(dest='command', help='可用命令')
        
        # generate 子命令
        self._add_generate_subcommand(subparsers)
        
        # analyze 子命令
        self._add_analyze_subcommand(subparsers)
        
        # cache 子命令
        self._add_cache_subcommand(subparsers)
        
        return parser
    
    def _add_generate_subcommand(self, subparsers):
        """添加generate子命令"""
        generate_parser = subparsers.add_parser('generate', help='生成SQL问题')
        generate_parser.add_argument(
            '--count', 
            type=int, 
            default=10,
            help='生成问题数量 (默认: 10)'
        )
        generate_parser.add_argument(
            '--output', 
            help='输出文件路径'
        )
        generate_parser.add_argument(
            '--use-existing-comments', 
            action='store_true',
            help='分析阶段使用数据库自带的注释进行ER分析'
        )
        generate_parser.add_argument(
            '--no-cache', 
            action='store_true',
            help='禁用缓存，强制重新分析'
        )
    
    def _add_analyze_subcommand(self, subparsers):
        """添加analyze子命令"""
        analyze_parser = subparsers.add_parser('analyze', help='分析数据库结构')
        analyze_parser.add_argument(
            '--output', 
            help='输出文件路径'
        )
        analyze_parser.add_argument(
            '--use-existing-comments', 
            action='store_true',
            help='分析完成后，使用数据库自带的注释覆盖生成结果'
        )
        analyze_parser.add_argument(
            '--no-cache', 
            action='store_true',
            help='禁用缓存，强制重新分析'
        )
    
    def _add_cache_subcommand(self, subparsers):
        """添加cache子命令"""
        cache_parser = subparsers.add_parser('cache', help='缓存管理')
        cache_subparsers = cache_parser.add_subparsers(dest='cache_command', help='缓存操作')
        
        # cache list
        cache_subparsers.add_parser('list', help='列出已缓存的数据库')
        
        # cache clear
        clear_parser = cache_subparsers.add_parser('clear', help='清除缓存')
        clear_parser.add_argument('database_name', help='要清除缓存的数据库名称')