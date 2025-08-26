"""字段分类管道 - 分析流程步骤3（优化版V2）

本管道负责对数据库中的字段进行分类和熵值计算：
- 收集字段样本数据
- 计算字段熵值
- 使用LLM进行字段分类
- 生成字段分类报告

优化要点：
1. 移除基于规则的推断，完全依赖LLM
2. 简化代码结构
3. 提前计算熵值供LLM参考
"""

import logging
from typing import Dict, Any, Optional, List, TYPE_CHECKING
import json
from dataclasses import dataclass, field
from datetime import datetime
from collections import Counter

from ..base import Pipeline, PipelineStep
from ...models.database import DatabaseSchema
from ...models.analysis import DomainKnowledge, FieldClassification, FieldCategory, FieldEntropyInfo
from ...models.step_results import FieldClassificationResult
from ...models.pipeline_common import (
    FieldInfo,
    DEFAULT_SAMPLE_SIZE,
    DEFAULT_MAX_TABLES,
    DEFAULT_BATCH_SIZE
)
from .utils import calculate_entropy, get_entropy_level
from ...services import ServiceContainer

if TYPE_CHECKING:
    from ...services import DatabaseService, LLMService, PromptService

logger = logging.getLogger(__name__)


# ========== 导入上下文模型 ==========

from ...models.pipeline_contexts import FieldClassificationContext


# ========== 管道步骤 ==========

class CollectAndAnalyzeFieldsStep(PipelineStep[FieldClassificationContext]):
    """步骤1：收集字段信息并计算熵值"""
    
    def __init__(self):
        super().__init__(name="Collect and Analyze Fields")
        self.sample_size = DEFAULT_SAMPLE_SIZE
        self.max_tables = DEFAULT_MAX_TABLES
    
    def execute(self, context: FieldClassificationContext) -> FieldClassificationContext:
        """收集字段信息并计算熵值"""
        logger.info("=== 步骤1：收集字段信息并计算熵值 ===")
        
        field_infos = []
        table_count = 0
        
        for table in context.database_schema.tables[:self.max_tables]:
            # 黑名单检查已删除，aid_info表已在数据库获取源头过滤
            
            # 收集表的字段信息
            table_fields = self._collect_table_fields(table, context)
            field_infos.extend(table_fields)
            
            table_count += 1
            if table_count >= self.max_tables:
                logger.warning(f"已达到最大表数限制 ({self.max_tables})")
                break
        
        context.field_infos = field_infos
        logger.info(f"收集完成：共 {len(field_infos)} 个字段")
        
        return context
    
    def _collect_table_fields(self, table, context: FieldClassificationContext) -> List[FieldInfo]:
        """收集单个表的字段信息"""
        logger.info(f"收集表 {table.name} 的字段信息")
        
        # 获取表数据
        column_names = [col.name for col in table.columns]
        sql = f"SELECT {', '.join(column_names)} FROM {table.name} LIMIT {self.sample_size}"
        
        rows = context.database_service.execute_query(sql)
        if not rows:
            return []
        
        # 按字段组织信息
        field_infos = []
        for col in table.columns:
            # 收集样本（包括空值）
            all_samples = [row.get(col.name) for row in rows]
            non_null_samples = [s for s in all_samples if s is not None]
            
            # 即使所有样本都是空值，也要创建字段信息
            # 计算熵值（只基于非空样本）
            entropy = calculate_entropy(non_null_samples) if non_null_samples else 0.0
            
            # 创建字段信息
            field_info = FieldInfo(
                field_name=f"{table.name}.{col.name}",
                table_name=table.name,
                column_name=col.name,
                data_type=col.data_type,
                samples=non_null_samples[:10] if non_null_samples else [],  # 只保留10个样本
                entropy=entropy
            )
            
            field_infos.append(field_info)
            logger.info(f"  - {field_info.field_name}: 熵值={entropy:.3f}, 非空样本数={len(non_null_samples)}")
        
        return field_infos
    



