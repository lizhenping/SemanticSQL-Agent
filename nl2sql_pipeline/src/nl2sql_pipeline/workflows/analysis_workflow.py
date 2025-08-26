"""数据库分析工作流

使用LangGraph编排数据库分析的8个步骤：
1. 架构提取
2. 初始领域分析
3. 字段分类
4. 列描述生成
5. 列描述修正
6. 表描述生成
7. 领域知识优化
8. ER关系分析

工作流负责：
- 管理分析状态
- 协调步骤执行
- 保存中间结果
"""

import logging
from typing import TypedDict, Dict, Any, Optional, List
from datetime import datetime
import json

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from ..models.states import AnalysisState, AnalysisResult
from ..models.database import DatabaseSchema
from ..models.analysis import (
    DomainKnowledge,
    FieldClassification,
    ColumnDescription,
    TableDescription,
    ERRelationship,
    FieldCategory,
    PhysicalRelation,
    LogicalRelation,
    ConceptualRelationship,
    FieldEntropyInfo
)
from ..pipelines.analysis import (
    SchemaExtractionPipeline,
    DomainAnalysisPipeline,
    FieldClassificationPipeline,
    ColumnDescriptionPipeline,
    ColumnCorrectionPipeline,
    TableDescriptionPipeline,
    DomainOptimizationPipeline,
    ERAnalysisPipeline
)
from ..services import ServiceContainer  # 导入共享的ServiceContainer
from ..services.database_service import DatabaseService
from ..services.llm_service import LLMService
from ..services.prompt_service import PromptService
from ..services.config_service import ConfigService

logger = logging.getLogger(__name__)


class AnalysisWorkflowState(TypedDict):
    """分析工作流状态
    
    属性:
        database_name: 数据库名称
        database_config: 数据库连接配置
        current_step: 当前执行步骤
        completed_steps: 已完成的步骤列表
        error_message: 错误信息
        
        # 各步骤的输出结果
        database_schema: 数据库架构
        initial_domain_knowledge: 初始领域知识
        field_classifications: 字段分类结果
        column_descriptions: 列描述
        corrected_column_descriptions: 修正后的列描述
        table_descriptions: 表描述
        optimized_domain_knowledge: 优化后的领域知识
        er_relationships: ER关系
        
        # 最终结果
        analysis_result: 完整的分析结果
    """
    # 基本信息
    database_name: str
    database_config: Dict[str, Any]
    current_step: str
    completed_steps: List[str]
    error_message: Optional[str]
    
    # 步骤输出
    database_schema: Optional[DatabaseSchema]
    initial_domain_knowledge: Optional[DomainKnowledge]
    field_classifications: Optional[Dict[str, Dict[str, Any]]]
    field_classification_models: Optional[List[FieldClassification]]  # 字段分类模型对象
    field_entropy_info: Optional[Dict[str, FieldEntropyInfo]]  # 熵值信息（关键补充）
    column_descriptions: Optional[Dict[str, ColumnDescription]]
    corrected_column_descriptions: Optional[Dict[str, ColumnDescription]]
    table_descriptions: Optional[Dict[str, TableDescription]]
    optimized_domain_knowledge: Optional[DomainKnowledge]
    er_relationships: Optional[Dict[str, List[ERRelationship]]]
    
    # 最终结果
    analysis_result: Optional[AnalysisResult]


