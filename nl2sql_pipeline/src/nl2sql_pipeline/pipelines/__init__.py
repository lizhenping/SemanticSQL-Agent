"""管道模块

包含所有管道相关的定义和实现。
"""

from .base import Pipeline, PipelineStep, PipelineContext

# 生成管道
from .generation import ScenarioDrivenGenerationPipeline

__all__ = [
    # 基类
    'Pipeline',
    'PipelineStep',
    'PipelineContext',
    # 生成管道
    'ScenarioDrivenGenerationPipeline'
]