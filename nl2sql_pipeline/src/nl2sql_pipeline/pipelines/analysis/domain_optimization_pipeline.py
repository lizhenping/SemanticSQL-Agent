"""领域知识优化管道（极简版）

本管道负责基于完整的数据库分析结果优化领域知识描述。
主要通过LLM理解表结构和业务逻辑，生成更准确的领域描述。

优化要点：
1. 删除基于规则的分析，完全依赖LLM
2. 简化为2个步骤：准备数据 -> LLM优化
3. 专注于核心目标：生成更好的领域描述
"""

import logging
from typing import Dict, Any, List
from collections import Counter

from ..base import Pipeline, PipelineStep
from ...models.database import DatabaseSchema
from ...models.analysis import (
    DomainKnowledge,
    TableDescription,
    ColumnDescription
)
from ...models.pipeline_contexts import DomainOptimizationContext
from ...services import ServiceContainer

logger = logging.getLogger(__name__)


# ========== 管道步骤 ==========

class PrepareOptimizationDataStep(PipelineStep[DomainOptimizationContext]):
    """准备优化数据步骤
    
    整理和汇总数据库分析结果，为LLM优化做准备。
    """
    
    def execute(self, context: DomainOptimizationContext) -> DomainOptimizationContext:
        """执行数据准备"""
        logger.info("开始准备优化数据")
        
        # 统计基本信息
        stats = self._calculate_statistics(context)
        
        # 提取核心表信息
        core_tables = self._extract_core_tables(context)
        
        # 保存准备好的数据
        context.optimization_insights = {
            'statistics': stats,
            'core_tables': core_tables
        }
        
        logger.info(f"数据准备完成，识别出 {len(core_tables)} 个核心表")
        
        return context
    
    def _calculate_statistics(self, context: DomainOptimizationContext) -> Dict[str, Any]:
        """计算数据库统计信息"""
        # 表类型分布
        type_counter = Counter()
        for table_desc in context.table_descriptions.values():
            type_counter[table_desc.business_type] += 1
        
        return {
            'total_tables': len(context.database_schema.tables),
            'total_columns': sum(len(t.columns) for t in context.database_schema.tables),
            'table_type_distribution': dict(type_counter)
        }
    
    def _extract_core_tables(self, context: DomainOptimizationContext) -> List[Dict[str, Any]]:
        """提取核心表信息"""
        core_tables = []
        
        # 选择置信度高的表
        for table_name, table_desc in context.table_descriptions.items():
            if table_desc.confidence >= 0.7:  # 只选择高置信度的表
                # 获取该表的关键字段
                key_columns = table_desc.key_columns[:5] if table_desc.key_columns else []
                
                core_tables.append({
                    'name': table_name,
                    'description': table_desc.description,
                    'type': table_desc.business_type,
                    'key_columns': key_columns,
                    'confidence': table_desc.confidence
                })
        
        # 按置信度排序，返回前10个
        core_tables.sort(key=lambda x: x['confidence'], reverse=True)
        return core_tables[:10]