class ClassifyFieldsWithLLMStep(PipelineStep[FieldClassificationContext]):
    """步骤2：使用LLM进行字段分类"""
    
    def __init__(self):
        super().__init__(name="Classify Fields with LLM")
        self.batch_size = DEFAULT_BATCH_SIZE
    
    def execute(self, context: FieldClassificationContext) -> FieldClassificationContext:
        """使用LLM对字段进行分类"""
        logger.info("=== 步骤2：使用LLM进行字段分类 ===")
        
        if not context.llm_service or not context.prompt_service:
            logger.warning("未提供LLM服务，使用默认分类")
            context.field_classifications = self._create_default_classifications(context.field_infos)
            return context
        
        # 批量处理字段
        classifications = []
        for i in range(0, len(context.field_infos), self.batch_size):
            batch = context.field_infos[i:i+self.batch_size]
            logger.info(f"处理批次 {i//self.batch_size + 1}: {len(batch)} 个字段")
            
            batch_classifications = self._classify_batch(batch, context.domain_knowledge, context)
            classifications.extend(batch_classifications)
        
        context.field_classifications = classifications
        logger.info(f"LLM分类完成：共分类 {len(classifications)} 个字段")
        
        # 生成统计信息
        context.classification_stats = self._generate_statistics(classifications)
        self._log_statistics(context.classification_stats)
        
        return context
    
    def _classify_batch(self, field_infos: List[FieldInfo], 
                       domain_knowledge: DomainKnowledge,
                       context: FieldClassificationContext) -> List[FieldClassification]:
        """对一批字段进行分类"""
        # 准备数据
        batch_data = []
        for field_info in field_infos:
            batch_data.append({
                'field_name': field_info.field_name,
                'data_type': field_info.data_type,
                'samples': field_info.samples[:5],
                'entropy': field_info.entropy
            })
        
        # 渲染提示词
        prompt = context.prompt_service.render(
            'analysis/03_field_classification.j2',
            domain_type=domain_knowledge.domain_type,
            domain_description='\n'.join(domain_knowledge.business_concepts),
            fields=batch_data
        )
        
        # 调用LLM
        response = context.llm_service.generate(prompt)
        
        # 解析响应
        llm_results = self._parse_llm_response(response)
        
        # 创建分类对象
        classifications = []
        for field_info in field_infos:
            llm_result = llm_results.get(field_info.field_name, {})
            
            classification = FieldClassification(
                field_name=field_info.field_name,
                category=self._parse_category(llm_result.get('category', 'other')),
                data_type=field_info.data_type,
                confidence=0.8 if llm_result else 0.3,
                # 可选字段
                table_name=field_info.table_name,
                column_name=field_info.column_name,
                field_type=llm_result.get('field_type', '未知'),
                importance=self._parse_importance(llm_result.get('importance', 'medium')),
                entropy_level=self._get_entropy_level(field_info.entropy)
            )
            
            classifications.append(classification)
        
        return classifications
    
    def _parse_llm_response(self, response: str) -> Dict[str, Dict]:
        """解析LLM响应"""
        try:
            # 提取JSON
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                return json.loads(json_str)
        except Exception as e:
            logger.warning(f"解析LLM响应失败: {e}")
        
        return {}
    
    def _parse_category(self, category_str: str) -> FieldCategory:
        """解析类别字符串"""
        category_map = {
            'identifier': FieldCategory.IDENTIFIER,
            'measure': FieldCategory.MEASURE,
            'dimension': FieldCategory.DIMENSION,
            'datetime': FieldCategory.DATETIME,
            'text': FieldCategory.TEXT,
            'boolean': FieldCategory.BOOLEAN,
            'other': FieldCategory.OTHER
        }
        return category_map.get(category_str.lower(), FieldCategory.OTHER)
    
    def _parse_importance(self, importance_str: str) -> float:
        """解析重要性"""
        importance_map = {
            'high': 0.8,
            'medium': 0.5,
            'low': 0.3
        }
        return importance_map.get(importance_str.lower(), 0.5)
    
    def _get_entropy_level(self, entropy: float) -> str:
        """获取熵值级别
        
        参数:
            entropy: 熵值（0-1）
            
        返回:
            熵值级别：low, medium, high
        """
        return get_entropy_level(entropy)
    

    
    def _create_default_classifications(self, field_infos: List[FieldInfo]) -> List[FieldClassification]:
        """创建默认分类（当LLM不可用时）"""
        classifications = []
        for field_info in field_infos:
            classification = FieldClassification(
                field_name=field_info.field_name,
                category=FieldCategory.OTHER,
                data_type=field_info.data_type,
                confidence=0.1,
                table_name=field_info.table_name,
                column_name=field_info.column_name,
                field_type='未知',
                importance=0.5,
                entropy_level=self._get_entropy_level(field_info.entropy)
            )
            classifications.append(classification)
        return classifications
    
    def _generate_statistics(self, classifications: List[FieldClassification]) -> Dict[str, Any]:
        """生成统计信息"""
        category_counts = Counter()
        type_counts = Counter()
        importance_counts = Counter()
        
        for c in classifications:
            category_counts[c.category.value] += 1
            if c.field_type:
                type_counts[c.field_type] += 1
            importance_counts[c.importance] += 1
        
        return {
            'total_fields': len(classifications),
            'category_distribution': dict(category_counts),
            'type_distribution': dict(type_counts.most_common(10)),  # 只保留前10个
            'importance_distribution': dict(importance_counts)
        }
    
    def _log_statistics(self, stats: Dict[str, Any]) -> None:
        """输出统计信息"""
        logger.info("字段分类统计：")
        logger.info(f"  - 总字段数：{stats['total_fields']}")
        logger.info(f"  - 类别分布：{stats['category_distribution']}")
        logger.info(f"  - 类型TOP10：{stats['type_distribution']}")
        logger.info(f"  - 重要性分布：{stats['importance_distribution']}")


