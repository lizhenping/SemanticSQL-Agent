"""三阶段固定编排流水线（core/pipeline.py）

论文 §III 的固定编排：Phase 1 Analysis (DA) → Phase 2 Generation (DS)
→ Phase 3 Diagnosis (DT, Eq.4 循环)。

这是 cli.py 唯一调用的入口，取代原 ReAct agent 的自由决策。
依赖全部注入（可测试性），工具按 K1→K2→...→K6 固定顺序执行。

依赖方向：core → tools/infra/models，不依赖 cli。

进度（对照 REFACTOR_PLAN）：
- Phase 1 Analysis：✅ 已实现（K1~K6 全套 tools/analysis/）
- Phase 2 Generation：⚠️ stub（S5 迁移 tools/synthesis 后填充）
- Phase 3 Diagnosis：⚠️ stub（S6 迁移 tools/diagnosis 后填充）
"""

import logging
from pathlib import Path
from typing import Optional

from config.settings import Settings

from core.knowledge_store import KnowledgeBase
from infra.database import DatabaseManager
from infra.llm import LLMClient, create_llm_client
from infra.storage import JSONLKnowledgeStore
from prompts.template_manager import PromptManager

# Phase 1 工具（已迁移完成）
from tools.analysis import (
    SchemaExtractionTool,
    DomainAnalysisTool,
    FieldAnalysisTool,
    ColumnAnalysisTool,
    TableAnalysisTool,
    ERAnalysisTool,
)
# Phase 2 工具（S5 迁移完成）
from tools.synthesis import QuestionSynthTool, SQLSynthTool
# Phase 3 工具（S6 迁移完成）
from tools.diagnosis import DiagnoseTool, CorrectTool


