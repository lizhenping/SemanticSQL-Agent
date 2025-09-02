"""缓存命令处理器

负责处理缓存管理相关的命令
"""

import os
from typing import Dict, Any

from .base import Command, CommandResult
from ...workflows.main_workflow import MainWorkflow


class CacheCommand(Command):
    """缓存命令处理器"""
    
    def __init__(self, workflow: MainWorkflow, **kwargs):
        """初始化缓存命令
        
        Args:
            workflow: 主工作流实例
            **kwargs: 其他参数传递给基类
        """
        super().__init__(**kwargs)
        self.workflow = workflow
    
    def execute(self, args: Dict[str, Any]) -> CommandResult:
        """执行缓存命令
        
        Args:
            args: 命令参数
            
        Returns:
            CommandResult: 执行结果
        """
        cache_command = args.get('cache_command')
        
        if not cache_command:
            return CommandResult(
                success=False,
                message="请指定缓存操作命令 (list, clear)",
                exit_code=1
            )
        
        if cache_command == 'list':
            return self._list_cache()
        elif cache_command == 'clear':
            return self._clear_cache(args)
        else:
            return CommandResult(
                success=False,
                message=f"未知的缓存命令: {cache_command}",
                exit_code=1
            )
    
    def _list_cache(self) -> CommandResult:
        """列出缓存的数据库
        
        Returns:
            CommandResult: 执行结果
        """
        try:
            cache_dir = self.workflow.cache_dir
            databases = []
            
            if os.path.exists(cache_dir):
                files = os.listdir(cache_dir)
                for f in files:
                    if f.endswith('_analysis.pkl'):
                        db_name = f.replace('_analysis.pkl', '')
                        databases.append(db_name)
            
            if databases:
                message_lines = ["已缓存的数据库:"]
                for db in sorted(databases):
                    message_lines.append(f"  - {db}")
                message = "\n".join(message_lines)
                
                # 同时输出到控制台
                print(message)
            else:
                message = "没有缓存的数据库"
                print(message)
            
            return CommandResult(
                success=True,
                message=message,
                data={'databases': databases}
            )
            
        except Exception as e:
            self.logger.error(f"列出缓存失败: {e}", exc_info=True)
            return CommandResult(
                success=False,
                message=f"列出缓存失败: {str(e)}",
                exit_code=1
            )
    
    def _clear_cache(self, args: Dict[str, Any]) -> CommandResult:
        """清除缓存
        
        Args:
            args: 命令参数
            
        Returns:
            CommandResult: 执行结果
        """
        db_name = args.get('database_name')
        
        if not db_name:
            return CommandResult(
                success=False,
                message="请指定要清除缓存的数据库名称",
                exit_code=1
            )
        
        try:
            self.workflow.clear_cache(db_name)
            message = f"已清除 {db_name} 的缓存"
            print(message)
            
            return CommandResult(
                success=True,
                message=message
            )
            
        except Exception as e:
            self.logger.error(f"清除缓存失败: {e}", exc_info=True)
            return CommandResult(
                success=False,
                message=f"清除缓存失败: {str(e)}",
                exit_code=1
            )