"""编排层（core/）

固定三阶段流水线编排 + 知识库唯一真相源。
依赖方向：可依赖 tools/infra/models，不依赖 cli。

模块：
- knowledge_store.py: KnowledgeBase（K1..K6 唯一真相源 + Diagnose/Retrieve 方法）
- pipeline.py:         PipelineExecutor（三阶段固定编排，S7 建）
"""

from core.knowledge_store import KnowledgeBase
from core.pipeline import PipelineExecutor

__all__ = ["KnowledgeBase", "PipelineExecutor"]
