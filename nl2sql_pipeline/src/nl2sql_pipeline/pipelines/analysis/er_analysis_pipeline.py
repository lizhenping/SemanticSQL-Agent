"""ER关系分析管道 - 分析流程步骤8

本管道负责分析数据库中表之间的实体关系（ER），分为三个层次：

1. 物理层关系分析：
   - 使用SQL查询分析外键约束
   - 提取表之间的直接物理关联

2. 逻辑层关系分析：
   - 使用LLM分析字段命名模式
   - 识别隐含的逻辑关联（如共享ID模式）

3. 概念层关系分析：
   - 使用LLM分析业务语义
   - 识别高层次的概念关系（聚合、组合、依赖、关联）

输入：数据库架构、领域知识、表描述
输出：三层ER关系分析结果
"""

import logging
import json
from typing import Dict, Any, Optional, List, Set

from ..base import Pipeline, PipelineStep
from ...models.database import DatabaseSchema, TableInfo
from ...models.analysis import (
    DomainKnowledge, FieldClassification, TableDescription,
    PhysicalRelation, LogicalRelation, ConceptualRelationship,
    ERAnalysisResult
)
from ...models.pipeline_contexts import ERAnalysisContext
from ...services import LLMService, PromptService, DatabaseService, ServiceContainer

logger = logging.getLogger(__name__)


class AnalyzePhysicalRelationsStep(PipelineStep[ERAnalysisContext]):
    """步骤1：分析物理层关系（使用SQL查询外键）"""
    
    def __init__(self, database_service: Optional[DatabaseService] = None):
        super().__init__(name="Analyze Physical Relations")
        self.database_service = database_service
    
    def execute(self, context: ERAnalysisContext) -> ERAnalysisContext:
        """使用SQL查询分析数据库中的物理关系"""
        logger.info("=== 步骤1：分析物理层关系（SQL查询） ===")
        
        physical_relations = []
        
        # 如果有数据库服务，使用SQL查询外键
        if self.database_service:
            try:
                physical_relations = self._query_foreign_keys()
            except Exception:
                logger.warning("SQL查询失败，回退到架构信息分析")
                physical_relations = self._analyze_from_schema(context)
        else:
            physical_relations = self._analyze_from_schema(context)
        
        # 更新关系图
        for relation in physical_relations:
            if relation.from_table not in context.relationship_graph:
                context.relationship_graph[relation.from_table] = set()
            context.relationship_graph[relation.from_table].add(relation.to_table)
        
        context.physical_relations = physical_relations
        logger.info(f"物理层分析完成：发现 {len(physical_relations)} 个物理关系")
        
        return context
    
    def _query_foreign_keys(self) -> List[PhysicalRelation]:
        """通过SQL查询获取外键关系"""
        logger.info("执行SQL查询外键约束...")
        
        fk_query = """
        SELECT 
            CONSTRAINT_NAME,
            TABLE_NAME,
            COLUMN_NAME,
            REFERENCED_TABLE_NAME,
            REFERENCED_COLUMN_NAME
        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
        WHERE REFERENCED_TABLE_NAME IS NOT NULL
            AND TABLE_SCHEMA = DATABASE()
        ORDER BY TABLE_NAME, ORDINAL_POSITION
        """
        
        fk_results = self.database_service.execute_query(fk_query)
        physical_relations = []
        
        for row in fk_results:
            relation = PhysicalRelation(
                from_table=row['TABLE_NAME'],
                to_table=row['REFERENCED_TABLE_NAME'],
                from_column=row['COLUMN_NAME'],
                to_column=row['REFERENCED_COLUMN_NAME'],
                constraint_name=row['CONSTRAINT_NAME'],
                relationship_type='foreign_key'
            )
            physical_relations.append(relation)
            logger.info(f"  - 发现外键：{relation.from_table}.{relation.from_column} -> "
                      f"{relation.to_table}.{relation.to_column}")
        
        return physical_relations
    
    def _analyze_from_schema(self, context: ERAnalysisContext) -> List[PhysicalRelation]:
        """从架构信息分析外键关系（备用方法）"""
        physical_relations = []
        
        for table in context.database_schema.tables:
            for column in table.columns:
                if column.is_foreign_key:
                    for fk in table.foreign_keys:
                        if fk.get('column') == column.name:
                            relation = PhysicalRelation(
                                from_table=table.name,
                                to_table=fk.get('referenced_table', ''),
                                from_column=column.name,
                                to_column=fk.get('referenced_column', ''),
                                constraint_name=fk.get('constraint_name', ''),
                                relationship_type='foreign_key'
                            )
                            physical_relations.append(relation)
        
        return physical_relations


