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
from typing import Optional

from tools.base_tool import BaseSemanticTool
from infra.sql_ast import SQLAstParser, SqlglotParser
from infra.database import DatabaseManager
from models.diagnosis import Error, ErrorType, ErrorLocation
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
        """执行性 + 空结果检查（论文第 4 个 check）"""
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
            elif sr.result_count is not None and sr.result_count == 0:
                errors.append(Error(
                    type=ErrorType.EMPTY_RESULT,
                    location=ErrorLocation(clause="EXECUTION"),
                    detail="SQL 执行返回空结果，可能 WHERE 条件过严或 JOIN 错误",
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
                sr.result_count = len(data)
                if len(data) == 0:
                    errors.append(Error(
                        type=ErrorType.EMPTY_RESULT,
                        location=ErrorLocation(clause="EXECUTION"),
                        detail="SQL 执行返回空结果",
                    ))
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
    # LLM 语义审查（论文 L270 "semantic side"）
    # ============================================================

    def _llm_semantic_review(self, triple: Triple) -> list[Error]:
        """LLM 对照 q 意图 + K2 域规则审查 r，捕捉结构检查抓不到的问题"""
        try:
            prompt = self._render_prompt(
                "diagnosis/semantic_review.j2",
                question=triple.question.text,
                sql=triple.sql_result.sql,
                rationale=triple.rationale.focus,
                domain_rules=(
                    self.kbase.get_domain().description if self.kbase else ""
                ),
            )
            result = self._llm_generate_json(prompt)
        except Exception as e:
            self.logger.warning(f"LLM 语义审查失败 {triple.question_id}: {e}")
            return []

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
            clause = issue.get("clause", "")
            errors.append(Error(
                type=ErrorType.SEMANTIC_INCONSISTENCY,
                location=ErrorLocation(
                    clause=clause,
                    column=issue.get("column"),
                    table=issue.get("table"),
                ),
                detail=detail,
            ))
        return errors
