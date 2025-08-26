"""命令注册器

负责管理和分发命令
"""

from typing import Dict, Type, Optional
import logging

from .commands.base import Command, CommandResult


class CommandRegistry:
    """命令注册器
    
    负责注册、查找和执行命令
    """
    
    def __init__(self, workflow: 'MainWorkflow', logger: Optional[logging.Logger] = None):
        """初始化命令注册器
        
        Args:
            workflow: 主工作流实例
            logger: 日志记录器
        """
        self.workflow = workflow
        self.logger = logger or logging.getLogger(__name__)
        self._commands: Dict[str, Type[Command]] = {}
        self._register_default_commands()
    
    def _register_default_commands(self) -> None:
        """注册默认命令"""
        # 延迟导入以避免循环依赖
        from .commands.analyze import AnalyzeCommand
        from .commands.generate import GenerateCommand
        from .commands.cache import CacheCommand
        
        self.register('analyze', AnalyzeCommand)
        self.register('generate', GenerateCommand)
        self.register('cache', CacheCommand)
    
    def register(self, name: str, command_class: Type[Command]) -> None:
        """注册命令
        
        Args:
            name: 命令名称
            command_class: 命令类
        """
        self._commands[name] = command_class
        self.logger.debug(f"注册命令: {name} -> {command_class.__name__}")
    
    def get_command(self, name: str) -> Optional[Command]:
        """获取命令实例
        
        Args:
            name: 命令名称
            
        Returns:
            命令实例，如果命令不存在返回None
        """
        command_class = self._commands.get(name)
        if command_class:
            return command_class(workflow=self.workflow, logger=self.logger)
        return None
    
    def execute(self, command_name: str, args: Dict) -> CommandResult:
        """执行命令
        
        Args:
            command_name: 命令名称
            args: 命令参数
            
        Returns:
            CommandResult: 执行结果
        """
        command = self.get_command(command_name)
        
        if not command:
            available_commands = ', '.join(self._commands.keys())
            return CommandResult(
                success=False,
                message=f"未知命令: {command_name}。可用命令: {available_commands}",
                exit_code=1
            )
        
        self.logger.info(f"执行命令: {command_name}")
        return command.execute(args)
    
    def list_commands(self) -> list:
        """列出所有可用命令
        
        Returns:
            命令名称列表
        """
        return list(self._commands.keys())