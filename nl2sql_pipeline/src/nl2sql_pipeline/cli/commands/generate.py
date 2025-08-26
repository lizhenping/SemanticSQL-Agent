"""生成命令处理器

负责处理问题生成相关的命令
"""

import os
from typing import Dict, Any
from pathlib import Path

from .base import Command, CommandResult
from ...workflows.main_workflow import MainWorkflow
from ...config.database import DatabaseConfig
from ...utils.file_utils import ensure_directory_exists, copy_file_safely, get_output_directory


class GenerateCommand(Command):
    """生成命令处理器"""
    
    def __init__(self, workflow: MainWorkflow, **kwargs):
        """初始化生成命令
        
        Args:
            workflow: 主工作流实例
            **kwargs: 其他参数传递给基类
        """
        super().__init__(**kwargs)
        self.workflow = workflow
    
    def execute(self, args: Dict[str, Any]) -> CommandResult:
        """执行生成命令
        
        Args:
            args: 命令参数
            
        Returns:
            CommandResult: 执行结果
        """
        # 验证必要参数
        db_config = DatabaseConfig.from_args(args)
        if not db_config.validate():
            missing = db_config.get_missing_fields()
            return CommandResult(
                success=False,
                message=f"缺少必要的数据库连接参数: {', '.join(missing)}",
                exit_code=1
            )
        
        try:
            # 获取生成参数
            count = args.get('count', 100)
            output = args.get('output')
            use_cache = not args.get('no_cache', False)
            
            # 确保输出目录存在
            output_dir = get_output_directory(output, 'output')
            ensure_directory_exists(output_dir)
            
            self.logger.info(f"开始生成问题，目标数量: {count}")
            
            # 执行生成流程
            result = self.workflow.run_complete_pipeline(
                database_name=args['database'],
                database_config=db_config.to_dict(),
                target_count=count,
                output_dir=output_dir,
                use_cache=use_cache
            )
            
            # 如果指定了输出文件，复制到指定位置
            if output:
                questions_file = result['summary']['output_files']['questions']
                copy_file_safely(questions_file, output)
                self.logger.info(f"问题已保存到: {output}")
            
            return CommandResult(
                success=True,
                message=f"成功生成 {result['summary']['generation']['actual_count']} 个问题",
                data=result
            )
            
        except Exception as e:
            self.logger.error(f"生成命令执行失败: {e}", exc_info=True)
            return CommandResult(
                success=False,
                message=f"生成命令执行失败: {str(e)}",
                exit_code=1
            )