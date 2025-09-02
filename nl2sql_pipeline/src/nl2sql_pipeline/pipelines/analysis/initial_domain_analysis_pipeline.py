"""初始领域分析管道（优化版）

对数据库进行初步的业务领域分析，识别核心概念和关系。
参考 que_gen_ddd 的 LLMDatabaseDomainService 实现。

优化要点：
1. 使用类型安全的ServiceContainer
2. 拆分长方法
3. 移除过度的异常处理
4. 改进代码组织
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import json
import os

from ..base import Pipeline, PipelineStep
from ...models.database import DatabaseSchema, TableInfo, ColumnInfo
from ...models.analysis import DomainKnowledge
from ...services import ServiceContainer
from ...services.database_service import DatabaseService
from ...services.llm_service import LLMService
from ...services.prompt_service import PromptService

logger = logging.getLogger(__name__)


# ========== 导入上下文模型 ==========

from ...models.pipeline_contexts import DomainAnalysisContext


# ========== 管道步骤定义 ==========

class FormatDatabaseDDLStep(PipelineStep[DomainAnalysisContext]):
    """格式化数据库DDL步骤
    
    将数据库结构格式化为DDL语句，供LLM理解。
    """
    
    def __init__(self):
        """初始化步骤"""
        super().__init__("格式化数据库DDL")
    
    def execute(self, context: DomainAnalysisContext) -> DomainAnalysisContext:
        """执行DDL格式化"""
        logger.info("格式化数据库DDL")
        
        ddl_lines = []
        for table in context.database_schema.tables:
            ddl_lines.extend(self._format_table_ddl(table))
            ddl_lines.append("")  # 空行分隔
        
        context.database_ddl = "\n".join(ddl_lines)
        logger.debug(f"生成DDL长度: {len(context.database_ddl)} 字符")
        
        return context
    
    def _format_table_ddl(self, table: TableInfo) -> List[str]:
        """格式化单个表的DDL"""
        lines = [f"CREATE TABLE `{table.name}` ("]
        
        # 列定义
        column_defs = self._format_column_definitions(table)
        
        # 主键
        pk_def = self._format_primary_key(table)
        if pk_def:
            column_defs.append(pk_def)
        
        # 外键
        column_defs.extend(self._format_foreign_keys(table))
        
        lines.append(",\n".join(column_defs))
        
        # 表定义结束
        lines.append(self._format_table_suffix(table))
        
        return lines
    
    def _format_column_definitions(self, table: TableInfo) -> List[str]:
        """格式化列定义"""
        column_defs = []
        for col in table.columns:
            col_def = f"  `{col.name}` {col.data_type}"
            if not col.is_nullable:
                col_def += " NOT NULL"
            if col.default_value:
                col_def += f" DEFAULT {col.default_value}"
            # 移除 comment 注入，避免将数据库注释传递给 LLM
            # if col.comment:
            #     col_def += f" COMMENT '{col.comment}'"
            column_defs.append(col_def)
        return column_defs
    
    def _format_primary_key(self, table: TableInfo) -> Optional[str]:
        """格式化主键定义"""
        pk_cols = [col.name for col in table.columns if col.is_primary_key]
        if pk_cols:
            return f"  PRIMARY KEY ({', '.join(f'`{c}`' for c in pk_cols)})"
        return None
    
    def _format_foreign_keys(self, table: TableInfo) -> List[str]:
        """格式化外键定义"""
        fk_defs = []
        for fk in table.foreign_keys:
            fk_def = (f"  FOREIGN KEY (`{fk['column']}`) "
                     f"REFERENCES `{fk['referenced_table']}` (`{fk['referenced_column']}`)")
            fk_defs.append(fk_def)
        return fk_defs
    
    def _format_table_suffix(self, table: TableInfo) -> str:
        """格式化表定义后缀"""
        suffix = ")"
        # 移除表级 comment 注入，避免将数据库注释传递给 LLM
        # if table.comment:
        #     suffix += f" COMMENT='{table.comment}'"
        suffix += ";"
        return suffix


class CollectTableSummariesStep(PipelineStep[DomainAnalysisContext]):
    """收集表摘要步骤
    
    收集每个表的基本信息摘要。
    """
    
    def __init__(self, database_service: DatabaseService):
        """初始化步骤"""
        super().__init__("收集表摘要")
        self.db_service = database_service
    
    def execute(self, context: DomainAnalysisContext) -> DomainAnalysisContext:
        """执行表摘要收集"""
        logger.info("收集表摘要信息")
        
        for table in context.database_schema.tables:
            context.table_summaries[table.name] = self._create_table_summary(table)
        
        logger.info(f"收集了 {len(context.table_summaries)} 个表的摘要")
        return context
    
    def _create_table_summary(self, table: TableInfo) -> str:
        """创建单个表的摘要"""
        # 获取基本信息
        row_count = self._get_table_row_count(table.name)
        pk_info = self._get_primary_key_info(table)
        fk_info = self._get_foreign_key_info(table)
        col_stats = self._get_column_stats(table)
        
        # 构建摘要
        summary_parts = [
            f"表名: {table.name}",
            f"行数: {row_count}",
            f"列数: {col_stats['total']} (可空: {col_stats['nullable']})",
            pk_info,
            fk_info
        ]
        
        # 移除表注释信息，避免将数据库注释传递给 LLM
        # if table.comment:
        #     summary_parts.append(f"注释: {table.comment}")
        
        return "\n".join(summary_parts)
    
    def _get_table_row_count(self, table_name: str) -> int:
        """获取表行数"""
        # 移除try-except，让异常自然传播
        return self.db_service.get_table_row_count(table_name)
    
    def _get_primary_key_info(self, table: TableInfo) -> str:
        """获取主键信息"""
        pk_cols = [col.name for col in table.columns if col.is_primary_key]
        return f"主键: {', '.join(pk_cols)}" if pk_cols else "无主键"
    
    def _get_foreign_key_info(self, table: TableInfo) -> str:
        """获取外键信息"""
        fk_count = len(table.foreign_keys)
        return f"{fk_count}个外键" if fk_count > 0 else "无外键"
    
    def _get_column_stats(self, table: TableInfo) -> Dict[str, int]:
        """获取列统计信息"""
        return {
            'total': len(table.columns),
            'nullable': sum(1 for col in table.columns if col.is_nullable)
        }


class CollectFieldStatisticsStep(PipelineStep[DomainAnalysisContext]):
    """收集字段统计步骤
    
    收集字段类型分布等统计信息。
    """
    
    def __init__(self):
        """初始化步骤"""
        super().__init__("收集字段统计")
    
    def execute(self, context: DomainAnalysisContext) -> DomainAnalysisContext:
        """执行字段统计"""
        logger.info("收集字段统计信息")
        
        type_stats = {}
        pattern_stats = self._init_pattern_stats()
        
        # 收集统计信息
        for table in context.database_schema.tables:
            for col in table.columns:
                self._update_type_stats(type_stats, col)
                self._update_pattern_stats(pattern_stats, table.name, col)
        
        # 保存结果
        context.field_statistics = self._prepare_statistics(type_stats, pattern_stats)
        logger.info(f"字段类型分布: {type_stats}")
        
        return context
    
    def _init_pattern_stats(self) -> Dict[str, List[str]]:
        """初始化模式统计"""
        return {
            'id_fields': [],      # ID类字段
            'date_fields': [],    # 日期时间字段
            'status_fields': [],  # 状态字段
            'amount_fields': [],  # 金额字段
            'count_fields': []    # 计数字段
        }
    
    def _update_type_stats(self, type_stats: Dict[str, int], col: ColumnInfo) -> None:
        """更新类型统计"""
        data_type = col.data_type.upper()
        base_type = data_type.split('(')[0]  # 去除长度信息
        type_stats[base_type] = type_stats.get(base_type, 0) + 1
    
    def _update_pattern_stats(self, pattern_stats: Dict[str, List[str]], 
                            table_name: str, col: ColumnInfo) -> None:
        """更新模式统计"""
        col_name_lower = col.name.lower()
        field_key = f"{table_name}.{col.name}"
        
        # ID字段
        if col.is_primary_key or col_name_lower.endswith('_id') or col_name_lower == 'id':
            pattern_stats['id_fields'].append(field_key)
        
        # 日期时间字段
        if any(kw in col_name_lower for kw in ['date', 'time', 'created', 'updated']):
            pattern_stats['date_fields'].append(field_key)
        
        # 状态字段
        if any(kw in col_name_lower for kw in ['status', 'state', 'type']):
            pattern_stats['status_fields'].append(field_key)
        
        # 金额字段
        if any(kw in col_name_lower for kw in ['amount', 'price', 'cost', 'fee']):
            pattern_stats['amount_fields'].append(field_key)
        
        # 计数字段
        if any(kw in col_name_lower for kw in ['count', 'num', 'qty', 'quantity']):
            pattern_stats['count_fields'].append(field_key)
    
    def _prepare_statistics(self, type_stats: Dict[str, int], 
                          pattern_stats: Dict[str, List[str]]) -> Dict[str, Any]:
        """准备统计结果"""
        return {
            'type_distribution': type_stats,
            'patterns': {k: len(v) for k, v in pattern_stats.items()},
            'pattern_examples': {k: v[:3] for k, v in pattern_stats.items()}  # 每种模式保留3个例子
        }


class GenerateDomainDescriptionStep(PipelineStep[DomainAnalysisContext]):
    """生成领域描述步骤
    
    使用LLM根据收集的信息生成领域描述。
    """
    
    def __init__(self, llm_service: LLMService, prompt_service: PromptService):
        """初始化步骤
        
        参数:
            llm_service: LLM服务
            prompt_service: 提示词服务
        """
        super().__init__("生成领域描述")
        self.llm_service = llm_service
        self.prompt_service = prompt_service
    
    def execute(self, context: DomainAnalysisContext) -> DomainAnalysisContext:
        """执行领域描述生成"""
        logger.info("使用LLM生成领域描述")
        
        # 使用结构化格式
        prompt = self._prepare_structured_prompt(context)
        response = self.llm_service.generate(prompt)
        context.domain_knowledge = self._parse_structured_response(response)
        
        logger.info(f"领域分析完成: {context.domain_knowledge.domain_type}")
        return context
    

    def _prepare_structured_prompt(self, context: DomainAnalysisContext) -> str:
        """准备结构化提示词（只需要DDL）"""
        return self.prompt_service.render(
            'analysis/02_domain_analysis_structured.j2',
            schema_ddl=context.database_ddl
        )
    
    def _parse_structured_response(self, response: str) -> DomainKnowledge:
        """解析结构化JSON响应"""
        try:
            # 清理响应
            response = response.strip()
            
            # 如果响应包含```json标记，提取其中的内容
            if '```json' in response:
                start = response.find('```json') + 7
                end = response.find('```', start)
                if end > start:
                    response = response[start:end].strip()
            
            # 解析JSON
            data = json.loads(response)
            
            # 创建DomainKnowledge对象，直接使用LLM返回的数据
            return DomainKnowledge(
                domain_type=data.get('domain_type', '未知领域'),
                description=data.get('domain_type', '未知领域'),  # 简单使用domain_type作为描述
                business_concepts=data.get('key_entities', []),  # key_entities现在包含了概念
                naming_patterns={},
                key_entities=data.get('key_entities', []),
                business_rules=data.get('business_rules', []),
                key_relationships=[],  # 关系信息已整合到business_rules中
                # 兼容字段
                main_entities=data.get('key_entities', []),
                business_terms=data.get('key_entities', []),  # 使用key_entities代替business_concepts
                relationships=[]  # 关系信息已整合到business_rules中
            )
        except Exception as e:
            logger.error(f"解析结构化响应失败: {e}")
            logger.debug(f"原始响应: {response[:500]}...")
            # 返回默认值
            return DomainKnowledge(
                domain_type='未知领域',
                description='领域分析失败',
                business_concepts=[],
                naming_patterns={},
                key_entities=[],
                business_rules=[],
                key_relationships=[]
            )
    



# ========== 管道主类 ==========

class DomainAnalysisPipeline(Pipeline[DomainAnalysisContext]):
    """初始领域分析管道
    
    分析数据库的业务领域特征。
    """
    
    # ========== 初始化方法 ==========
    
    def __init__(self, services: ServiceContainer):
        """初始化管道
        
        参数:
            services: 类型安全的服务容器
        """
        super().__init__("初始领域分析")
        self._init_steps(services)
    
    def _init_steps(self, services: ServiceContainer) -> None:
        """初始化管道步骤（按执行顺序）"""
        # 1. 格式化DDL
        self.add_step(FormatDatabaseDDLStep())
        
        # 2. 收集表摘要
        self.add_step(CollectTableSummariesStep(services.database_service))
        
        # 3. 收集字段统计
        self.add_step(CollectFieldStatisticsStep())
        
        # 4. 生成领域描述
        self.add_step(GenerateDomainDescriptionStep(
            services.llm_service,
            services.prompt_service
        ))
    
    # ========== 公有方法 ==========
    
    def execute(self, database_schema: DatabaseSchema, database_name: str) -> Dict[str, Any]:
        """执行领域分析
        
        参数:
            database_schema: 数据库结构
            database_name: 数据库名称
            
        返回:
            包含领域知识的字典
        """
        # 创建初始上下文
        context = DomainAnalysisContext(
            database_schema=database_schema,
            database_name=database_name
        )
        
        # 运行管道
        result = self.run(context)
        
        # 返回结果
        return {
            'domain_knowledge': result.domain_knowledge,
            'field_statistics': result.field_statistics
        }


