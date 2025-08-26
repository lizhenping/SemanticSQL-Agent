"""应用程序核心模块

包含应用程序的主要逻辑，独立于命令行入口
"""

import sys
import logging
from typing import List, Optional

from .cli import ArgumentParser
from .config import setup_logging, EnvironmentConfig


class NL2SQLApplication:
    """NL2SQL Pipeline 应用程序
    
    负责协调各个组件，执行命令行操作
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """初始化应用程序
        
        Args:
            logger: 可选的日志记录器
        """
        self.logger = logger
        self.env_config = None
        self.workflow = None
        self.command_registry = None
        self._initialized = False
    
    def initialize(self, setup_logging_enabled: bool = True):
        """初始化应用程序环境
        
        Args:
            setup_logging_enabled: 是否设置日志配置
        """
        if self._initialized:
            return
        
        # 1. 设置日志（如果需要）
        if setup_logging_enabled:
            setup_logging()
        
        # 2. 设置logger（如果未提供）
        if not self.logger:
            self.logger = logging.getLogger(__name__)
        
        # 3. 初始化环境配置管理器
        self.env_config = EnvironmentConfig(self.logger)
        
        # 4. 创建主工作流
        from .workflows.main_workflow import MainWorkflow
        self.workflow = MainWorkflow()
        
        # 5. 创建命令注册器
        from .cli.command_registry import CommandRegistry
        self.command_registry = CommandRegistry(self.workflow, self.logger)
        
        self._initialized = True
        self.logger.info("应用程序初始化完成")
    
    def run(self, argv: List[str]) -> int:
        """运行应用程序
        
        Args:
            argv: 命令行参数列表（不包含程序名）
            
        Returns:
            退出码
        """
        # 确保已初始化
        if not self._initialized:
            self.initialize()
        
        # 解析命令行参数
        arg_parser = ArgumentParser()
        args_dict = arg_parser.parse(argv)
        
        # 验证命令
        command = args_dict.get('command')
        if not command:
            print("错误: 请指定一个命令 (generate, analyze, cache)", file=sys.stderr)
            print("错误: 使用 --help 查看帮助信息", file=sys.stderr)
            return 1
        
        # 配置环境变量
        self.env_config.configure_from_args(args_dict)
        
        # 执行命令
        self.logger.info(f"执行命令: {command}")
        result = self.command_registry.execute(command, args_dict)
        
        if result.success:
            self.logger.info("命令执行完成")
        else:
            print(f"错误: {result.message}", file=sys.stderr)
        
        return result.exit_code
    
