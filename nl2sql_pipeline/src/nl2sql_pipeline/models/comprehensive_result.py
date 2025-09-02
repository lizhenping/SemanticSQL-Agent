"""综合分析结果模型

包含所有步骤的完整分析结果。
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime

from .database import DatabaseSchema
from .analysis import (
    DomainKnowledge,
    ColumnDescription,
    TableDescription,
    ERRelationship
)
from .step_results import (
    SchemaExtractionResult,
    DomainAnalysisResult,
    FieldClassificationResult,
    ColumnDescriptionResult,
    ColumnCorrectionResult,
    TableDescriptionResult,
    DomainOptimizationResult,
    ERAnalysisResult
)


@dataclass
class ComprehensiveAnalysisResult:
    """综合分析结果
    
    包含所有8个步骤的完整分析结果，提供便捷的数据访问接口。
    """
    # 基本信息
    database_name: str
    analysis_start_time: datetime
    analysis_end_time: datetime
    
    # 所有步骤的结果（完整保存）
    schema_extraction: SchemaExtractionResult
    domain_analysis: DomainAnalysisResult
    field_classification: FieldClassificationResult
    column_description: ColumnDescriptionResult
    column_correction: ColumnCorrectionResult
    table_description: TableDescriptionResult
    domain_optimization: DomainOptimizationResult
    er_analysis: ERAnalysisResult
    
    # ========== 便捷访问属性 ==========
    
    @property
    def total_duration_seconds(self) -> float:
        """获取总分析时长（秒）"""
        return (self.analysis_end_time - self.analysis_start_time).total_seconds()
    
    @property
    def database_schema(self) -> Optional[DatabaseSchema]:
        """获取数据库架构"""
        return self.schema_extraction.database_schema
    
    @property
    def initial_domain_knowledge(self) -> Optional[DomainKnowledge]:
        """获取初始领域知识"""
        return self.domain_analysis.domain_knowledge
    
    @property
    def final_domain_knowledge(self) -> Optional[DomainKnowledge]:
        """获取优化后的领域知识"""
        return self.domain_optimization.optimized_domain_knowledge
    
    @property
    def final_column_descriptions(self) -> Dict[str, ColumnDescription]:
        """获取最终的列描述（修正后）"""
        return self.column_correction.corrected_column_descriptions
    
    @property
    def table_descriptions(self) -> Dict[str, TableDescription]:
        """获取表描述"""
        return self.table_description.table_descriptions
    
    @property
    def er_relationships(self) -> Dict[str, List[ERRelationship]]:
        """获取ER关系"""
        return self.er_analysis.er_relationships
    
    @property
    def field_entropy_info(self) -> Dict[str, Any]:
        """获取字段熵值信息"""
        return self.field_classification.field_entropy_info
    
    # ========== 统计方法 ==========
    
    def get_analysis_stats(self) -> Dict[str, Any]:
        """获取综合分析统计"""
        return {
            "database_name": self.database_name,
            "total_duration_seconds": self.total_duration_seconds,
            "total_tables": self.schema_extraction.table_count,
            "total_columns": self.schema_extraction.total_columns,
            "classified_fields": self.field_classification.classified_fields,
            "described_columns": self.column_description.described_columns,
            "corrected_columns": self.column_correction.corrected_count,
            "described_tables": self.table_description.described_tables,
            "discovered_relationships": self.er_analysis.total_relationships,
            "step_stats": self.get_step_stats()
        }
    
    def get_step_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取每个步骤的统计信息"""
        steps = [
            self.schema_extraction,
            self.domain_analysis,
            self.field_classification,
            self.column_description,
            self.column_correction,
            self.table_description,
            self.domain_optimization,
            self.er_analysis
        ]
        
        return {
            step.step_name: {
                "status": step.status,
                "duration_seconds": step.duration_seconds,
                "error_message": step.error_message
            }
            for step in steps
        }
    
    def get_successful_steps(self) -> List[str]:
        """获取成功执行的步骤列表"""
        steps = [
            self.schema_extraction,
            self.domain_analysis,
            self.field_classification,
            self.column_description,
            self.column_correction,
            self.table_description,
            self.domain_optimization,
            self.er_analysis
        ]
        
        return [step.step_name for step in steps if step.is_success()]
    
    def get_failed_steps(self) -> List[str]:
        """获取失败的步骤列表"""
        steps = [
            self.schema_extraction,
            self.domain_analysis,
            self.field_classification,
            self.column_description,
            self.column_correction,
            self.table_description,
            self.domain_optimization,
            self.er_analysis
        ]
        
        return [step.step_name for step in steps if step.status == "failed"]
    
    def is_complete(self) -> bool:
        """检查分析是否完整成功"""
        return len(self.get_failed_steps()) == 0
    
    # ========== 数据访问方法 ==========
    
    def get_table_description(self, table_name: str) -> Optional[TableDescription]:
        """获取特定表的描述"""
        return self.table_descriptions.get(table_name)
    
    def get_column_description(self, table_name: str, column_name: str) -> Optional[ColumnDescription]:
        """获取特定列的描述"""
        field_key = f"{table_name}.{column_name}"
        return self.final_column_descriptions.get(field_key)
    
    def get_table_relationships(self, table_name: str) -> List[ERRelationship]:
        """获取特定表的关系"""
        return self.er_relationships.get(table_name, [])
    
    # ========== 序列化方法 ==========
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（用于序列化）"""
        return {
            "database_name": self.database_name,
            "analysis_start_time": self.analysis_start_time.isoformat(),
            "analysis_end_time": self.analysis_end_time.isoformat(),
            "total_duration_seconds": self.total_duration_seconds,
            "analysis_stats": self.get_analysis_stats(),
            "successful_steps": self.get_successful_steps(),
            "failed_steps": self.get_failed_steps(),
            # 可以根据需要添加更多序列化逻辑
        }
    
    def summary(self) -> str:
        """生成分析摘要"""
        stats = self.get_analysis_stats()
        
        return f"""
数据库分析报告
==============
数据库名称: {self.database_name}
分析时间: {self.analysis_start_time.strftime('%Y-%m-%d %H:%M:%S')} - {self.analysis_end_time.strftime('%Y-%m-%d %H:%M:%S')}
总耗时: {self.total_duration_seconds:.2f} 秒

统计信息:
- 表数量: {stats['total_tables']}
- 列数量: {stats['total_columns']}
- 已分类字段: {stats['classified_fields']}
- 已描述列: {stats['described_columns']}
- 已修正列: {stats['corrected_columns']}
- 已描述表: {stats['described_tables']}
- 发现的关系: {stats['discovered_relationships']}

步骤执行状态:
- 成功: {len(self.get_successful_steps())} 个
- 失败: {len(self.get_failed_steps())} 个
"""