class AnalysisWorkflow:
    """数据库分析工作流
    
    管理和执行完整的数据库分析流程。
    """
    
    # ========== 初始化相关方法 ==========
    
    def __init__(self, services: ServiceContainer):
        """初始化工作流
        
        参数:
            services: 服务容器
        """
        self.services = services
        
        # 初始化各个管道
        self._init_pipelines()
        
        # 构建工作流图
        self.workflow = self._build_workflow()
        
        # 设置检查点保存器（用于断点续传）
        self.checkpointer = MemorySaver()
        
        # 编译工作流
        self.app = self.workflow.compile(checkpointer=self.checkpointer)
    
    def _init_pipelines(self):
        """初始化所有分析管道（按工作流执行顺序）"""
        # 1. 架构提取管道
        self.schema_pipeline = SchemaExtractionPipeline(self.services)
        
        # 2. 领域分析管道
        self.domain_pipeline = DomainAnalysisPipeline(self.services)
        
        # 3. 字段分类管道
        self.field_classification_pipeline = FieldClassificationPipeline(self.services)
        
        # 4. 列描述生成管道
        self.column_description_pipeline = ColumnDescriptionPipeline(self.services)
        
        # 5. 表描述生成管道
        self.table_description_pipeline = TableDescriptionPipeline(self.services)
        
        # 6. 列描述修正管道
        self.column_correction_pipeline = ColumnCorrectionPipeline(self.services)
        
        # 7. 领域优化管道
        self.domain_optimization_pipeline = DomainOptimizationPipeline(self.services)
        
        # 8. ER关系分析管道
        self.er_analysis_pipeline = ERAnalysisPipeline(self.services)
    
    def _build_workflow(self) -> StateGraph:
        """构建工作流图
        
        返回:
            配置好的状态图
        """
        # 创建状态图
        workflow = StateGraph(AnalysisWorkflowState)
        
        # 添加节点（每个步骤对应一个节点）
        workflow.add_node("extract_schema", self._extract_schema)
        workflow.add_node("analyze_domain", self._analyze_domain)
        workflow.add_node("classify_fields", self._classify_fields)
        workflow.add_node("generate_column_desc", self._generate_column_descriptions)
        workflow.add_node("generate_table_desc", self._generate_table_descriptions)
        workflow.add_node("correct_column_desc", self._correct_column_descriptions)
        workflow.add_node("optimize_domain", self._optimize_domain)
        workflow.add_node("analyze_er", self._analyze_er_relationships)
        workflow.add_node("finalize_result", self._finalize_result)
        
        # 设置入口点
        workflow.set_entry_point("extract_schema")
        
        # 添加边（定义执行流程）
        workflow.add_edge("extract_schema", "analyze_domain")
        workflow.add_edge("analyze_domain", "classify_fields")
        workflow.add_edge("classify_fields", "generate_column_desc")
        workflow.add_edge("generate_column_desc", "generate_table_desc")
        workflow.add_edge("generate_table_desc", "correct_column_desc")
        workflow.add_edge("correct_column_desc", "optimize_domain")
        workflow.add_edge("optimize_domain", "analyze_er")
        workflow.add_edge("analyze_er", "finalize_result")
        workflow.add_edge("finalize_result", END)
        
        return workflow
    
    # ========== 主要公开方法 ==========
    
    def run(self, database_name: str, database_config: Dict[str, Any], 
            thread_id: Optional[str] = None) -> AnalysisResult:
        """运行分析工作流
        
        参数:
            database_name: 数据库名称
            database_config: 数据库连接配置
            thread_id: 线程ID（用于断点续传）
            
        返回:
            分析结果
        """
        # 初始化状态
        initial_state = self._create_initial_state(database_name, database_config)
        
        # 配置线程
        config = {"configurable": {"thread_id": thread_id or "default"}}
        
        logger.info(f"开始分析数据库: {database_name}")
        
        # 运行工作流
        final_state = self._execute_workflow(initial_state, config)
        
        # 检查结果
        if final_state and final_state.get("analysis_result"):
            logger.info("数据库分析工作流执行成功")
            return final_state["analysis_result"]
        else:
            error_msg = final_state.get("error_message") if final_state else "未知错误"
            raise Exception(f"数据库分析失败: {error_msg}")
    
    def get_checkpoint(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """获取检查点状态
        
        参数:
            thread_id: 线程ID
            
        返回:
            检查点状态或None
        """
        config = {"configurable": {"thread_id": thread_id}}
        checkpoint = self.checkpointer.get(config)
        return checkpoint.state if checkpoint else None
    
    def resume(self, thread_id: str) -> AnalysisResult:
        """从检查点恢复执行
        
        参数:
            thread_id: 线程ID
            
        返回:
            分析结果
        """
        checkpoint = self.get_checkpoint(thread_id)
        if not checkpoint:
            raise ValueError(f"找不到线程 {thread_id} 的检查点")
        
        logger.info(f"从检查点恢复执行，当前步骤: {checkpoint.get('current_step')}")
        
        # 继续执行
        config = {"configurable": {"thread_id": thread_id}}
        final_state = self._execute_workflow(None, config)
        
        if final_state and final_state.get("analysis_result"):
            return final_state["analysis_result"]
        else:
            raise Exception("恢复执行失败")
    
    # ========== 工作流步骤方法 ==========
    
    def _extract_schema(self, state: AnalysisWorkflowState) -> AnalysisWorkflowState:
        """步骤1：提取数据库架构
        
        参数:
            state: 当前状态
            
        返回:
            更新后的状态
        """
        logger.info("开始执行步骤1：提取数据库架构")
        state["current_step"] = "extract_schema"
        
        # 连接数据库
        self.services.database_service.connect(**state["database_config"])
        
        # 执行架构提取
        result = self.schema_pipeline.execute(state["database_config"])
        
        # 保存结果
        state["database_schema"] = result["database_schema"]
        state["completed_steps"].append("extract_schema")
        
        logger.info(f"架构提取完成，发现 {len(result['database_schema'].tables)} 个表")
        
        return state
    
    def _analyze_domain(self, state: AnalysisWorkflowState) -> AnalysisWorkflowState:
        """步骤2：初始领域分析
        
        参数:
            state: 当前状态
            
        返回:
            更新后的状态
        """
        logger.info("开始执行步骤2：初始领域分析")
        state["current_step"] = "analyze_domain"
        
        result = self.domain_pipeline.execute(
            database_schema=state["database_schema"],
            database_name=state["database_name"]
        )
        
        state["initial_domain_knowledge"] = result["domain_knowledge"]
        state["completed_steps"].append("analyze_domain")
        
        logger.info(f"领域分析完成: {result['domain_knowledge'].domain_type}")
        
        return state
    
    def _classify_fields(self, state: AnalysisWorkflowState) -> AnalysisWorkflowState:
        """步骤3：字段分类
        
        参数:
            state: 当前状态
            
        返回:
            更新后的状态
        """
        logger.info("开始执行步骤3：字段分类")
        state["current_step"] = "classify_fields"
        
        # 使用管道的 execute 方法，保持与其他管道一致
        result = self.field_classification_pipeline.execute(
            database_schema=state["database_schema"],
            database_name=state["database_name"],
            domain_knowledge=state["initial_domain_knowledge"]
        )
        
        state["field_classifications"] = result.field_classifications_dict or {}
        state["field_classification_models"] = result.field_classifications or []
        field_entropy_info = result.field_entropy_info or {}
        logger.debug(f"从字段分类获得的熵值信息数量: {len(field_entropy_info)}")
        if field_entropy_info:
            first_key = list(field_entropy_info.keys())[0]
            logger.debug(f"熵值信息示例 - 键: {first_key}, 值类型: {type(field_entropy_info[first_key])}")
        state["field_entropy_info"] = field_entropy_info
        state["completed_steps"].append("classify_fields")
        
        logger.info(f"字段分类完成，处理了 {len(state['field_classifications'])} 个字段")
        
        return state
    
    def _generate_column_descriptions(self, state: AnalysisWorkflowState) -> AnalysisWorkflowState:
        """步骤4：生成列描述
        
        参数:
            state: 当前状态
            
        返回:
            更新后的状态
        """
        logger.info("开始执行步骤4：生成列描述")
        state["current_step"] = "generate_column_desc"
        
        # 转换字段分类为字典格式
        field_classifications_dict = self._field_classifications_to_dict(state["field_classifications"])
        
        result = self.column_description_pipeline.execute(
            database_schema=state["database_schema"],
            database_name=state["database_name"],
            domain_knowledge=state["initial_domain_knowledge"],
            field_classifications=field_classifications_dict,
            field_entropy_info=state.get("field_entropy_info", {})
        )
        
        state["column_descriptions"] = result["column_descriptions"]
        state["completed_steps"].append("generate_column_desc")
        
        logger.info(f"列描述生成完成")
        
        return state
    
    def _generate_table_descriptions(self, state: AnalysisWorkflowState) -> AnalysisWorkflowState:
        """步骤5：生成表描述
        
        参数:
            state: 当前状态
            
        返回:
            更新后的状态
        """
        logger.info("开始执行步骤6：生成表描述")
        state["current_step"] = "generate_table_desc"
        
        result = self.table_description_pipeline.execute(
            database_schema=state["database_schema"],
            database_name=state["database_name"],
            domain_knowledge=state["initial_domain_knowledge"],
            column_descriptions=state["column_descriptions"]
        )
        
        state["table_descriptions"] = result["table_descriptions"]
        state["completed_steps"].append("generate_table_desc")
        
        logger.info(f"表描述生成完成")
        
        return state

    def _correct_column_descriptions(self, state: AnalysisWorkflowState) -> AnalysisWorkflowState:
        """步骤6：修正列描述
        
        参数:
            state: 当前状态
            
        返回:
            更新后的状态
        """
        logger.info("开始执行步骤6：修正列描述")
        state["current_step"] = "correct_column_desc"
        
        result = self.column_correction_pipeline.execute(
            database_schema=state["database_schema"],
            database_name=state["database_name"],
            domain_knowledge=state["initial_domain_knowledge"],
            column_descriptions=state["column_descriptions"],
            field_classifications=state["field_classifications"]
        )
        
        state["corrected_column_descriptions"] = result["column_descriptions"]
        state["completed_steps"].append("correct_column_desc")
        
        logger.info(f"列描述修正完成，修正了 {result['correction_stats']['total_corrected']} 个描述")
        
        return state

    def _optimize_domain(self, state: AnalysisWorkflowState) -> AnalysisWorkflowState:
        """步骤7：优化领域知识
        
        参数:
            state: 当前状态
            
        返回:
            更新后的状态
        """
        logger.info("开始执行步骤7：优化领域知识")
        state["current_step"] = "optimize_domain"
        
        result = self.domain_optimization_pipeline.execute(
            database_schema=state["database_schema"],
            database_name=state["database_name"],
            initial_domain_knowledge=state["initial_domain_knowledge"],
            table_descriptions=state["table_descriptions"],
            column_descriptions=state["corrected_column_descriptions"],
            field_classifications=state["field_classifications"]
        )
        
        state["optimized_domain_knowledge"] = result["optimized_domain_knowledge"]
        state["completed_steps"].append("optimize_domain")
        
        logger.info("领域知识优化完成")
        
        return state
    
    def _analyze_er_relationships(self, state: AnalysisWorkflowState) -> AnalysisWorkflowState:
        """步骤8：分析ER关系
        
        参数:
            state: 当前状态
            
        返回:
            更新后的状态
        """
        logger.info("开始执行步骤8：分析ER关系")
        state["current_step"] = "analyze_er"
        
        result = self.er_analysis_pipeline.analyze(
            database_schema=state["database_schema"],
            database_name=state["database_name"],
            domain_knowledge=state.get("optimized_domain_knowledge", state.get("initial_domain_knowledge")),
            field_classifications=state.get("field_classification_models", []),
            table_descriptions=state.get("table_descriptions", {}),
            column_descriptions=state.get("corrected_column_descriptions", state.get("column_descriptions", {}))
        )
        
        state["er_relationships"] = {
            "physical": result.physical_relations,
            "logical": result.logical_relations,
            "conceptual": result.conceptual_relations
        }
        state["completed_steps"].append("analyze_er")
        
        # 计算总关系数
        total_relations = len(result.physical_relations) + len(result.logical_relations) + len(result.conceptual_relations)
        
        # 如果statistics中有总数，使用它；否则使用计算值
        if result.statistics and 'total_relations' in result.statistics:
            total_relations = result.statistics['total_relations']
            
        logger.info(f"ER关系分析完成，发现 {total_relations} 个关系")
        
        return state
    
    def _finalize_result(self, state: AnalysisWorkflowState) -> AnalysisWorkflowState:
        """最终步骤：整合分析结果
        
        参数:
            state: 当前状态
            
        返回:
            更新后的状态
        """
        logger.info("开始整合分析结果")
        state["current_step"] = "finalize_result"
        
        # 转换字段分类
        field_classifications_dict = self._convert_field_classifications(state)
        
        # 转换ER关系
        er_relationships_dict = self._convert_er_relationships(state)
        
        # 创建完整的分析结果
        analysis_result = self._create_analysis_result(
            state, field_classifications_dict, er_relationships_dict
        )
        
        state["analysis_result"] = analysis_result
        state["completed_steps"].append("finalize_result")
        
        logger.info("分析结果整合完成")
        
        # 断开数据库连接
        self.services.database_service.disconnect()
        
        return state
    
    # ========== 辅助私有方法 ==========
    
    def _create_initial_state(self, database_name: str, database_config: Dict[str, Any]) -> Dict[str, Any]:
        """创建初始状态"""
        return {
            "database_name": database_name,
            "database_config": database_config,
            "current_step": "",
            "completed_steps": [],
            "error_message": None,
            "database_schema": None,
            "initial_domain_knowledge": DomainKnowledge(
                domain_type="未知",
                description="待分析"
            ),
            "field_classifications": None,
            "column_descriptions": None,
            "corrected_column_descriptions": None,
            "table_descriptions": None,
            "optimized_domain_knowledge": None,
            "er_relationships": None,
            "analysis_result": None
        }
    
    def _execute_workflow(self, initial_state: Optional[Dict[str, Any]], config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """执行工作流"""
        final_state = None
        for output in self.app.stream(initial_state, config):
            for key, value in output.items():
                logger.debug(f"步骤 {key} 完成")
                final_state = value
        return final_state
    
    def _convert_field_classifications(self, state: AnalysisWorkflowState) -> Dict[str, Dict[str, Any]]:
        """转换字段分类为字典格式"""
        field_classifications = state.get("field_classification_models", [])
        
        # 如果没有模型列表，尝试从原始数据构建
        if not field_classifications and "field_classifications" in state:
            field_classifications = self._build_field_classifications_from_raw(state)
        
        # 转换为字典格式
        return self._field_classifications_to_dict(field_classifications)
    
    def _build_field_classifications_from_raw(self, state: AnalysisWorkflowState) -> List[FieldClassification]:
        """从原始数据构建字段分类列表"""
        logger.warning("未找到field_classification_models，尝试从原始字典转换")
        field_classifications = []
        
        field_class_data = state["field_classifications"]
        if isinstance(field_class_data, dict):
            for field_key, classification in field_class_data.items():
                field_classification = self._create_field_classification(
                    field_key, classification, state["database_schema"]
                )
                if field_classification:
                    field_classifications.append(field_classification)
        elif isinstance(field_class_data, list):
            logger.info("field_classifications已经是列表格式，直接使用")
            field_classifications = field_class_data
            
        return field_classifications
    
    def _create_field_classification(self, field_key: str, classification: Dict[str, Any], 
                                   database_schema: DatabaseSchema) -> Optional[FieldClassification]:
        """创建单个字段分类对象"""
        table_name, column_name = field_key.split('.', 1)
        
        # 查找列信息
        column = self._find_column(table_name, column_name, database_schema)
        if not column:
            return None
        
        # 映射类别
        category = self._map_field_category(classification.get("category", "text"))
        
        return FieldClassification(
            field_name=field_key,
            category=category,
            confidence=classification.get("importance", 0.5),
            reasoning=classification.get("description", ""),
            data_type=column.data_type,
            is_nullable=column.is_nullable
        )
    
    def _find_column(self, table_name: str, column_name: str, database_schema: DatabaseSchema):
        """查找列信息"""
        for table in database_schema.tables:
            if table.name == table_name:
                return next((c for c in table.columns if c.name == column_name), None)
        return None
    
    def _map_field_category(self, category_str: str) -> FieldCategory:
        """映射字段类别字符串到枚举"""
        category_mapping = {
            "identifier": FieldCategory.IDENTIFIER,
            "measure": FieldCategory.MEASURE,
            "dimension": FieldCategory.DIMENSION,
            "datetime": FieldCategory.DATETIME,
            "text": FieldCategory.TEXT,
            "boolean": FieldCategory.BOOLEAN
        }
        return category_mapping.get(category_str.lower(), FieldCategory.OTHER)
    
    def _field_classifications_to_dict(self, field_classifications) -> Dict[str, Dict[str, Any]]:
        """将字段分类列表转换为字典"""
        field_classifications_dict = {}
        
        if isinstance(field_classifications, list):
            for fc in field_classifications:
                key = self._get_field_key(fc)
                if key:
                    field_classifications_dict[key] = {
                        'category': fc.category.value if hasattr(fc.category, 'value') else str(fc.category),
                        'confidence': getattr(fc, 'confidence', 0.0),
                        'reasoning': getattr(fc, 'reasoning', ''),
                        'dim_or_meas': getattr(fc, 'dim_or_meas', 'dimension'),
                        'importance': getattr(fc, 'importance', 0.5),
                        'field_type': getattr(fc, 'field_type', 'unknown')
                    }
        else:
            field_classifications_dict = field_classifications or {}
            
        return field_classifications_dict
    
    def _get_field_key(self, fc) -> Optional[str]:
        """获取字段分类的键"""
        if hasattr(fc, 'table_name') and hasattr(fc, 'column_name'):
            return f"{fc.table_name}.{fc.column_name}"
        elif hasattr(fc, 'field_name'):
            return fc.field_name
        return None
    
    def _convert_er_relationships(self, state: AnalysisWorkflowState) -> Dict[str, List[ERRelationship]]:
        """转换ER关系为字典格式"""
        er_relationships = state["er_relationships"]
        er_relationships_dict = {}
        
        if isinstance(er_relationships, dict):
            # 转换字典中的关系对象
            for level, relations in er_relationships.items():
                er_relationships_dict[level] = [
                    self._convert_to_er_relationship(relation) 
                    for relation in relations
                ]
        elif isinstance(er_relationships, list):
            # 按层级分组
            er_relationships_dict = self._group_relations_by_level(er_relationships)
        else:
            er_relationships_dict = {"physical": [], "logical": [], "conceptual": []}
            
        return er_relationships_dict
    
    def _group_relations_by_level(self, relations: List) -> Dict[str, List[ERRelationship]]:
        """按层级分组关系"""
        grouped = {}
        for relation in relations:
            level = getattr(relation, 'level', 'physical')
            if level not in grouped:
                grouped[level] = []
            er_rel = self._convert_to_er_relationship(relation)
            grouped[level].append(er_rel)
        return grouped
    
    def _convert_to_er_relationship(self, relation) -> ERRelationship:
        """将不同类型的关系对象转换为ERRelationship对象"""
        if isinstance(relation, ERRelationship):
            return relation
        elif isinstance(relation, PhysicalRelation):
            return self._convert_physical_relation(relation)
        elif isinstance(relation, LogicalRelation):
            return self._convert_logical_relation(relation)
        elif isinstance(relation, ConceptualRelationship):
            return self._convert_conceptual_relation(relation)
        else:
            return self._convert_generic_relation(relation)
    
    def _convert_physical_relation(self, relation: PhysicalRelation) -> ERRelationship:
        """转换物理关系"""
        return ERRelationship(
            source_table=relation.from_table,
            target_table=relation.to_table,
            relationship_type=relation.relationship_type,
            source_column=relation.from_column,
            target_column=relation.to_column,
            confidence=1.0,
            level="physical"
        )
    
    def _convert_logical_relation(self, relation: LogicalRelation) -> ERRelationship:
        """转换逻辑关系"""
        return ERRelationship(
            source_table=relation.source_table,
            target_table=relation.target_table,
            relationship_type=relation.relationship_type,
            source_column=relation.source_column,
            target_column=relation.target_column,
            confidence=relation.confidence,
            level="logical"
        )
    
    def _convert_conceptual_relation(self, relation: ConceptualRelationship) -> ERRelationship:
        """转换概念关系"""
        return ERRelationship(
            source_table=relation.source_table,
            target_table=relation.target_table,
            relationship_type=relation.relationship_type,
            source_column=relation.source_column,
            target_column=relation.target_column,
            confidence=getattr(relation, 'confidence', 0.8),
            level="conceptual"
        )
    
    def _convert_generic_relation(self, relation) -> ERRelationship:
        """转换通用关系对象"""
        # 获取关系数据
        if hasattr(relation, '__dict__'):
            rel_dict = relation.__dict__
        elif isinstance(relation, dict):
            rel_dict = relation
        else:
            logger.warning(f"无法转换关系对象类型: {type(relation)}")
            return ERRelationship(
                source_table="unknown",
                target_table="unknown",
                relationship_type="unknown",
                confidence=0.0,
                level="unknown"
            )
        
        return ERRelationship(
            source_table=rel_dict.get('source_table', rel_dict.get('from_table', 'unknown')),
            target_table=rel_dict.get('target_table', rel_dict.get('to_table', 'unknown')),
            relationship_type=rel_dict.get('relationship_type', 'unknown'),
            source_column=rel_dict.get('source_column', rel_dict.get('from_column')),
            target_column=rel_dict.get('target_column', rel_dict.get('to_column')),
            confidence=rel_dict.get('confidence', 0.5),
            level=rel_dict.get('level', 'physical')
        )
    
    def _create_analysis_result(self, state: AnalysisWorkflowState, 
                              field_classifications_dict: Dict[str, Dict[str, Any]],
                              er_relationships_dict: Dict[str, List[ERRelationship]]) -> AnalysisResult:
        """创建分析结果对象"""
        return AnalysisResult(
            database_name=state["database_name"],
            analysis_timestamp=datetime.now(),
            database_schema=state["database_schema"],
            domain_knowledge=self._get_domain_knowledge(state),
            table_descriptions=list((state.get("table_descriptions") or {}).values()),
            column_descriptions=self._get_column_descriptions(state),
            field_classifications=field_classifications_dict,
            er_relationships=er_relationships_dict,
            analysis_stats=self._create_analysis_stats(state)
        )
    
    def _get_domain_knowledge(self, state: AnalysisWorkflowState) -> DomainKnowledge:
        """获取领域知识"""
        return (state.get("optimized_domain_knowledge") or 
                state.get("initial_domain_knowledge") or 
                DomainKnowledge(domain_type="未知", description="待分析"))
    
    def _get_column_descriptions(self, state: AnalysisWorkflowState) -> List[ColumnDescription]:
        """获取列描述列表"""
        column_descriptions = (state.get("corrected_column_descriptions") or 
                             state.get("column_descriptions") or {})
        return list(column_descriptions.values())
    
    def _create_analysis_stats(self, state: AnalysisWorkflowState) -> Dict[str, Any]:
        """创建分析统计信息"""
        return {
            "total_tables": len(state["database_schema"].tables),
            "total_columns": sum(len(t.columns) for t in state["database_schema"].tables),
            "completed_steps": state["completed_steps"],
            "analysis_duration": "N/A"  # 可以计算实际耗时
        }