class PipelineExecutor:
    """三阶段固定编排器（论文 §III）

    用法（典型，由 cli.py 构造）：
        pipeline = PipelineExecutor.from_settings(settings, history_dir)
        kbase = pipeline.run_analysis(benchmark="spider", database="concert_singer")
        triples = pipeline.run_generation(count=100)   # S5 后可用
        pipeline.run_diagnosis(triples)                # S6 后可用

    也可直接构造（单测/脚本）：
        pipeline = PipelineExecutor(
            db=DatabaseManager.for_sqlite(path),
            llm=create_llm_client(),
            kbase=KnowledgeBase("concert_singer", store),
            prompt_manager=PromptManager(),
        )
    """

    def __init__(
        self,
        db: DatabaseManager,
        llm: LLMClient,
        kbase: KnowledgeBase,
        prompt_manager: PromptManager,
    ):
        self.db = db
        self.llm = llm
        self.kbase = kbase
        self.prompt_manager = prompt_manager
        self.logger = logging.getLogger(self.__class__.__name__)

    # ============================================================
    # 工厂
    # ============================================================

    @classmethod
    def from_settings(
        cls,
        settings: Optional[Settings] = None,
        history_dir: Optional[str] = None,
    ) -> "PipelineExecutor":
        """从 Settings 构造完整 pipeline（cli.py 用）

        Args:
            settings: 配置；None 则用默认 Settings()
            history_dir: K 的 JSONL 落盘目录；None 则用 ./history
        """
        if settings is None:
            settings = Settings()

        db = DatabaseManager.from_settings(settings)
        llm = create_llm_client(settings)

        if history_dir is None:
            history_dir = str(Path("history") / settings.db_database)
        store = JSONLKnowledgeStore(history_dir)
        kbase = KnowledgeBase(settings.db_database, store)
        prompt_manager = PromptManager()

        return cls(db=db, llm=llm, kbase=kbase, prompt_manager=prompt_manager)

    @classmethod
    def for_sqlite(
        cls,
        sqlite_path: str,
        database_name: Optional[str] = None,
        benchmark: Optional[str] = None,
        llm: Optional[LLMClient] = None,
        history_dir: Optional[str] = None,
        prompt_manager: Optional[PromptManager] = None,
    ) -> "PipelineExecutor":
        """直连 SQLite 文件构造 pipeline（论文数据集全部 sqlite）

        Args:
            sqlite_path: .sqlite 文件路径
            database_name: K1 里的数据库名；None 则取文件 stem
            benchmark: benchmark 名（spider/bird/...）；用于分层存储产物
            llm: LLM 客户端；None 则从 Settings 创建（生产用）
            history_dir: JSONL 目录；None 则自动按 benchmark/database 分层
                         （history/<benchmark>/<database>）
        """
        name = database_name or Path(sqlite_path).stem

        # 先建轻量依赖（LLM/prompt），失败快速暴露；DB 连接较重放后面
        if llm is None:
            llm = create_llm_client()
        if prompt_manager is None:
            prompt_manager = PromptManager()

        db = DatabaseManager.for_sqlite(sqlite_path)
        db.initialize()

        if history_dir is None:
            # 按 benchmark/database 分层存储，避免不同 benchmark 同名库冲突
            if benchmark:
                history_dir = str(Path("history") / benchmark / name)
            else:
                history_dir = str(Path("history") / name)
        store = JSONLKnowledgeStore(history_dir)
        kbase = KnowledgeBase(name, store)
        return cls(db=db, llm=llm, kbase=kbase, prompt_manager=prompt_manager)

    # ============================================================
    # Phase 1: Analysis (DA) — 论文 §III.C，K1..K6
    # ============================================================

    def run_analysis(self) -> KnowledgeBase:
        """执行 Phase 1：K1→K2→K3→K4→K5→K6 固定顺序

        每个工具从 kbase 读取上游 K，分析后写回 kbase。
        返回填满 K1..K6 的 KnowledgeBase。
        """
        self.logger.info("▶ Phase 1 Analysis 开始（K1..K6）")

        # K1: Schema Extraction（需要 db 连接）
        SchemaExtractionTool(
            db=self.db, kbase=self.kbase
        ).run(database_name=self.kbase.database_name)

        # K2: Domain Analysis（依赖 K1 schema + LLM）
        DomainAnalysisTool(
            llm=self.llm, kbase=self.kbase, prompt_manager=self.prompt_manager
        ).run()

        # K3: Field Analysis（依赖 K1）
        FieldAnalysisTool(
            llm=self.llm, kbase=self.kbase, prompt_manager=self.prompt_manager
        ).run()

        # K4: Column Analysis（依赖 K1 + K3）
        ColumnAnalysisTool(
            llm=self.llm, kbase=self.kbase, prompt_manager=self.prompt_manager
        ).run()

        # K5: Table Analysis（依赖 K1 + K3 + K4）
        TableAnalysisTool(
            llm=self.llm, kbase=self.kbase, prompt_manager=self.prompt_manager
        ).run()

        # K6: ER Analysis（依赖 K1~K5）
        ERAnalysisTool(
            llm=self.llm, kbase=self.kbase, prompt_manager=self.prompt_manager
        ).run()

        self.logger.info(f"✅ Phase 1 完成：{self.kbase.summary()}")
        return self.kbase

    # ============================================================
    # Phase 2: Generation (DS) — 论文 §III.D
    # ============================================================

    def run_generation(self, count: int = 10, execute: bool = True) -> list:
        """执行 Phase 2：合成 (q, s, r) 三元组

        流程：QuestionSynthTool 合成 count 个 q → 每个 q 经 SQLSynthTool
        生成 (s, r) → 组装成 list[Triple]。

        ⚠️ 不含 Phase 3 反思（Diagnose→Correct 由 run_diagnosis 编排）。

        Args:
            count: 合成样本数
            execute: 是否执行 SQL 验证（默认 True，失败不抛错，记入 SQLResult）

        Returns:
            list[Triple]（论文核心产物）
        """
        self.logger.info(f"▶ Phase 2 Generation 开始（目标 {count} 条）")

        # q：场景驱动的问题合成
        q_tool = QuestionSynthTool(
            llm=self.llm, kbase=self.kbase, prompt_manager=self.prompt_manager
        )
        questions = q_tool.run(count=count)
        self.logger.info(f"  合成 {len(questions)} 个问题，开始生成 SQL")

        # (s, r)：逐问题生成 SQL + 推理链
        s_tool = SQLSynthTool(
            llm=self.llm, db=self.db, kbase=self.kbase,
            prompt_manager=self.prompt_manager,
        )
        triples = []
        for i, q in enumerate(questions, 1):
            try:
                triple = s_tool.run(q, execute=execute)
                triples.append(triple)
                self.logger.info(
                    f"  [{i}/{len(questions)}] {q.question_id}: "
                    f"{'✅' if triple.sql_result.execution_success else '⚠️'}"
                )
            except Exception as e:
                self.logger.warning(f"  [{i}/{len(questions)}] {q.question_id} 生成失败: {e}")

        # 落盘到 questions/sql 两层（与 storage LAYER_FILES 对齐，供 Phase 3 读取）
        if self.kbase and triples:
            self._persist_phase2(triples)

        self.logger.info(f"✅ Phase 2 完成：{len(triples)}/{len(questions)} 条三元组")
        return triples

    def _persist_phase2(self, triples: list) -> None:
        """把 Phase 2 产物落到 questions/sql 两层 JSONL（供 Phase 3 与导出用）"""
        from models.synthesis import Triple
        q_records = []
        s_records = []
        for t in triples:
            if not isinstance(t, Triple):
                continue
            q_records.append({
                "question_id": t.question_id,
                "question_text": t.question.text,
                "question_focus": t.question.question_focus,
                "business_rules": t.question.business_rules,
            })
            s_records.append({
                "question_id": t.question_id,
                "sql": t.sql_result.sql,
                "dialect": t.sql_result.dialect,
                "executed": t.sql_result.executed,
                "execution_success": t.sql_result.execution_success,
                "result_count": t.sql_result.result_count,
                "execution_error": t.sql_result.execution_error,
            })
        self.kbase.store.save("questions", q_records)
        self.kbase.store.save("sql", s_records)

    # ============================================================
    # Phase 3: Diagnosis (DT) — 论文 §III.E, Eq.4 循环
    # ============================================================

    def run_diagnosis(self, triples: list, max_iters: int = 3) -> list:
        """执行 Phase 3：对每个 triple 跑 Diagnose→Retrieve→Correct 循环（Eq.4）

        论文 §III.E Eq.4:
            E⁽ᵏ⁾     = Diagnose(q⁽ᵏ⁾, s⁽ᵏ⁾, r⁽ᵏ⁾, K, I)
            Φ⁽ᵏ⁾     = Retrieve(E⁽ᵏ⁾, K)
            (q⁽ᵏ⁺¹⁾, s⁽ᵏ⁺¹⁾, r⁽ᵏ⁺¹⁾) = Correct(q⁽ᵏ⁾, s⁽ᵏ⁾, r⁽ᵏ⁾, Φ⁽ᵏ⁾, K)
            重复直到 E 为空或达 max_iters

        Args:
            triples: Phase 2 产出的 list[Triple]
            max_iters: Eq.4 循环最大迭代数（论文 "maximum iteration limit"）

        Returns:
            修正后的 list[Triple]（每个 triple 的 rationale.correction_history
            记录完整精修轨迹）
        """
        self.logger.info(f"▶ Phase 3 Diagnosis 开始（{len(triples)} 条，max_iters={max_iters}）")

        diagnose_tool = DiagnoseTool(
            llm=self.llm, db=self.db, kbase=self.kbase,
            prompt_manager=self.prompt_manager,
        )
        correct_tool = CorrectTool(
            llm=self.llm, db=self.db, kbase=self.kbase,
            prompt_manager=self.prompt_manager,
        )

        refined: list = []
        traces: list = []
        for i, triple in enumerate(triples, 1):
            try:
                result, trace = self._eq4_loop(
                    triple, diagnose_tool, correct_tool, max_iters
                )
                refined.append(result)
                traces.append(trace)
                n_corr = len(result.rationale.correction_history)
                ok = result.sql_result.execution_success
                self.logger.info(
                    f"  [{i}/{len(triples)}] {triple.question_id}: "
                    f"{'✅' if ok else '⚠️'} {n_corr} 轮修正"
                )
            except Exception as e:
                self.logger.warning(
                    f"  [{i}/{len(triples)}] {triple.question_id} 诊断失败: {e}"
                )
                refined.append(triple)  # 失败则保留原样
                traces.append(self._failed_trace(triple, max_iters, str(e)))

        # 落盘修正后的 sql（覆盖 Phase 2 的 sql 层）
        if self.kbase and refined:
            self._persist_phase3(refined, traces)

        ok_count = sum(1 for t in refined if t.sql_result.execution_success)
        self.logger.info(
            f"✅ Phase 3 完成：{ok_count}/{len(refined)} 条 SQL 执行通过"
        )
        return refined

    def _eq4_loop(
        self, triple, diagnose_tool: DiagnoseTool,
        correct_tool: CorrectTool, max_iters: int,
    ) -> tuple:
        """单个 triple 的 Eq.4 循环：Diagnose→Retrieve→Correct 直到收敛"""
        from models.diagnosis import DiagnosisIteration, DiagnosisTrace, SampleDecision
        current = triple
        trace = DiagnosisTrace(
            question_id=triple.question_id,
            original_question=triple.question.text,
            original_sql=triple.sql_result.sql,
            max_correction_iterations=max_iters,
        )
        terminal_errors = []
        for k in range(1, max_iters + 1):
            # E = Diagnose(...)
            errors = diagnose_tool.run(current)
            if not errors:
                # 收敛：无错误，停止迭代（论文 "until no errors are detected"）
                terminal_errors = []
                trace.iterations.append(DiagnosisIteration(
                    iteration=k,
                    question=current.question.text,
                    sql_before=current.sql_result.sql,
                    rationale_focus=current.rationale.focus,
                    errors=[],
                    execution_success_after=current.sql_result.execution_success,
                    execution_error_after=current.sql_result.execution_error,
                    result_count_after=current.sql_result.result_count,
                    action="verified",
                ))
                break
            # Φ = Retrieve(E, K)
            evidence = self.kbase.retrieve_evidence(errors)
            # (q', s', r') = Correct(...)
            before = current
            current = correct_tool.run(current, errors, evidence, iteration=k)
            trace.iterations.append(DiagnosisIteration(
                iteration=k,
                question=before.question.text,
                sql_before=before.sql_result.sql,
                rationale_focus=before.rationale.focus,
                errors=errors,
                evidence=evidence,
                sql_after=current.sql_result.sql,
                execution_success_after=current.sql_result.execution_success,
                execution_error_after=current.sql_result.execution_error,
                result_count_after=current.sql_result.result_count,
                action="corrected",
            ))
            terminal_errors = errors
        else:
            # 修正次数耗尽后必须再检查最终 SQL，不能把“已修正”误写成“已通过”。
            terminal_errors = diagnose_tool.run(current)
            trace.iterations.append(DiagnosisIteration(
                iteration=max_iters + 1,
                question=current.question.text,
                sql_before=current.sql_result.sql,
                rationale_focus=current.rationale.focus,
                errors=terminal_errors,
                execution_success_after=current.sql_result.execution_success,
                execution_error_after=current.sql_result.execution_error,
                result_count_after=current.sql_result.result_count,
                action="max_iterations_reached",
            ))

        trace.final_question = current.question.text
        trace.final_sql = current.sql_result.sql
        trace.final_execution_success = current.sql_result.execution_success
        trace.final_execution_error = current.sql_result.execution_error
        trace.final_result_count = current.sql_result.result_count
        if current.sql_result.execution_success is not True:
            trace.decision = SampleDecision.REJECTED
            trace.decision_reason = "final_sql_not_executable"
        elif terminal_errors:
            trace.decision = SampleDecision.UNRESOLVED
            trace.decision_reason = "diagnosis_errors_remain_after_limit"
        else:
            trace.decision = SampleDecision.ACCEPTED
            trace.decision_reason = "executable_and_no_detected_errors"
        current.rationale.admission_decision = trace.decision.value
        current.rationale.admission_reason = trace.decision_reason
        return current, trace

    def _failed_trace(self, triple, max_iters: int, detail: str):
        """将编排异常也写成可审计的拒绝记录，避免静默丢失候选样本。"""
        from models.diagnosis import DiagnosisTrace, SampleDecision
        triple.rationale.admission_decision = SampleDecision.REJECTED.value
        triple.rationale.admission_reason = "diagnosis_pipeline_exception"
        return DiagnosisTrace(
            question_id=triple.question_id,
            original_question=triple.question.text,
            original_sql=triple.sql_result.sql,
            max_correction_iterations=max_iters,
            final_question=triple.question.text,
            final_sql=triple.sql_result.sql,
            final_execution_success=triple.sql_result.execution_success,
            final_execution_error=triple.sql_result.execution_error,
            decision=SampleDecision.REJECTED,
            decision_reason=f"diagnosis_pipeline_exception: {detail}",
        )

    def _persist_phase3(self, triples: list, traces: list) -> None:
        """持久化最终 SQL、逐轮诊断轨迹和训练语料准入裁决。"""
        from models.synthesis import Triple
        s_records = []
        for t in triples:
            if not isinstance(t, Triple):
                continue
            s_records.append({
                "question_id": t.question_id,
                "sql": t.sql_result.sql,
                "dialect": t.sql_result.dialect,
                "executed": t.sql_result.executed,
                "execution_success": t.sql_result.execution_success,
                "result_count": t.sql_result.result_count,
                "execution_error": t.sql_result.execution_error,
                "corrected_by_reflection": t.sql_result.corrected_by_reflection,
                "correction_rounds": len(t.rationale.correction_history),
            })
        self.kbase.store.save("sql", s_records)
        self.kbase.store.save(
            "diagnosis_trace", [trace.model_dump(mode="json") for trace in traces]
        )
        self.kbase.store.save("corpus_manifest", [
            {
                "question_id": trace.question_id,
                "decision": trace.decision.value,
                "decision_reason": trace.decision_reason,
                "final_execution_success": trace.final_execution_success,
                "diagnosis_iterations": len(trace.iterations),
            }
            for trace in traces
        ])

    # ============================================================
    # 全流程（三阶段串联）
    # ============================================================

    def run(self, count: int = 10, execute: bool = True, max_iters: int = 3) -> list:
        """跑完整三阶段：Analysis → Generation → Diagnosis

        Phase 1/2/3 全部可用。返回修正后的 list[Triple]。
        """
        self.run_analysis()
        triples = self.run_generation(count=count, execute=execute)
        triples = self.run_diagnosis(triples, max_iters=max_iters)
        return triples
