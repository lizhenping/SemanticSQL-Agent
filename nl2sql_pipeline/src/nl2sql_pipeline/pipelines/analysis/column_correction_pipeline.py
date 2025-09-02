"""列描述修正管道（优化版）

本管道负责对生成的列描述进行自我修正。
包含3个步骤：识别候选 -> LLM修正 -> 最终处理

优化要点：
1. 移除不必要的异常处理
2. 拆分超长方法
3. 删除死代码
4. 改进类型安全
5. 重组代码结构
"""

import json
import logging
from typing import Dict, Any, List, Optional, Set

from ..base import Pipeline, PipelineStep
from ...models.database import DatabaseSchema, TableInfo
from ...models.analysis import (
    DomainKnowledge,
    ColumnDescription,
    FieldClassification
)
from ...models.pipeline_contexts import ColumnCorrectionContext

from ...services import ServiceContainer

logger = logging.getLogger(__name__)


# ========== 常量定义 ==========

# 通用描述模式
GENERIC_PATTERNS = [
    r'^.{0,10}字段$',  # "XXX字段"
    r'^.{0,10}信息$',  # "XXX信息"
    r'^.{0,10}数据$',  # "XXX数据"
    r'^.{0,10}内容$',  # "XXX内容"
    r'^.{0,10}标识$',  # "XXX标识"
    r'^字段描述$',     # 默认描述
]

# 技术术语集合
TECHNICAL_TERMS = {
    'varchar', 'int', 'bigint', 'datetime', 'timestamp',
    'text', 'decimal', 'float', 'double', 'char',
    'primary key', '主键', 'foreign key', '外键',
    'not null', 'nullable', '可空', '非空'
}


# ========== 管道步骤 ==========

class IdentifyCorrectionCandidatesStep(PipelineStep[ColumnCorrectionContext]):
    """识别需要修正的列描述"""
    
    def __init__(self):
        super().__init__("识别修正候选")
    
    def execute(self, context: ColumnCorrectionContext) -> ColumnCorrectionContext:
        """执行候选识别"""
        logger.info("开始识别需要修正的列描述")
        
        candidates = set()
        stats = self._init_stats()
        
        for field_key, desc in context.column_descriptions.items():
    
                
            reasons = self._check_correction_needed(field_key, desc, context)
            
            if reasons:
                candidates.add(field_key)
                self._update_stats(stats, reasons)
                logger.debug(f"字段 {field_key} 需要修正: {', '.join(reasons)}")
        
        context.correction_candidates = candidates
        context.correction_stats = stats
        
        logger.info(f"识别出 {len(candidates)} 个需要修正的列描述")
        logger.info(f"修正原因统计: {stats}")
        
        return context
    
    def _init_stats(self) -> Dict[str, int]:
        """初始化统计信息"""
        return {
            'too_generic': 0,
            'too_short': 0,
            'too_long': 0,
            'has_technical_terms': 0,
            'low_confidence': 0,
            'type_mismatch': 0
        }
    
    def _check_correction_needed(self, field_key: str, desc: ColumnDescription, 
                               context: ColumnCorrectionContext) -> List[str]:
        """检查是否需要修正"""
        reasons = []
        
        # 检查是否过于通用
        if self._is_generic_description(desc.description):
            reasons.append("过于通用")
        
        # 检查长度
        desc_length = len(desc.description)
        if desc_length < 5:
            reasons.append("描述过短")
        elif desc_length > 100:
            reasons.append("描述过长")
        
        # 检查技术术语
        if self._contains_technical_terms(desc.description):
            reasons.append("包含技术术语")
        
        # 检查置信度
        if desc.confidence < 0.7 and desc.source != "existing":
            reasons.append("置信度低")
        
        # 检查字段类型匹配
        if field_key in context.field_classifications:
            classification = context.field_classifications[field_key]
            if not self._matches_field_type(desc.description, classification):
                reasons.append("与字段类型不匹配")
        
        return reasons
    
    def _update_stats(self, stats: Dict[str, int], reasons: List[str]):
        """更新统计信息"""
        reason_map = {
            "过于通用": "too_generic",
            "描述过短": "too_short",
            "描述过长": "too_long",
            "包含技术术语": "has_technical_terms",
            "置信度低": "low_confidence",
            "与字段类型不匹配": "type_mismatch"
        }
        
        for reason in reasons:
            if reason in reason_map:
                stats[reason_map[reason]] += 1
    
    def _is_generic_description(self, description: str) -> bool:
        """判断描述是否过于通用"""
        import re
        return any(re.match(pattern, description) for pattern in GENERIC_PATTERNS)
    
    def _contains_technical_terms(self, description: str) -> bool:
        """检查描述是否包含技术术语"""
        desc_lower = description.lower()
        return any(term in desc_lower for term in TECHNICAL_TERMS)
    
    def _matches_field_type(self, description: str, classification: Dict[str, Any]) -> bool:
        """检查描述是否与字段类型匹配"""
        category = classification.get("category", "")
        
        # 简单的匹配规则
        type_keywords = {
            "identifier": ["标识", "ID"],
            "datetime": ["时间", "日期", "时刻"],
            "measure": ["数量", "金额", "数值", "总计", "统计"]
        }
        
        if category in type_keywords:
            return any(keyword in description for keyword in type_keywords[category])
        
        return True