class GenerateOptimizedDomainKnowledgeStep(PipelineStep[DomainOptimizationContext]):
    """生成优化的领域知识步骤
    
    使用LLM基于数据库分析结果生成优化的领域描述。
    """
    
    def __init__(self, llm_service, prompt_service):
        super().__init__("生成优化领域知识")
        self.llm_service = llm_service
        self.prompt_service = prompt_service
    
    def execute(self, context: DomainOptimizationContext) -> DomainOptimizationContext:
        """执行领域知识生成"""
        logger.info("开始生成优化的领域知识")
        
        # 准备提示词参数
        prompt_params = self._prepare_prompt_params(context)
        
        # 使用模板生成提示词
        prompt = self.prompt_service.render(
            'analysis/07_domain_optimization.j2',
            **prompt_params
        )
        
        # 调用LLM生成优化的描述
        optimized_description = self.llm_service.generate(prompt)
        
        # 创建优化的领域知识对象
        context.optimized_domain_knowledge = DomainKnowledge(
            domain_type=context.initial_domain_knowledge.domain_type,
            description=optimized_description.strip(),
            business_concepts=context.initial_domain_knowledge.business_concepts,
            naming_patterns=context.initial_domain_knowledge.naming_patterns,
            key_entities=[],  # 简化：不再提取实体
            main_entities=[],
            business_rules=[],  # 简化：不再提取规则
            key_relationships=[]
        )
        
        # 记录改进
        self._log_improvements(context)
        
        logger.info("优化的领域知识生成完成")
        
        return context
    
    def _prepare_prompt_params(self, context: DomainOptimizationContext) -> Dict[str, Any]:
        """准备提示词参数"""
        insights = context.optimization_insights
        stats = insights['statistics']
        core_tables = insights['core_tables']
        
        # 为每个核心表添加列注释示例
        enriched_tables = []
        for table_info in core_tables:
            table_name = table_info['name']
            
            # 获取该表的部分列注释
            sample_columns = []
            if table_info.get('key_columns'):
                for col_name in table_info['key_columns'][:5]:  # 最多5个关键列
                    field_key = f"{table_name}.{col_name}"
                    col_desc = context.column_descriptions.get(field_key)
                    if col_desc:
                        sample_columns.append({
                            'name': col_name,
                            'description': col_desc.description
                        })
            
            enriched_table = table_info.copy()
            enriched_table['sample_columns'] = sample_columns
            enriched_tables.append(enriched_table)
        
        # 准备字段类型分布
        field_categories = {}
        for field_key, field_class in context.field_classifications.items():
            category = field_class.get('category', 'unknown')
            field_categories[category] = field_categories.get(category, 0) + 1
        
        # 准备表类型分析洞察
        analysis_insights = {
            'entity_tables': stats['table_type_distribution'].get('entity_table', 0),
            'relation_tables': stats['table_type_distribution'].get('relation_table', 0),
            'config_tables': stats['table_type_distribution'].get('config_table', 0),
            'log_tables': stats['table_type_distribution'].get('log_table', 0)
        }
        
        return {
            'initial_domain': context.initial_domain_knowledge.description,
            'table_summaries': enriched_tables,
            'field_categories': field_categories,
            'total_tables': stats['total_tables'],
            'total_columns': stats['total_columns'],
            'analysis_insights': analysis_insights
        }
    
    def _log_improvements(self, context: DomainOptimizationContext):
        """记录改进情况"""
        initial_length = len(context.initial_domain_knowledge.description)
        optimized_length = len(context.optimized_domain_knowledge.description)
        
        logger.info("领域知识优化统计:")
        logger.info(f"- 描述长度: {initial_length} → {optimized_length}")
        logger.info(f"- 核心表数量: {len(context.optimization_insights['core_tables'])}")


# ========== 主管道类 ==========

class DomainOptimizationPipeline(Pipeline[DomainOptimizationContext]):
    """领域知识优化管道（极简版）
    
    执行流程：准备数据 -> LLM优化
    """
    
    def __init__(self, services: ServiceContainer):
        """初始化管道"""
        super().__init__("领域知识优化")
        self.services = services
        
        # 只需要两个步骤
        self.add_step(PrepareOptimizationDataStep())
        self.add_step(GenerateOptimizedDomainKnowledgeStep(
            services.llm_service,
            services.prompt_service
        ))
    
    def execute(self,
                database_schema: DatabaseSchema,
                database_name: str,
                initial_domain_knowledge: DomainKnowledge,
                table_descriptions: Dict[str, TableDescription],
                column_descriptions: Dict[str, ColumnDescription],
                field_classifications: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """执行领域知识优化管道
        
        参数:
            database_schema: 数据库架构模型
            database_name: 数据库名称
            initial_domain_knowledge: 初始领域知识
            table_descriptions: 表描述字典
            column_descriptions: 列描述字典
            field_classifications: 字段分类结果
            
        返回:
            包含优化结果的字典
        """
        # 创建初始上下文
        context = DomainOptimizationContext(
            database_schema=database_schema,
            database_name=database_name,
            initial_domain_knowledge=initial_domain_knowledge,
            table_descriptions=table_descriptions,
            column_descriptions=column_descriptions,
            field_classifications=field_classifications
        )
        
        # 运行管道
        result = self.run(context)
        
        # 返回结果
        return {
            'optimized_domain_knowledge': result.optimized_domain_knowledge,
            'optimization_insights': result.optimization_insights
        }