class AnalyzeLogicalRelationsStep(PipelineStep[ERAnalysisContext]):
    """步骤2：使用LLM分析逻辑层关系"""
    
    def __init__(self, llm_service: LLMService, prompt_service: PromptService):
        super().__init__(name="Analyze Logical Relations")
        self.llm_service = llm_service
        self.prompt_service = prompt_service
    
    def execute(self, context: ERAnalysisContext) -> ERAnalysisContext:
        """使用LLM分析隐含的逻辑关系"""
        logger.info("=== 步骤2：分析逻辑层关系（LLM分析） ===")
        
        # 准备LLM分析数据
        prompt_data = self._prepare_prompt_data(context)
        
        # 渲染提示词
        prompt = self.prompt_service.render(
            'analysis/08_er_analysis.j2',
            analysis_type='logical',
            **prompt_data
        )
        
        # 调用LLM
        llm_response = self.llm_service.generate(prompt)
        
        # 解析结果
        logical_relations = self._parse_llm_response(llm_response, 'logical')
        
        context.logical_relations = logical_relations
        logger.info(f"逻辑层分析完成：发现 {len(logical_relations)} 个逻辑关系")
        
        return context
    
    def _prepare_prompt_data(self, context: ERAnalysisContext) -> Dict[str, Any]:
        """准备提示词数据"""
        # 格式化表结构信息
        formatted_schema = self._format_schema_with_comments(context)
        
        # 格式化外键信息
        fk_info = self._format_foreign_keys(context.physical_relations)
        
        return {
            'formatted_schema': formatted_schema,
            'fk_info': fk_info,
            'database_name': context.database_name
        }
    
    def _format_schema_with_comments(self, context: ERAnalysisContext) -> str:
        """格式化带注释的表结构"""
        lines = ["数据库表结构（包含业务注释）："]
        
        for table in context.database_schema.tables:
            # 表注释
            table_desc = ""
            if context.table_descriptions and table.name in context.table_descriptions:
                table_desc = context.table_descriptions[table.name].description
            
            lines.append(f"\n表: {table.name}")
            if table_desc:
                lines.append(f"  注释: {table_desc}")
            
            lines.append("  列:")
            for column in table.columns:
                # 列注释
                col_key = f"{table.name}.{column.name}"
                col_desc = ""
                if context.column_descriptions and col_key in context.column_descriptions:
                    col_desc = context.column_descriptions[col_key].description
                
                col_info = f"    - {column.name} ({column.data_type})"
                if column.is_primary_key:
                    col_info += " [主键]"
                if column.is_foreign_key:
                    col_info += " [外键]"
                if col_desc:
                    col_info += f" -- {col_desc}"
                
                lines.append(col_info)
        
        return "\n".join(lines)
    
    def _format_foreign_keys(self, physical_relations: List[PhysicalRelation]) -> str:
        """格式化外键信息"""
        if not physical_relations:
            return "物理外键关系：无"
        
        lines = ["物理外键关系："]
        for rel in physical_relations:
            lines.append(f"  - {rel.from_table}.{rel.from_column} -> {rel.to_table}.{rel.to_column}")
        
        return "\n".join(lines)
    
    def _parse_llm_response(self, response: str, relation_type: str) -> List[Any]:
        """解析LLM响应"""
        try:
            result = json.loads(response)
            relations = []
            
            for rel_data in result.get('relations', []):
                if relation_type == 'logical':
                    relation = LogicalRelation(
                        source_table=rel_data['source_table'],
                        target_table=rel_data['target_table'],
                        source_column=rel_data.get('source_column'),
                        target_column=rel_data.get('target_column'),
                        relationship_type=rel_data.get('relation_type', '1:N'),
                        confidence=0.8,
                        reason=rel_data.get('business_meaning', '')
                    )
                    relations.append(relation)
            
            return relations
        
        except Exception as e:
            logger.error(f"解析LLM响应失败: {e}")
            return []