class PerformLLMDeepCorrectionStep(PipelineStep[ColumnCorrectionContext]):
    """使用LLM进行深度修正"""
    
    def __init__(self, llm_service, prompt_service):
        super().__init__("LLM深度修正")
        self.llm_service = llm_service
        self.prompt_service = prompt_service
    
    def execute(self, context: ColumnCorrectionContext) -> ColumnCorrectionContext:
        """执行LLM修正"""
        logger.info(f"开始LLM深度修正，剩余 {len(context.correction_candidates)} 个候选")
        
        if not context.correction_candidates:
            return context
        
        # 逐个处理每个列
        for field_key in list(context.correction_candidates):
            self._correct_single_column(field_key, context)
        
        logger.info("LLM深度修正完成")
        return context
    
    def _correct_single_column(self, field_key: str, context: ColumnCorrectionContext):
        """修正单个列"""

            
        correction_info = self._prepare_correction_info(field_key, context)
        
        if not correction_info:
            return
        
        # 生成提示词并调用LLM
        prompt = self.prompt_service.render(
            'analysis/05_column_correction.j2',
            **correction_info
        )
        
        response = self.llm_service.generate(prompt)
        
        # 应用修正结果
        self._apply_correction(response, field_key, context)
    
    def _prepare_correction_info(self, field_key: str, 
                                context: ColumnCorrectionContext) -> Optional[Dict[str, Any]]:
        """准备修正信息"""
        table_name, column_name = field_key.split('.', 1)
        desc = context.column_descriptions.get(field_key)
        
        if not desc:
            return None
        
        # 查找表和列信息
        table, column = self._find_table_and_column(
            table_name, column_name, context.database_schema
        )
        
        if not table or not column:
            return None
        
        # 获取字段分类信息
        field_class = context.field_classifications.get(field_key, {})
        
        return {
            'table_name': table_name,
            'column_name': column_name,
            'domain_description': context.domain_knowledge.description,
            'table_schema_ddl': self._generate_table_ddl(table),
            'column_type': column.data_type,
            'is_nullable': 'YES' if column.is_nullable else 'NO',
            'column_examples': self._get_column_examples(table_name, column_name),
            'current_description': desc.description,
            'field_category': field_class.get('category', 'unknown'),
            'dim_or_meas': field_class.get('dim_or_meas', 'unknown')
        }
    
    def _find_table_and_column(self, table_name: str, column_name: str, 
                              schema: DatabaseSchema) -> tuple:
        """查找表和列信息"""
        table = next(
            (t for t in schema.tables if t.name == table_name),
            None
        )
        
        if not table:
            return None, None
        
        column = next(
            (c for c in table.columns if c.name == column_name),
            None
        )
        
        return table, column
    
    def _generate_table_ddl(self, table: TableInfo) -> str:
        """生成表的DDL"""
        ddl_lines = [f"CREATE TABLE {table.name} ("]
        
        for i, col in enumerate(table.columns):
            col_def = f"  {col.name} {col.data_type}"
            if not col.is_nullable:
                col_def += " NOT NULL"
            if col.is_primary_key:
                col_def += " PRIMARY KEY"
            if i < len(table.columns) - 1:
                col_def += ","
            ddl_lines.append(col_def)
        
        ddl_lines.append(");")
        return "\n".join(ddl_lines)
    
    def _get_column_examples(self, table_name: str, column_name: str) -> str:
        """获取列的样例数据"""
        # TODO: 实现从数据库获取样例数据
        return "暂无样例数据"
    
    def _apply_correction(self, response: str, field_key: str, 
                         context: ColumnCorrectionContext):
        """应用修正结果"""
        try:
            result = json.loads(response)
            
            if result.get('needs_correction', False):
                corrected_desc = result.get('corrected_description', '')
                if corrected_desc:
                    # 更新描述
                    context.column_descriptions[field_key].description = corrected_desc
                    context.corrected_columns.add(field_key)
                    context.correction_candidates.discard(field_key)
                    
                    reason = result.get('correction_reason', '无具体原因')
                    logger.info(f"修正字段 {field_key}: {reason}")
            else:
                # 不需要修正
                context.correction_candidates.discard(field_key)
                logger.debug(f"字段 {field_key} 不需要修正")
                
        except json.JSONDecodeError as e:
            logger.error(f"解析LLM响应失败 {field_key}: {e}, 响应: {response[:200]}...")