# ========== 主管道类 ==========

class FieldClassificationPipeline(Pipeline[FieldClassificationContext]):
    """字段分类管道（优化版）
    
    完整的字段分类流程：
    1. 收集字段信息并计算熵值
    2. 使用LLM进行智能分类
    """
    
    def __init__(self, services: ServiceContainer, name: str = "Field Classification Pipeline"):
        """初始化字段分类管道"""
        super().__init__(name=name)
        
        # 保存服务引用（用于创建上下文）
        self.services = services
        
        # 添加步骤
        self.add_step(CollectAndAnalyzeFieldsStep())
        self.add_step(ClassifyFieldsWithLLMStep())
        
        logger.info(f"初始化 {name}，包含 {len(self.steps)} 个步骤")
    
    def execute(self, database_schema: DatabaseSchema, database_name: str,
                domain_knowledge: Optional[DomainKnowledge] = None) -> FieldClassificationResult:
        """执行字段分类管道
        
        参数:
            database_schema: 数据库结构
            database_name: 数据库名称
            domain_knowledge: 领域知识（可选）
            
        返回:
            FieldClassificationResult: 包含完整分类结果的步骤对象
        """
        start_time = datetime.now()
        
        try:
            # 创建上下文
            context = FieldClassificationContext(
                database_schema=database_schema,
                database_name=database_name,
                domain_knowledge=domain_knowledge,
                database_service=self.services.database_service,
                llm_service=self.services.llm_service,
                prompt_service=self.services.prompt_service
            )
            
            # 执行管道
            result_context = self.run(context)
            
            # 构建熵值信息字典
            field_entropy_info = self._build_entropy_info_dict(result_context)
            
            # 构建字段分类字典（兼容旧接口）
            field_classifications_dict = self._build_classifications_dict(result_context.field_classifications)
            
            logger.info(f"字段分类完成: 处理了 {len(result_context.field_infos)} 个字段")
            
            # 返回步骤结果对象
            return FieldClassificationResult(
                step_name="field_classification",
                start_time=start_time,
                end_time=datetime.now(),
                status="success",
                field_infos=result_context.field_infos,
                field_classifications=result_context.field_classifications,
                field_classifications_dict=field_classifications_dict,
                field_entropy_info=field_entropy_info,
                classification_stats=result_context.classification_stats or {}
            )
            
        except Exception as e:
            logger.error(f"字段分类失败: {e}")
            return FieldClassificationResult(
                step_name="field_classification",
                start_time=start_time,
                end_time=datetime.now(),
                status="failed",
                error_message=str(e)
            )
    
    def execute_legacy(self, database_schema: DatabaseSchema, database_name: str,
                      domain_knowledge: Optional[DomainKnowledge] = None) -> Dict[str, Any]:
        """执行字段分类管道（旧版接口，用于兼容）
        
        返回:
            包含分类结果的字典
        """
        result = self.execute(database_schema, database_name, domain_knowledge)
        if result.is_success():
            return {
                'field_classifications': result.field_classifications,
                'field_classification_models': result.field_classifications,
                'field_entropy_info': result.field_entropy_info
            }
        else:
            raise Exception(result.error_message)
    
    def classify_fields(self,
                       database_schema: DatabaseSchema,
                       database_name: str,
                       domain_knowledge: Optional[DomainKnowledge] = None) -> List[FieldClassification]:
        """执行字段分类"""
        # 创建上下文
        context = FieldClassificationContext(
            database_schema=database_schema,
            database_name=database_name,
            domain_knowledge=domain_knowledge,
            database_service=self.services.database_service,
            llm_service=self.services.llm_service,
            prompt_service=self.services.prompt_service
        )
        
        # 执行管道
        result_context = self.run(context)
        
        # 返回分类结果
        return result_context.field_classifications
    
    def _build_entropy_info_dict(self, context: FieldClassificationContext) -> Dict[str, FieldEntropyInfo]:
        """构建熵值信息字典"""
        entropy_info_dict = {}
        
        logger.debug(f"从 {len(context.field_infos)} 个字段信息构建熵值字典")
        
        for field_info in context.field_infos:
            # 计算熵值级别
            entropy_level = get_entropy_level(field_info.entropy)
            
            # 计算唯一值比例（使用样本估算）
            unique_values = len(set(field_info.samples)) if field_info.samples else 0
            total_samples = len(field_info.samples)
            unique_ratio = unique_values / total_samples if total_samples > 0 else 0.0
            
            # 计算空值比例（如果所有样本都是空值，则为1.0）
            # 注意：这里我们无法准确计算空值比例，因为已经过滤了
            # 但如果 samples 为空，可以假设全是空值
            null_ratio = 1.0 if not field_info.samples else 0.0
            
            # 创建熵值信息对象
            entropy_info = FieldEntropyInfo(
                field_name=field_info.field_name,
                entropy_value=field_info.entropy,
                unique_ratio=unique_ratio,
                null_ratio=null_ratio,
                entropy_level=entropy_level
            )
            
            entropy_info_dict[field_info.field_name] = entropy_info
        
        return entropy_info_dict
    
    def _build_classifications_dict(self, field_classifications: List[FieldClassification]) -> Dict[str, Dict[str, Any]]:
        """构建字段分类字典（兼容旧接口）
        
        参数:
            field_classifications: 字段分类列表
            
        返回:
            字段分类字典，键为字段名，值为分类信息字典
        """
        field_classifications_dict = {}
        
        for fc in field_classifications:
            # 获取字段键
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
        
        return field_classifications_dict
    
    def _get_field_key(self, fc: FieldClassification) -> Optional[str]:
        """获取字段分类的键
        
        参数:
            fc: 字段分类对象
            
        返回:
            字段键（表名.列名格式）
        """
        if hasattr(fc, 'table_name') and hasattr(fc, 'column_name') and fc.table_name and fc.column_name:
            return f"{fc.table_name}.{fc.column_name}"
        elif hasattr(fc, 'field_name') and fc.field_name:
            return fc.field_name
        return None



# ========== 便捷函数 ==========

def classify_database_fields(
    database_schema: DatabaseSchema,
    database_name: str,
    services: ServiceContainer,
    **kwargs
) -> List[FieldClassification]:
    """便捷函数：执行字段分类"""
    pipeline = FieldClassificationPipeline(services)
    return pipeline.classify_fields(
        database_schema=database_schema,
        database_name=database_name,
        **kwargs
    )