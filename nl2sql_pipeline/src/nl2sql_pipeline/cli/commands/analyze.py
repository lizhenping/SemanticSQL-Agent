"""分析命令处理器

负责处理数据库分析相关的命令
"""

import json
from typing import Dict, Any
from pathlib import Path

from .base import Command, CommandResult
from ...workflows.main_workflow import MainWorkflow
from ...config.database import DatabaseConfig
from ...utils.file_utils import ensure_directory_exists


class AnalyzeCommand(Command):
    """分析命令处理器"""
    
    def __init__(self, workflow: MainWorkflow, **kwargs):
        """初始化分析命令
        
        Args:
            workflow: 主工作流实例
            **kwargs: 其他参数传递给基类
        """
        super().__init__(**kwargs)
        self.workflow = workflow
    
    def execute(self, args: Dict[str, Any]) -> CommandResult:
        """执行分析命令
        
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
            # 获取分析参数
            use_cache = not args.get('no_cache', False)
            output_file = args.get('output')
            
            self.logger.info(f"开始分析数据库: {args['database']}")
            
            # 执行分析
            analysis_result = self.workflow.analyze_database(
                database_name=args['database'],
                database_config=db_config.to_dict(),
                use_cache=use_cache
            )
            
            # 记录分析结果
            self.logger.info("分析完成")
            self.logger.info(f"- 表数量: {len(analysis_result.database_schema.tables)}")
            self.logger.info(f"- 领域类型: {analysis_result.domain_knowledge.domain_type}")
            
            # 准备输出数据
            output_data = self._prepare_output_data(analysis_result)
            
            # 如果指定了输出文件，保存分析结果
            if output_file:
                self._save_analysis_result(output_file, output_data)
                self.logger.info(f"分析结果已保存到: {output_file}")
            
            return CommandResult(
                success=True,
                message="数据库分析完成",
                data=output_data
            )
            
        except Exception as e:
            self.logger.error(f"分析命令执行失败: {e}", exc_info=True)
            return CommandResult(
                success=False,
                message=f"分析命令执行失败: {str(e)}",
                exit_code=1
            )
    
    def _prepare_output_data(self, analysis_result) -> Dict[str, Any]:
        """准备输出数据
        
        Args:
            analysis_result: 分析结果对象
            
        Returns:
            格式化的输出数据字典
        """
        return {
            'database_name': analysis_result.database_name,
            'timestamp': analysis_result.analysis_timestamp.isoformat(),
            'domain': {
                'type': analysis_result.domain_knowledge.domain_type,
                'description': analysis_result.domain_knowledge.description
            },
            'tables': len(analysis_result.database_schema.tables),
            'columns': sum(
                len(t.columns) for t in analysis_result.database_schema.tables
            )
        }
    
    def _save_analysis_result(self, output_file: str, data: Dict[str, Any]) -> None:
        """保存分析结果到文件
        
        Args:
            output_file: 输出文件路径
            data: 要保存的数据
        """
        output_path = Path(output_file)
        ensure_directory_exists(output_path, is_file_path=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)