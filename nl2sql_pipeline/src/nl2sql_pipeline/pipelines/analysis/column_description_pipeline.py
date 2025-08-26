"""列描述生成管道（优化版）

本管道负责为数据库中的每个列生成业务描述。
包含3个步骤：格式化DDL -> 收集样例 -> 生成描述

优化要点：
1. 删除不必要的异常处理
2. 简化长方法
3. 减少过度抽象
4. 清晰的代码组织
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from ..base import Pipeline, PipelineStep
from ...models.database import DatabaseSchema, TableInfo, ColumnInfo
from ...models.analysis import (
    DomainKnowledge,
    FieldClassification,
    ColumnDescription,
    FieldEntropyInfo
)
from ...models.pipeline_contexts import ColumnDescriptionContext
from ...services import ServiceContainer

logger = logging.getLogger(__name__)

# ========== 常量定义 ==========
# 黑名单机制已删除，aid_info表已在数据库获取源头过滤

DEFAULT_SAMPLE_SIZE = 5
DEFAULT_BATCH_SIZE = 10


# ========== 管道步骤 ==========

class FormatTableDDLStep(PipelineStep[ColumnDescriptionContext]):
    """格式化表DDL步骤"""
    
    def execute(self, context: ColumnDescriptionContext) -> ColumnDescriptionContext:
        """执行DDL格式化"""
        logger.info("开始格式化表DDL信息")
        
        for table in context.database_schema.tables:
            # 黑名单检查已删除，aid_info表已在数据库获取源头过滤
            context.table_ddls[table.name] = self._format_table_ddl(table)
        
        logger.info(f"格式化了 {len(context.table_ddls)} 个表的DDL")
        return context
    
    def _format_table_ddl(self, table: TableInfo) -> str:
        """格式化单个表的DDL"""
        lines = [f"CREATE TABLE `{table.name}` ("]
        
        # 添加列定义
        column_defs = []
        for col in table.columns:
            col_def = f"  `{col.name}` {col.data_type}"
            if not col.is_nullable:
                col_def += " NOT NULL"
            if col.is_primary_key:
                col_def += " PRIMARY KEY"
            if col.default_value:
                col_def += f" DEFAULT {col.default_value}"
            if col.comment:
                col_def += f" COMMENT '{col.comment}'"
            column_defs.append(col_def)
        
        lines.extend([f"{cd}," if i < len(column_defs) - 1 else cd 
                     for i, cd in enumerate(column_defs)])
        
        lines.append(");")
        
        return "\n".join(lines)


class CollectColumnExamplesStep(PipelineStep[ColumnDescriptionContext]):
    """收集列样例数据步骤"""
    
    def __init__(self, sample_size: int = DEFAULT_SAMPLE_SIZE):
        super().__init__("收集列样例")
        self.sample_size = sample_size
    
    def execute(self, context: ColumnDescriptionContext) -> ColumnDescriptionContext:
        """执行样例收集"""
        logger.info(f"开始收集列样例数据，每列 {self.sample_size} 条")
        
        for table in context.database_schema.tables:
            # 黑名单检查已删除，aid_info表已在数据库获取源头过滤
            self._collect_table_examples(table, context)
        
        logger.info(f"收集了 {len(context.field_examples)} 个字段的样例数据")
        return context
    
    def _collect_table_examples(self, table: TableInfo, context: ColumnDescriptionContext):
        """收集单个表的样例数据"""
        for column in table.columns:
            field_key = f"{table.name}.{column.name}"
            
            try:
                examples = context.database_service.get_column_examples(
                    table.name,
                    column.name,
                    limit=self.sample_size,
                    schema=context.database_name
                )
                context.field_examples[field_key] = examples
            except Exception as e:
                logger.warning(f"获取字段 {field_key} 样例失败: {e}")
                context.field_examples[field_key] = []


class GenerateColumnDescriptionsStep(PipelineStep[ColumnDescriptionContext]):
    """生成列描述步骤"""
    
    def execute(self, context: ColumnDescriptionContext) -> ColumnDescriptionContext:
        """执行列描述生成"""
        logger.info("开始生成列描述")
        
        for table in context.database_schema.tables:
            # 黑名单检查已删除，aid_info表已在数据库获取源头过滤
            self._generate_table_column_descriptions(table, context)
        
        logger.info(f"列描述生成完成，共生成 {len(context.column_descriptions)} 个描述")
        return context
    
    def _generate_table_column_descriptions(self, table: TableInfo, context: ColumnDescriptionContext):
        """生成单个表的所有列描述"""
        table_ddl = context.table_ddls.get(table.name, "")
        
        for column in table.columns:
            field_key = f"{table.name}.{column.name}"
            
            # 如果有注释，直接使用
            if column.comment:
                context.column_descriptions[field_key] = ColumnDescription(
                    table_name=table.name,
                    column_name=column.name,
                    description=column.comment,
                    confidence=1.0,
                    source="existing"
                )
                continue
            
            # 生成新描述
            description = self._generate_single_column_description(
                table, column, field_key, table_ddl, context
            )
            
            context.column_descriptions[field_key] = ColumnDescription(
                table_name=table.name,
                column_name=column.name,
                description=description,
                confidence=0.8,
                source="generated"
            )
    
    def _generate_single_column_description(self, table: TableInfo, column: ColumnInfo,
                                          field_key: str, table_ddl: str,
                                          context: ColumnDescriptionContext) -> str:
        """生成单个列的描述"""
        # 获取上下文信息
        field_classification = context.field_classifications.get(
            field_key, 
            {"category": "text", "dim_or_meas": "dimension", "importance": 0.5}
        )
        
        entropy_info = context.field_entropy_info.get(field_key, {}) if context.field_entropy_info else {}
        examples = context.field_examples.get(field_key, [])
        
        # 准备提示词参数
        prompt_params = {
            'database_name': context.database_name,
            'database_domain': context.domain_knowledge.description,
            'domain_knowledge': context.domain_knowledge,
            'table_name': table.name,
            'table_ddl': self._remove_comments_from_ddl(table_ddl),
            'column_name': column.name,
            'column_type': column.data_type,
            'is_nullable': column.is_nullable,
            'is_primary_key': column.is_primary_key,
            'is_foreign_key': column.is_foreign_key,
            'column_examples': self._format_examples(examples),
            'field_category': field_classification.get("category", "text"),
            'dim_or_meas': field_classification.get("dim_or_meas", "dimension"),
            'field_importance': field_classification.get("importance", 0.5),
            'entropy_info': {
                'entropy': entropy_info.get('entropy', 0),
                'unique_ratio': entropy_info.get('unique_count', 0) / entropy_info.get('total_count', 1) if entropy_info.get('total_count') else 0,
                'null_ratio': entropy_info.get('null_count', 0) / entropy_info.get('total_count', 1) if entropy_info.get('total_count') else 0,
                'entropy_level': entropy_info.get('entropy_level', '未知')
            }
        }
        
        try:
            # 生成提示词
            prompt = context.prompt_service.render(
                'analysis/04_column_description.j2',
                **prompt_params
            )
            
            # 调用LLM
            response = context.llm_service.generate(prompt)
            
            # 解析响应
            return self._parse_llm_response(response, column.name)
            
        except Exception as e:
            logger.error(f"生成列描述失败 {field_key}: {e}")
            return f"{column.name}字段"
    
    def _remove_comments_from_ddl(self, table_ddl: str) -> str:
        """删除DDL中的注释"""
        lines = table_ddl.split('\n')
        result_lines = []
        
        for line in lines:
            comment_index = line.find('COMMENT')
            if comment_index != -1:
                line = line[:comment_index].rstrip()
                if line.endswith(','):
                    line = line[:-1]
            result_lines.append(line)
        
        return '\n'.join(result_lines)
    
    def _format_examples(self, examples: List[Any]) -> str:
        """格式化样例数据"""
        if not examples:
            return "无样例数据"
        
        # 限制样例数量
        examples = examples[:5]
        
        # 格式化非空样例
        formatted = []
        for ex in examples:
            if ex is not None:
                str_ex = str(ex)
                if len(str_ex) > 50:
                    str_ex = str_ex[:50] + "..."
                formatted.append(str_ex)
        
        return ", ".join(formatted) if formatted else "无有效样例"
    
    def _parse_llm_response(self, response: str, column_name: str) -> str:
        """解析LLM响应"""
        if not response:
            return f"{column_name}字段"
        
        # 清理响应
        description = response.strip()
        
        # 移除可能的引号
        if description.startswith('"') and description.endswith('"'):
            description = description[1:-1]
        
        # 如果太长，截断
        if len(description) > 200:
            description = description[:197] + "..."
        
        return description or f"{column_name}字段"


# ========== 主管道类 ==========

class ColumnDescriptionPipeline(Pipeline[ColumnDescriptionContext]):
    """列描述生成管道（优化版）
    
    执行流程：格式化DDL -> 收集样例 -> 生成描述 -> 批量优化
    """
    
    def __init__(self, services: ServiceContainer):
        """初始化管道"""
        super().__init__("列描述生成")
        self.services = services
        
        # 按顺序添加步骤
        self.add_step(FormatTableDDLStep())
        self.add_step(CollectColumnExamplesStep())
        self.add_step(GenerateColumnDescriptionsStep())

    
    def execute(self,
                database_schema: DatabaseSchema,
                database_name: str,
                domain_knowledge: DomainKnowledge,
                field_classifications: Dict[str, Dict[str, Any]],
                field_entropy_info: Optional[Dict[str, FieldEntropyInfo]] = None) -> Dict[str, Any]:
        """执行列描述生成管道
        
        参数:
            database_schema: 数据库架构
            database_name: 数据库名称
            domain_knowledge: 领域知识
            field_classifications: 字段分类结果
            field_entropy_info: 字段熵值信息（可选）
            
        返回:
            包含列描述的结果字典
        """
        # 创建上下文
        context = ColumnDescriptionContext(
            database_schema=database_schema,
            database_name=database_name,
            domain_knowledge=domain_knowledge,
            field_classifications=field_classifications,
            field_entropy_info=field_entropy_info,
            database_service=self.services.database_service,
            llm_service=self.services.llm_service,
            prompt_service=self.services.prompt_service
        )
        
        # 运行管道
        result = self.run(context)
        
        # 返回结果
        return {
            "column_descriptions": result.column_descriptions,
            "table_ddls": result.table_ddls,
            "field_examples": result.field_examples
        }