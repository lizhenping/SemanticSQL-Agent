"""Phase 3 / Diagnose: 语义错误检测（tools/diagnosis/diagnose.py）

论文 §III.E Eq.4 的第一个算子 Diagnose：
    E = Diagnose(q, s, r, K, I)

混合两类检查（论文原话 "combines deterministic constraint checking
with LLM-based semantic inspection"）：

1. 程序化校验（确定性，对齐论文 L270）：
   - check_columns:    s 引用的列是否存在 + K4 语义匹配（kbase 已实现）
   - check_joins:      JOIN 是否符合 K6 外键结构（kbase 已实现）
   - check_aggregation: AVG/SUM 参数是否符合 K3 类型（kbase 已实现，Fig.1 反例）
   - check_execution:  s 在数据库 I 上能否执行（执行失败/空结果）

2. LLM 语义审查（论文 L270 "holistic semantic inconsistencies that
   structural checks cannot capture"）：
   - 对照 q 的意图和 K2 域规则审查 r，捕捉结构检查抓不到的语义不一致

产物：list[Error]（论文 E），每个带 type + location。

设计：DiagnoseTool 组合 SQLAstParser（解析 s）+ kbase.check_* + LLM 审查。
不照搬旧 reflection_tools，按论文 §III.E 重新实现。
"""

import logging
import re
from typing import Optional

from tools.base_tool import BaseSemanticTool
from infra.sql_ast import SQLAstParser, SqlglotParser
from infra.database import DatabaseManager
from models.diagnosis import Error, ErrorType, ErrorLocation, SemanticClass
from models.synthesis import Triple


