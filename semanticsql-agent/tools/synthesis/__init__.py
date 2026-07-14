"""Phase 2 合成工具包（tools/synthesis/）

论文 §III.D 的 Generation (DS) 阶段，合成 (q, s, r) 三元组：
    QuestionSynthTool → q（场景驱动的问题合成）
    SQLSynthTool      → (s, r)（SQL + 结构化推理链）

两个工具都继承 BaseSemanticTool，依赖注入。
"""

from tools.synthesis.question_synth import QuestionSynthTool
from tools.synthesis.sql_synth import SQLSynthTool

__all__ = ["QuestionSynthTool", "SQLSynthTool"]
