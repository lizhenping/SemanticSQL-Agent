"""分析相关的管道

包含数据库分析流程的8个步骤管道。
"""

from .schema_extraction_pipeline import SchemaExtractionPipeline
# 初始领域分析模块
from .initial_domain_analysis_pipeline import DomainAnalysisPipeline
from .field_classification_pipeline import FieldClassificationPipeline
from .column_description_pipeline import ColumnDescriptionPipeline
from .column_correction_pipeline import ColumnCorrectionPipeline
from .table_description_pipeline import TableDescriptionPipeline
from .domain_optimization_pipeline import DomainOptimizationPipeline
from .er_analysis_pipeline import ERAnalysisPipeline

__all__ = [
    'SchemaExtractionPipeline',
    'DomainAnalysisPipeline',
    'FieldClassificationPipeline',
    'ColumnDescriptionPipeline',
    'ColumnCorrectionPipeline',
    'TableDescriptionPipeline',
    'DomainOptimizationPipeline',
    'ERAnalysisPipeline'
]