class DiagnoseTool(BaseSemanticTool):
    """Phase 3 Diagnose：检测 (q, s, r) 的语义错误 → list[Error]

    用法：
        tool = DiagnoseTool(llm=llm, db=db, kbase=kbase, prompt_manager=pm)
        errors = tool.run(triple)
    """

    def __init__(
        self,
        ast_parser: Optional[SQLAstParser] = None,
        use_llm_review: bool = True,
        **kwargs,
    ):
        super().__init__(name="diagnose_tool", **kwargs)
        # SQL AST 解析器（可注入 Fake 做单测；默认 sqlglot）
        self.ast_parser = ast_parser or SqlglotParser()
        # 是否启用 LLM 语义审查（程序化 check 总是开）
        self.use_llm_review = use_llm_review

    def run(self, triple: Triple) -> list[Error]:
        """对单个 triple 做完整诊断 → list[Error]"""
        self.logger.debug(f"🔍 Diagnose {triple.question_id}")
        sql = triple.sql_result.sql
        if not sql:
            return [Error(
                type=ErrorType.SYNTAX_ERROR,
                detail="SQL 为空",
            )]

        errors: list[Error] = []

        # ---- 程序化校验（论文 L270 确定性部分）----
        errors.extend(self._deterministic_checks(triple))

        # ---- LLM 语义审查（论文 L270 "semantic side"）----
        if self.use_llm_review and self.llm is not None:
            errors.extend(self._llm_semantic_review(triple))

        return errors

    # ============================================================
    # 程序化校验（调 kbase.check_*，论文 §III.E 的 4 个 check）
    # ============================================================

    def _deterministic_checks(self, triple: Triple) -> list[Error]:
        """4 个程序化 check：columns / joins / aggregation / execution"""
        if self.kbase is None:
            return []
        sql = triple.sql_result.sql
        errors: list[Error] = []

        # 1. 列存在性 + K4 语义（kbase.check_columns）
        ast_columns = self.ast_parser.extract_columns(sql)
        errors.extend(self.kbase.check_columns(ast_columns))

        # 2. JOIN vs K6 外键（kbase.check_joins）
        ast_joins = self.ast_parser.extract_joins(sql)
        errors.extend(self.kbase.check_joins(ast_joins))

        # 3. 聚合 vs K3 类型（kbase.check_aggregation，Fig.1 反例）
        ast_aggs = self.ast_parser.extract_aggregates(sql)
        errors.extend(self.kbase.check_aggregation(ast_aggs))

        # 4. 执行性（论文 "executes s on I to verify executability"）
        errors.extend(self._execution_check(triple))

        return errors

    def _execution_check(self, triple: Triple) -> list[Error]:
        """执行性检查（论文 B 类失败：数据库自己报告的失败）

        论文 §III.E：执行与 schema 检查覆盖 "whether a query does not parse,
        references a column that does not exist, or violates a constraint"。
        **空结果不算失败**——一个语义正确的问题完全可能合法地返回 0 行
        （如"列出满足某条件的记录"而无记录满足），把空结果当错误会诱导
        修正循环去放宽正确的 WHERE 条件，反而破坏语义。
        """
        errors: list[Error] = []
        sr = triple.sql_result

        # 若 Phase 2 已执行过，直接用其结果
        if sr.executed:
            if sr.execution_success is False:
                errors.append(Error(
                    type=ErrorType.EXECUTION_FAILED,
                    location=ErrorLocation(clause="EXECUTION"),
                    detail=sr.execution_error or "SQL 执行失败",
                ))
            return errors

        # Phase 2 未执行则现执行一次
        if self.db is None:
            return errors
        try:
            ret = self.db.execute_sql_safe(sr.sql, limit=100)
            if not ret.get("success"):
                errors.append(Error(
                    type=ErrorType.EXECUTION_FAILED,
                    location=ErrorLocation(clause="EXECUTION"),
                    detail=str(ret.get("error", "执行失败")),
                ))
            else:
                data = ret.get("data", [])
                sr.executed = True
                sr.execution_success = True
                sr.result_count = len(data)  # 空结果仅记录，不作为错误
        except Exception as e:
            sr.executed = True
            sr.execution_success = False
            sr.execution_error = str(e)
            errors.append(Error(
                type=ErrorType.EXECUTION_FAILED,
                location=ErrorLocation(clause="EXECUTION"),
                detail=str(e),
            ))
        return errors

    # ============================================================
    # LLM 语义审查（论文 §III.E "semantic checks"，Definition 1 顺序）
    # ============================================================

    def _llm_semantic_review(self, triple: Triple) -> list[Error]:
        """LLM 按 Definition 1 顺序审查：问题有效性 → 意图匹配 → 使用一致性

        论文 Diagnose(τ, K, D)：K 以"所涉元素的相关知识条目"形式注入提示；
        每个违例解析为论文 e_j=(t_j,u_j,λ_j,v_j)，即
        (semantic_class, artifact, location, detail/violated_condition)。
        """
        try:
            prompt = self._render_prompt(
                "diagnosis/semantic_review.j2",
                question=triple.question.text,
                sql=triple.sql_result.sql,
                rationale=triple.rationale.focus,
                knowledge_context=self._kb_digest(triple.sql_result.sql),
            )
            result = self._llm_generate_json(prompt)
        except Exception as e:
            self.logger.warning(f"LLM 语义审查失败 {triple.question_id}: {e}")
            # A failed review is not evidence that the pair is semantically clean.
            return [Error(
                type=ErrorType.SEMANTIC_REVIEW_FAILED,
                detail=f"LLM semantic review failed: {e}",
                artifact="s",
                detector=DetectorType.LLM,
            )]

        errors: list[Error] = []
        issues = result.get("issues", [])
        if not isinstance(issues, list):
            return errors
        for issue in issues:
            if not isinstance(issue, dict):
                continue
            detail = (issue.get("detail") or issue.get("description") or "").strip()
            if not detail:
                continue
            # 论文七类 t_j（非法类名兜底为通用语义不一致）
            try:
                sc = SemanticClass(str(issue.get("class", "")).strip())
            except ValueError:
                sc = None
            artifact = (issue.get("artifact") or "s").strip().lower()
            if artifact not in {"q", "s", "r"}:
                artifact = "s"
            errors.append(Error(
                type=ErrorType.SEMANTIC_INCONSISTENCY,
                location=ErrorLocation(
                    clause=issue.get("clause", ""),
                    column=issue.get("column") or None,
                    table=issue.get("table") or None,
                ),
                detail=detail,
                semantic_class=sc,
                artifact=artifact,
                violated_condition=(issue.get("condition") or "").strip(),
            ))
        return errors

    def _kb_digest(self, sql: str) -> str:
        """聚合所涉 schema 元素的 K 条目，作为 Diagnose 的证据上下文（论文 τ,K,D）

        只取与 SQL 涉及的表/列相关的条目，避免整库 K 撑爆提示：
        K2 域规则全量 + K3/K4（SQL 涉及列）+ K5（涉及表约束）+ K6（涉及表关系）。
        """
        if self.kbase is None:
            return ""
        parts: list[str] = []

        domain = self.kbase.get_domain()
        if domain is not None and getattr(domain, "description", ""):
            parts.append(f"[K2 域规则] {domain.description}")

        try:
            extracted_tables = self.ast_parser.extract_tables(sql) if hasattr(self.ast_parser, "extract_tables") else []
            # The parser contract returns table-name strings, not (table, alias) pairs.
            touched_tables = {
                item[0] if isinstance(item, (tuple, list)) else item
                for item in extracted_tables
                if item
            }
        except Exception:
            touched_tables = set()
        if not touched_tables:
            # 兜底：从 SQL 文本里猜表名（K1 全部表名中出现者）
            try:
                names = self.kbase.get_table_names()
                touched_tables = {n for n in names if re.search(rf"\b{re.escape(n)}\b", sql, re.IGNORECASE)}
            except Exception:
                touched_tables = set()

        try:
            touched_cols = self.ast_parser.extract_columns(sql)
        except Exception:
            touched_cols = []

        # K4/K3：SQL 涉及的列
        for table, column in touched_cols[:30]:
            cs = self.kbase.get_column(table, column)
            if cs is not None:
                parts.append(f"[K4] {table}.{column}: {cs.description}")
            cat = self.kbase.get_field_type(table, column)
            if cat is not None:
                parts.append(f"[K3] {table}.{column}: {cat.value}")

        # K5：涉及表的约束/描述与 K1 观测实例样本
        for table in sorted(touched_tables)[:10]:
            ts = self.kbase.get_table_semantic(table)
            if ts is not None:
                parts.append(f"[K5] {table}: {ts.description}")
            schema_table = self.kbase.get_schema().get_table(table)
            if schema_table is not None:
                for col in schema_table.columns:
                    if any(tbl == table and column == col.name for tbl, column in touched_cols):
                        if col.sample_values:
                            observed = ", ".join(str(v) for v in col.sample_values[:5])
                            parts.append(
                                f"[K1 observed sample] {table}.{col.name}: "
                                f"{observed} (not a complete domain)"
                            )
                        parts.append(
                            f"[K1 metadata] {table}.{col.name}: "
                            f"entropy={col.entropy_level}, rows={schema_table.row_count}"
                        )

        # K6：涉及表之间的关系
        for rel in self.kbase.get_relations():
            if rel.source_table in touched_tables or rel.target_table in touched_tables:
                src = f"{rel.source_table}.{rel.source_column}" if rel.source_column else rel.source_table
                tgt = f"{rel.target_table}.{rel.target_column}" if rel.target_column else rel.target_table
                reason = f" ({rel.reason})" if rel.reason else ""
                parts.append(f"[K6] {src} → {tgt} {rel.relationship_type}{reason}")

        return "\n".join(parts)