class FinalizeCorrectionsStep(PipelineStep[ColumnCorrectionContext]):
    """最终处理步骤"""
    
    def execute(self, context: ColumnCorrectionContext) -> ColumnCorrectionContext:
        """执行最终处理"""
        logger.info("开始最终处理")
        
        # 统计修正结果
        total_corrected = len(context.corrected_columns)
        total_columns = len(context.column_descriptions)
        
        # 按修正原因分组
        correction_by_reason = self._group_by_reason(context)
        
        # 记录统计信息
        logger.info(f"修正完成统计:")
        logger.info(f"- 总列数: {total_columns}")
        logger.info(f"- 修正数: {total_corrected}")
        logger.info(f"- 修正率: {total_corrected / total_columns * 100:.1f}%")
        logger.info(f"- 修正原因分布: {correction_by_reason}")
        
        # 保存统计信息
        context.correction_stats['total_corrected'] = total_corrected
        context.correction_stats['by_reason'] = correction_by_reason
        
        return context
    
    def _group_by_reason(self, context: ColumnCorrectionContext) -> Dict[str, int]:
        """按修正原因分组统计"""
        correction_by_reason = {}
        
        for field_key in context.corrected_columns:
            desc = context.column_descriptions.get(field_key)
            if desc and desc.correction_reason:
                reason = desc.correction_reason
                correction_by_reason[reason] = correction_by_reason.get(reason, 0) + 1
        
        return correction_by_reason


# ========== 主管道类 ==========

class ColumnCorrectionPipeline(Pipeline[ColumnCorrectionContext]):
    """列描述修正管道（优化版）
    
    执行流程：识别候选 -> LLM修正 -> 最终处理
    """
    
    def __init__(self, services: ServiceContainer):
        """初始化管道"""
        super().__init__("列描述修正")
        self.services = services
        
        # 按顺序添加步骤
        self.add_step(IdentifyCorrectionCandidatesStep())
        self.add_step(PerformLLMDeepCorrectionStep(
            services.llm_service,
            services.prompt_service
        ))
        self.add_step(FinalizeCorrectionsStep())
    
    def execute(self,
                database_schema: DatabaseSchema,
                database_name: str,
                domain_knowledge: DomainKnowledge,
                column_descriptions: Dict[str, ColumnDescription],
                field_classifications: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """执行列描述修正管道
        
        参数:
            database_schema: 数据库架构模型
            database_name: 数据库名称
            domain_knowledge: 领域知识模型
            column_descriptions: 待修正的列描述
            field_classifications: 字段分类结果
            
        返回:
            包含修正结果的字典
        """
        # 创建初始上下文
        context = ColumnCorrectionContext(
            database_schema=database_schema,
            database_name=database_name,
            domain_knowledge=domain_knowledge,
            column_descriptions=column_descriptions,
            field_classifications=field_classifications
        )
        
        # 运行管道
        result = self.run(context)
        
        # 返回结果
        return {
            'column_descriptions': result.column_descriptions,
            'correction_stats': result.correction_stats
        }