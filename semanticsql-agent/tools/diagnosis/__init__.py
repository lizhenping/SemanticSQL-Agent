"""Phase 3 诊断工具包（tools/diagnosis/）

论文 §III.E Eq.4 的 Diagnose→Retrieve→Correct 循环的两个算子：
    DiagnoseTool → list[Error]   （4 程序化 check + LLM 语义审查）
    CorrectTool  → Triple        （LLM 修正 + Evidence 注入 + history 追加）

Retrieve 由 core.knowledge_store.KnowledgeBase.retrieve_evidence 实现，
不在此包（它是 K 的查询方法，不是独立工具）。

两个工具都继承 BaseSemanticTool，依赖注入。
"""

from tools.diagnosis.diagnose import DiagnoseTool
from tools.diagnosis.correct import CorrectTool

__all__ = ["DiagnoseTool", "CorrectTool"]
