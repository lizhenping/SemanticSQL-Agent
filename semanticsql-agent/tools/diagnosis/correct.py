"""Phase 3 / Correct: 语义错误修正（tools/diagnosis/correct.py）

论文 §III.E Eq.4 的第三个算子 Correct：
    (q', s', r') = Correct(q, s, r, Φ, K)

论文 L272 要求 Correct 做三件事：
1. 替换 s 里无效的 schema 元素（用 Φ 里的合法替代）
2. 必要时改写 q 消除歧义/错误假设
3. 把 detected errors + applied corrections 追加到 r 保历史

设计：CorrectTool 注入 Evidence Φ + 原始 triple + errors，调 LLM 生成
修正后的 (q, s)，然后组装新的 Rationale（含 correction_history 追加）。

不照搬旧 reflection_tools，按论文 §III.E 重新实现。
"""

import logging
import re
from typing import Optional

from tools.base_tool import BaseSemanticTool
from infra.database import DatabaseManager
from models.diagnosis import Error, ErrorType, Correction
from models.synthesis import Triple, Question, SQLResult


class CorrectTool(BaseSemanticTool):
    """Phase 3 Correct：基于 errors + Evidence Φ 修正 triple

    用法：
        tool = CorrectTool(llm=llm, db=db, kbase=kbase, prompt_manager=pm)
        new_triple = tool.run(triple, errors, evidence, iteration=1)
    """

    def __init__(self, dialect: str = "sqlite", **kwargs):
        super().__init__(name="correct_tool", **kwargs)
        self.dialect = dialect

    def run(
        self,
        triple: Triple,
        errors: list[Error],
        evidence,  # Evidence（避免循环 import 用 duck typing）
        iteration: int,
    ) -> Triple:
        """修正 triple → 返回新的 Triple（保留 correction_history）

        Args:
            triple: 当前迭代的 (q, s, r)
            errors: Diagnose 产出的 E
            evidence: Retrieve 产出的 Φ
            iteration: 当前迭代号（用于 history 追踪）
        """
        self.logger.debug(
            f"🔧 Correct {triple.question_id} iter={iteration} "
            f"errors={len(errors)}"
        )

        sql_before = triple.sql_result.sql
        sql_after = sql_before
        question_after = triple.question.text

        # 1. LLM 生成修正后的 SQL（必要时也改写 q）
        if self.llm is not None:
            sql_after, question_after = self._llm_correct(
                triple, errors, evidence
            )
            sql_after = self._postprocess_sql(sql_after)
        else:
            # 无 LLM 时退化为启发式：只处理纯执行类错误的 trivial 情况
            self.logger.warning("correct_tool 未注入 llm，跳过 LLM 修正")

        # 2. 执行新 SQL 看是否真的修好了
        new_sql_result = self._execute(sql_after, triple.sql_result.dialect)

        # 3. 组装修正记录（论文要求 append to r 保历史）
        correction = Correction(
            iteration=iteration,
            errors_addressed=[e.type for e in errors],
            sql_before=sql_before,
            sql_after=sql_after,
            summary=self._summarize_errors(errors),
        )

        # 4. 构造新 triple：question 改写、sql 替换、rationale 追加历史
        new_question = triple.question
        if question_after and question_after != triple.question.text:
            new_question = triple.question.model_copy(update={"text": question_after})

        new_rationale = triple.rationale.model_copy(deep=True)
        new_rationale.errors = errors
        new_rationale.correction_history.append(correction)
        new_rationale.expected_output = self._expected_output_from_evidence(evidence)

        return Triple(
            question=new_question,
            sql_result=new_sql_result,
            rationale=new_rationale,
        )

    # ============================================================
    # LLM 修正（论文 L272：replace invalid schema elements / reformulate q）
    # ============================================================

    def _llm_correct(
        self, triple: Triple, errors: list[Error], evidence
    ) -> tuple[str, str]:
        """调 LLM 生成修正后的 (sql, question)"""
        # 把 Evidence Φ 渲染成可读文本
        evidence_text = self._render_evidence(evidence)
        errors_text = self._render_errors(errors)

        prompt = self._render_prompt(
            "diagnosis/correct.j2",
            question=triple.question.text,
            sql=triple.sql_result.sql,
            rationale=triple.rationale.focus,
            errors=errors_text,
            evidence=evidence_text,
            dialect=self.dialect,
        )
        result = self._llm_generate_json(prompt)

        sql = result.get("sql") or result.get("corrected_sql") or triple.sql_result.sql
        question = (
            result.get("question")
            or result.get("corrected_question")
            or triple.question.text
        )
        return sql, question

    # ============================================================
    # SQL 后处理 + 执行（复用 sql_synth 的逻辑模式）
    # ============================================================

    def _postprocess_sql(self, sql: str) -> str:
        """清理 markdown 标记 + 规范化"""
        sql = re.sub(r"```sql\s*", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"```\s*", "", sql)
        sql = re.sub(r"\s+", " ", sql).strip()
        if sql and not sql.endswith(";"):
            sql += ";"
        return sql

    def _execute(self, sql: str, dialect: str) -> SQLResult:
        """执行修正后的 SQL，结果记入 SQLResult"""
        result = SQLResult(sql=sql, dialect=dialect, corrected_by_reflection=True)
        if self.db is None:
            return result
        try:
            ret = self.db.execute_sql_safe(sql, limit=100)
            if ret.get("success"):
                result.executed = True
                result.execution_success = True
                result.result_count = len(ret.get("data", []))
            else:
                result.executed = True
                result.execution_success = False
                result.execution_error = str(ret.get("error", "执行失败"))
        except Exception as e:
            result.executed = True
            result.execution_success = False
            result.execution_error = str(e)
        return result

    # ============================================================
    # 渲染辅助
    # ============================================================

    def _render_errors(self, errors: list[Error]) -> str:
        """把 errors 渲染成给 LLM 的可读列表"""
        if not errors:
            return "(无错误)"
        lines = []
        for i, e in enumerate(errors, 1):
            loc = e.location
            loc_str = loc.clause or ""
            if loc.table:
                loc_str += f" {loc.table}"
            if loc.column:
                loc_str += f".{loc.column}"
            lines.append(f"{i}. [{e.type.value}] {loc_str}: {e.detail}")
        return "\n".join(lines)

    def _render_evidence(self, evidence) -> str:
        """把 Evidence Φ 渲染成给 LLM 的可读文本（供 Correct 参考）"""
        if evidence is None:
            return "(无证据)"
        parts: list[str] = []

        # K4 列语义（供替换错误列）
        if getattr(evidence, "columns", None):
            parts.append("可用列（K4 列语义）：")
            for key, col in evidence.columns.items():
                parts.append(f"  - {key}: {col.description}")
        # K3 字段类型（聚合错误时找正确 measure 列）
        if getattr(evidence, "field_types", None):
            parts.append("字段类型（K3）：")
            for key, cat in evidence.field_types.items():
                parts.append(f"  - {key}: {cat.value}")
        # K6 关系（JOIN 错误时找正确连接键）
        if getattr(evidence, "relations", None):
            parts.append("可用关系（K6）：")
            for rel in evidence.relations:
                src = f"{rel.source_table}.{rel.source_column}" if rel.source_column else rel.source_table
                tgt = f"{rel.target_table}.{rel.target_column}" if rel.target_column else rel.target_table
                parts.append(f"  - {src} → {tgt} ({rel.relationship_type})")
        # K2 域规则
        dr = getattr(evidence, "domain_rules", None)
        if dr is not None and getattr(dr, "description", ""):
            parts.append(f"域规则（K2）：{dr.description}")

        return "\n".join(parts) if parts else "(无具体证据)"

    def _summarize_errors(self, errors: list[Error]) -> str:
        """生成 correction.summary"""
        if not errors:
            return "无错误"
        types = sorted({e.type.value for e in errors})
        return f"修正 {len(errors)} 个错误: {', '.join(types)}"

    def _expected_output_from_evidence(self, evidence) -> str:
        """从证据里提炼期望输出提示（留给下游参考）"""
        if evidence is None:
            return ""
        cols = getattr(evidence, "columns", None) or {}
        if cols:
            # 取前几个合法列名作为期望输出提示
            names = list(cols.keys())[:3]
            return "期望涉及列: " + ", ".join(names)
        return ""