class AnalyzeConceptualRelationsStep(PipelineStep[ERAnalysisContext]):
    """步骤3：使用LLM分析概念层关系"""
    
    def __init__(self, llm_service: LLMService, prompt_service: PromptService):
        super().__init__(name="Analyze Conceptual Relations")
        self.llm_service = llm_service
        self.prompt_service = prompt_service
    
    def execute(self, context: ERAnalysisContext) -> ERAnalysisContext:
        """使用LLM分析业务概念层的关系"""
        logger.info("=== 步骤3：分析概念层关系（LLM分析） ===")
        
        # 准备数据
        prompt_data = self._prepare_prompt_data(context)
        
        # 渲染提示词
        prompt = self.prompt_service.render(
            'analysis/08_er_analysis.j2',
            analysis_type='conceptual',
            **prompt_data
        )
        
        # 调用LLM
        llm_response = self.llm_service.generate(prompt)
        
        # 解析结果
        conceptual_relations = self._parse_llm_response(llm_response)
        
        context.conceptual_relations = conceptual_relations
        logger.info(f"概念层分析完成：发现 {len(conceptual_relations)} 个概念关系")
        
        # 创建最终结果
        context.er_analysis_result = ERAnalysisResult(
            database_name=context.database_name,
            physical_relations=context.physical_relations,
            logical_relations=context.logical_relations,
            conceptual_relations=context.conceptual_relations,
            entity_types={},  # 简化版本不需要实体类型
            relationship_graph=dict(context.relationship_graph),
            statistics={
                'total_tables': len(context.database_schema.tables),
                'physical_relations': len(context.physical_relations),
                'logical_relations': len(context.logical_relations),
                'conceptual_relations': len(context.conceptual_relations)
            },
            summary={}
        )
        
        return context
    
    def _prepare_prompt_data(self, context: ERAnalysisContext) -> Dict[str, Any]:
        """准备概念分析的提示词数据"""
        # 复用逻辑层的格式化方法
        logical_step = AnalyzeLogicalRelationsStep(None, None)
        formatted_schema = logical_step._format_schema_with_comments(context)
        fk_info = logical_step._format_foreign_keys(context.physical_relations)
        
        # 格式化逻辑关系
        logical_info = self._format_logical_relations(context.logical_relations)
        
        # 表概念分析
        table_concepts = self._analyze_table_concepts(context)
        
        return {
            'formatted_schema': formatted_schema,
            'fk_info': fk_info,
            'physical_info': fk_info,  # 物理关系信息
            'logical_info': logical_info,
            'table_concepts': table_concepts,
            'database_name': context.database_name
        }
    
    def _format_logical_relations(self, logical_relations: List[LogicalRelation]) -> str:
        """格式化逻辑关系"""
        if not logical_relations:
            return "逻辑关系：无"
        
        lines = ["逻辑关系："]
        for rel in logical_relations:
            lines.append(f"  - {rel.source_table} -> {rel.target_table}: {rel.reason}")
        
        return "\n".join(lines)
    
    def _analyze_table_concepts(self, context: ERAnalysisContext) -> List[str]:
        """分析表的业务概念"""
        concepts = []
        
        if context.table_descriptions:
            for table_name, desc in context.table_descriptions.items():
                if desc.business_type:
                    concepts.append(f"{table_name}: {desc.business_type}")
        
        return concepts
    
    def _parse_llm_response(self, response: str) -> List[ConceptualRelationship]:
        """解析LLM响应"""
        try:
            result = json.loads(response)
            relations = []
            
            for rel_data in result.get('relations', []):
                relation = ConceptualRelationship(
                    source_table=rel_data['source_table'],
                    target_table=rel_data['target_table'],
                    source_column=rel_data.get('source_column'),
                    target_column=rel_data.get('target_column'),
                    relationship_type=rel_data.get('relation_type', '1:N'),
                    business_meaning=rel_data.get('business_meaning', ''),
                    cardinality=rel_data.get('relation_type', '1:N')
                )
                relations.append(relation)
            
            return relations
        
        except Exception as e:
            logger.error(f"解析概念关系失败: {e}")
            return []


class ERAnalysisPipeline(Pipeline[ERAnalysisContext]):
    """ER关系分析管道
    
    三层ER分析流程：
    1. 物理层分析：基于外键的显式关系（SQL查询）
    2. 逻辑层分析：基于LLM的隐含关系分析
    3. 概念层分析：基于LLM的高层业务关系分析
    """
    
    def __init__(self, services: ServiceContainer):
        """使用ServiceContainer初始化管道"""
        super().__init__(name="ER Analysis Pipeline")
        
        # 添加分析步骤
        self.add_step(AnalyzePhysicalRelationsStep(services.database_service))
        self.add_step(AnalyzeLogicalRelationsStep(services.llm_service, services.prompt_service))
        self.add_step(AnalyzeConceptualRelationsStep(services.llm_service, services.prompt_service))
        
        logger.info(f"初始化 ER Analysis Pipeline，包含 {len(self.steps)} 个步骤")
    
    def analyze(self,
                database_schema: DatabaseSchema,
                database_name: str,
                domain_knowledge: Optional[DomainKnowledge] = None,
                field_classifications: Optional[List[FieldClassification]] = None,
                table_descriptions: Optional[Dict[str, TableDescription]] = None,
                column_descriptions: Optional[Dict[str, Any]] = None) -> ERAnalysisResult:
        """执行ER关系分析
        
        参数:
            database_schema: 数据库架构信息
            database_name: 数据库名称
            domain_knowledge: 领域知识（可选）
            field_classifications: 字段分类结果（可选）
            table_descriptions: 表描述信息（可选）
            column_descriptions: 列描述信息（可选）
            
        返回:
            ERAnalysisResult: ER分析结果
        """
        # 创建上下文
        context = ERAnalysisContext(
            database_schema=database_schema,
            database_name=database_name,
            domain_knowledge=domain_knowledge,
            field_classifications=field_classifications,
            table_descriptions=table_descriptions,
            column_descriptions=column_descriptions
        )
        
        # 执行管道
        result_context = self.run(context)
        
        # 返回分析结果
        if result_context.er_analysis_result:
            return result_context.er_analysis_result
        else:
            raise RuntimeError("ER分析失败：未生成分析结果")

