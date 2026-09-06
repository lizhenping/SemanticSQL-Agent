"""SemanticSQL Agent CLI（cli.py）

命令行接口，固定三阶段流水线（论文 §III）的薄入口。
不再走 ReAct agent 自由决策，直接编排 core.PipelineExecutor。

命令 ↔ 论文阶段：
  analyze        ↔  Phase 1 Analysis  (DA, K1..K6)        ✅
  generate       ↔  Phase 2 Generation (DS, q/s/r 三元组)  ✅
  diagnose       ↔  Phase 3 Diagnosis (DT, Eq.4 循环)     ✅
  run            ↔  单库三阶段串联                        ✅
  run-benchmark  ↔  一键跑整个 benchmark（自动跳过 test）  ✅
  list-dbs       ↔  查看某 benchmark 可用 train 库         ✅

数据库定位（与 datasets/README.md 一致）：
  {DB_ROOT}/{benchmark}/databases/{database}/{database}.sqlite
DB_ROOT 默认 datasets/（容器内由 docker-compose 设为 /data），可用 --db-root 覆盖。
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import click

from core.pipeline import PipelineExecutor


# ----------------------------------------------------------------
# 日志
# ----------------------------------------------------------------
def _setup_logging(debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO
    handlers = [logging.StreamHandler()]
    log_file = os.getenv("LOG_FILE")
    if log_file:
        from logging.handlers import RotatingFileHandler
        handlers.append(RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024,
            backupCount=5, encoding="utf-8",
        ))
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )


# ----------------------------------------------------------------
# 数据库路径解析
# ----------------------------------------------------------------
def _resolve_sqlite_path(
    benchmark: Optional[str],
    database: Optional[str],
    sqlite: Optional[str],
    db_root: str,
    allow_eval: bool = False,
) -> str:
    """把 (benchmark, database) 或 --sqlite 解析成 sqlite 文件路径。

    规则（见 数据集/README.md）：
        {db_root}/{benchmark}/databases/{database}/{database}.sqlite

    数据泄露防护：默认拒绝评估（dev/test）库。若 benchmark+database 命中
    评估库黑名单，直接报错；传 allow_eval=True 可绕过（仅限调试，禁用于合成）。
    """
    if sqlite:
        if not Path(sqlite).exists():
            raise click.ClickException(f"sqlite 文件不存在: {sqlite}")
        return sqlite

    if not (benchmark and database):
        raise click.ClickException(
            "需要 --benchmark + --database，或直接 --sqlite 指定数据库文件"
        )

    # ⭐ 数据隔离：拒绝评估库用于合成（防 leakage）
    if not allow_eval:
        from infra.dataset_split import assert_train_only, DatasetSplitError
        try:
            assert_train_only(benchmark, database)
        except DatasetSplitError as e:
            raise click.ClickException(str(e))

    path = Path(db_root) / benchmark / "databases" / database / f"{database}.sqlite"
    if not path.exists():
        raise click.ClickException(
            f"数据库文件不存在: {path}\n"
            f"检查 --db-root（当前: {db_root}）/ --benchmark / --database 是否正确"
        )
    return str(path)


# ----------------------------------------------------------------
# CLI 主组
# ----------------------------------------------------------------
@click.group()
@click.version_option(version="0.4.0")
def cli():
    """SemanticSQL Agent — 知识引导的 Text-to-SQL 合成框架

    固定三阶段流水线（论文 §III）：
      Phase 1 Analysis → Phase 2 Generation → Phase 3 Diagnosis
    """
    pass


@cli.command("list-dbs")
@click.option("--benchmark", "-b", required=True, help="benchmark 名")
@click.option("--db-root", default=os.getenv("SEMANTICSQL_DB_ROOT", "datasets"),
              help="数据库根目录")
def list_dbs(benchmark, db_root):
    """列出某 benchmark 可用于合成的 train 库（排除 dev/test，防数据泄露）

    \b
    示例：
      python cli.py list-dbs -b spider
      python cli.py list-dbs -b bird
    """
    from infra.dataset_split import list_train_databases, EVAL_DBS
    train_dbs = list_train_databases(benchmark, db_root)
    eval_dbs = sorted(EVAL_DBS.get(benchmark, set()))
    click.echo(f"📊 {benchmark} 可合成库（train，{len(train_dbs)} 个）：")
    for db in train_dbs:
        click.echo(f"  ✅ {db}")
    if eval_dbs:
        click.echo(f"\n🚫 评估库（dev/test，禁止合成，{len(eval_dbs)} 个）：")
        for db in eval_dbs:
            click.echo(f"  ⛔ {db}")


# ----------------------------------------------------------------
# 审计：audit-summary
# ----------------------------------------------------------------
@cli.command("audit-summary")
@click.option("--history-dir", required=True,
              help="包含 diagnosis_trace.jsonl 的单库产物目录")
def audit_summary(history_dir):
    """汇总 Phase 3 的准入裁决、错误分类和修正结果（不调用模型）。"""
    trace_path = Path(history_dir) / "diagnosis_trace.jsonl"
    if not trace_path.exists():
        raise click.ClickException(f"未找到诊断轨迹: {trace_path}")

    traces = []
    with open(trace_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                traces.append(json.loads(line))
    if not traces:
        click.echo("没有可汇总的诊断记录")
        return

    from collections import Counter
    decisions = Counter(t.get("decision", "unresolved") for t in traces)
    error_types = Counter()
    categories = Counter()
    detectors = Counter()
    semantic_classes = Counter()
    corrected = 0
    for trace in traces:
        iterations = trace.get("iterations", [])
        if any(item.get("action") == "corrected" for item in iterations):
            corrected += 1
        for item in iterations:
            for error in item.get("errors", []):
                error_types[error.get("type", "unknown")] += 1
                categories[error.get("category", "unknown")] += 1
                detectors[error.get("detector", "unknown")] += 1
                if error.get("semantic_class"):
                    semantic_classes[error["semantic_class"]] += 1

    total = len(traces)
    click.echo(f"样本数: {total}")
    click.echo(
        "准入裁决: " + ", ".join(
            f"{name}={decisions[name]} ({decisions[name] / total:.1%})"
            for name in ("accepted", "rejected", "unresolved")
        )
    )
    click.echo(f"曾进入修正: {corrected} ({corrected / total:.1%})")
    if semantic_classes:
        # 论文 Table semantic-taxonomy 的七类语义错误频次
        order = ["I-1", "I-2", "I-3", "I-4", "II-1", "II-2", "III-1"]
        click.echo("七类语义错误（论文 Table taxonomy）: " + ", ".join(
            f"{name}={semantic_classes[name]}" for name in order if semantic_classes[name]
        ))
    if categories:
        click.echo("错误边界: " + ", ".join(
            f"{name}={count}" for name, count in sorted(categories.items())
        ))
    if detectors:
        click.echo("检测来源: " + ", ".join(
            f"{name}={count}" for name, count in sorted(detectors.items())
        ))
    if error_types:
        click.echo("错误类型:")
        for name, count in error_types.most_common():
            click.echo(f"  {name}: {count}")


# ----------------------------------------------------------------
# Phase 1: analyze
# ----------------------------------------------------------------
@cli.command()
@click.option("--benchmark", "-b", help="benchmark 名（spider/bird/spider2/ehrsql/science_benchmark）")
@click.option("--database", "-d", help="数据库名（sqlite 文件的 stem）")
@click.option("--sqlite", help="直接指定 .sqlite 文件路径（覆盖 benchmark+database）")
@click.option("--db-root", default=os.getenv("SEMANTICSQL_DB_ROOT", "数据集"),
              help="数据库根目录（默认: 数据集 或 $SEMANTICSQL_DB_ROOT）")
@click.option("--history-dir", help="K 的 JSONL 落盘目录（默认: history/<database>）")
@click.option("--summary", "-s", is_flag=True, help="额外打印 K1..K6 摘要")
@click.option("--debug", is_flag=True, help="启用 DEBUG 日志")
def analyze(benchmark, database, sqlite, db_root, history_dir, summary, debug):
    """Phase 1 Analysis：抽取 K1..K6 知识库（论文 §III.C）

    \b
    示例：
      python cli.py analyze -b spider -d concert_singer
      python cli.py analyze --sqlite 数据集/bird/databases/financial/financial.sqlite
    """
    _setup_logging(debug)

    sqlite_path = _resolve_sqlite_path(benchmark, database, sqlite, db_root)
    db_name = Path(sqlite_path).stem
    click.echo(f"📊 Phase 1 Analysis: {sqlite_path}")

    pipeline = PipelineExecutor.for_sqlite(
        sqlite_path=sqlite_path,
        database_name=db_name,
        benchmark=benchmark,
        history_dir=history_dir,
    )
    kbase = pipeline.run_analysis()

    _layer = f"{benchmark}/{db_name}" if benchmark else db_name
    click.echo(f"✅ Phase 1 完成，知识库 K1..K6 已写入: history/{_layer}")
    if summary:
        for k, v in kbase.summary().items():
            click.echo(f"   {k}: {v}")


# ----------------------------------------------------------------
# Phase 2: generate
# ----------------------------------------------------------------
@cli.command()
@click.option("--benchmark", "-b", help="benchmark 名")
@click.option("--database", "-d", help="数据库名")
@click.option("--sqlite", help="直接指定 .sqlite 文件路径")
@click.option("--db-root", default=os.getenv("SEMANTICSQL_DB_ROOT", "datasets"),
              help="数据库根目录")
@click.option("--count", "-n", default=10, type=int, help="合成样本数")
@click.option("--output", "-o", help="输出 JSONL 路径（默认: history/<db>/training_data.jsonl）")
@click.option("--reuse-knowledge", is_flag=True,
              help="复用已有 K1..K6（跳过 Phase 1，要求 history 目录已有知识库）")
@click.option("--debug", is_flag=True, help="启用 DEBUG 日志")
def generate(benchmark, database, sqlite, db_root, count, output, reuse_knowledge, debug):
    """Phase 2 Generation：合成 (q, s, r) 训练三元组（论文 §III.D）

    \b
    示例：
      python cli.py generate -b spider -d concert_singer -n 50
      python cli.py generate --reuse-knowledge -d concert_singer -n 50  # 跳过 Phase 1
    """
    _setup_logging(debug)

    sqlite_path = _resolve_sqlite_path(benchmark, database, sqlite, db_root)
    db_name = Path(sqlite_path).stem

    pipeline = PipelineExecutor.for_sqlite(
        sqlite_path=sqlite_path, database_name=db_name, benchmark=benchmark,
    )

    # Phase 1：抽取知识库（除非 --reuse-knowledge 且已有）
    if reuse_knowledge:
        click.echo(f"♻️  复用已有 K1..K6（跳过 Phase 1）")
    else:
        click.echo("▶ Phase 1 Analysis ...")
        pipeline.run_analysis()

    # Phase 2：合成三元组
    click.echo(f"▶ Phase 2 Generation（n={count}）...")
    triples = pipeline.run_generation(count=count)

    # 导出训练数据 JSONL（论文 Fig.training_data_format）
    _layer = f"{benchmark}/{db_name}" if benchmark else db_name
    out_path = output or f"history/{_layer}/training_data.jsonl"
    _save_triples(triples, out_path)

    ok = sum(1 for t in triples if t.sql_result.execution_success)
    click.echo(
        f"✅ 完成：{len(triples)} 条三元组（{ok} 条 SQL 执行通过）→ {out_path}"
    )


# ----------------------------------------------------------------
# Phase 3: diagnose
# ----------------------------------------------------------------
@cli.command()
@click.option("--input", "-i", required=True, help="待诊断的训练数据 JSONL（Phase 2 产物）")
@click.option("--benchmark", "-b", help="benchmark 名")
@click.option("--database", "-d", help="数据库名")
@click.option("--sqlite", help="直接指定 .sqlite 文件路径")
@click.option("--db-root", default=os.getenv("SEMANTICSQL_DB_ROOT", "datasets"),
              help="数据库根目录")
@click.option("--output", "-o", help="修正后输出路径（默认: <input>.corrected.jsonl）")
@click.option("--max-iters", default=3, type=int, help="Eq.4 修正循环最大迭代")
@click.option("--debug", is_flag=True, help="启用 DEBUG 日志")
def diagnose(input, benchmark, database, sqlite, db_root, output, max_iters, debug):
    """Phase 3 Diagnosis：Diagnose→Retrieve→Correct 循环（论文 §III.E, Eq.4）

    复用已有 K1..K6 知识库 + 已有 Phase 2 三元组，只跑 Phase 3 修正。

    \b
    示例：
      # 先跑过 generate 产出 training_data.jsonl，再诊断
      python cli.py diagnose -d concert_singer -i history/concert_singer/training_data.jsonl
    """
    _setup_logging(debug)

    sqlite_path = _resolve_sqlite_path(benchmark, database, sqlite, db_root)
    db_name = Path(sqlite_path).stem

    pipeline = PipelineExecutor.for_sqlite(
        sqlite_path=sqlite_path, database_name=db_name, benchmark=benchmark,
    )

    # 加载 Phase 2 产出的 triples
    from models.synthesis import Triple, Question, SQLResult, Rationale
    triples = _load_triples(input)
    if not triples:
        click.echo(f"❌ 未从 {input} 加载到任何样本，请先运行 generate")
        sys.exit(1)
    click.echo(f"📖 加载 {len(triples)} 条待诊断样本")

    # Phase 3：Eq.4 循环
    click.echo(f"▶ Phase 3 Diagnosis（max_iters={max_iters}）...")
    refined = pipeline.run_diagnosis(triples, max_iters=max_iters)

    out_path = output or (str(Path(input).with_suffix("")) + ".corrected.jsonl")
    _save_triples(refined, out_path, accepted_only=True)

    ok = sum(1 for t in refined if t.sql_result.execution_success)
    accepted = sum(1 for t in refined if t.rationale.admission_decision == "accepted")
    corrected = sum(1 for t in refined if t.rationale.correction_history)
    click.echo(
        f"✅ 完成：{accepted}/{len(refined)} 条通过训练准入（{ok} 条 SQL 执行通过），"
        f"{corrected} 条经修正 → {out_path}"
    )


# ----------------------------------------------------------------
# 全流程: run
# ----------------------------------------------------------------
@cli.command()
@click.option("--benchmark", "-b", help="benchmark 名")
@click.option("--database", "-d", help="数据库名")
@click.option("--sqlite", help="直接指定 .sqlite 文件路径")
@click.option("--db-root", default=os.getenv("SEMANTICSQL_DB_ROOT", "datasets"),
              help="数据库根目录")
@click.option("--count", "-n", default=10, type=int, help="合成样本数")
@click.option("--max-iters", default=3, type=int, help="Phase 3 Eq.4 修正循环最大迭代")
@click.option("--output", "-o", help="最终训练数据 JSONL 路径")
@click.option("--debug", is_flag=True, help="启用 DEBUG 日志")
def run(benchmark, database, sqlite, db_root, count, max_iters, output, debug):
    """三阶段全流程：Analysis → Generation → Diagnosis

    \b
    示例：
      python cli.py run -b spider -d concert_singer -n 100
    """
    _setup_logging(debug)

    sqlite_path = _resolve_sqlite_path(benchmark, database, sqlite, db_root)
    db_name = Path(sqlite_path).stem
    click.echo(f"▶ run: {sqlite_path}")

    pipeline = PipelineExecutor.for_sqlite(
        sqlite_path=sqlite_path, database_name=db_name, benchmark=benchmark,
    )

    click.echo("▶ Phase 1 Analysis ...")
    pipeline.run_analysis()
    click.echo("✅ Phase 1 完成")

    click.echo(f"▶ Phase 2 Generation（n={count}）...")
    triples = pipeline.run_generation(count=count)
    click.echo(f"✅ Phase 2 完成（{len(triples)} 条）")

    click.echo(f"▶ Phase 3 Diagnosis（max_iters={max_iters}）...")
    triples = pipeline.run_diagnosis(triples, max_iters=max_iters)

    _layer = f"{benchmark}/{db_name}" if benchmark else db_name
    out_path = output or f"history/{_layer}/training_data.jsonl"
    _save_triples(triples, out_path, accepted_only=True)
    ok = sum(1 for t in triples if t.sql_result.execution_success)
    accepted = sum(1 for t in triples if t.rationale.admission_decision == "accepted")
    click.echo(f"✅ 完成：{accepted}/{len(triples)} 条通过训练准入（{ok} 条执行通过）→ {out_path}")


# ----------------------------------------------------------------
# 批量：run-benchmark（一键跑整个 benchmark 的所有 train 库）
# ----------------------------------------------------------------
def _split_total(total: int, n_dbs: int) -> list[int]:
    """把论文设定的 benchmark 总量平均分配到每个数据库。

    均分规则：count_i = total // n_dbs，前 (total % n_dbs) 个库各 +1，
    保证 Σcount_i == total（如 spider2 20000/30 → 20 库 667 + 10 库 666）。
    """
    if n_dbs <= 0:
        return []
    base, extra = divmod(total, n_dbs)
    return [base + (1 if i < extra else 0) for i in range(n_dbs)]


# K1..K6 六层知识库对应的 LAYER_FILES key（复用判断用）
_KB_LAYER_KEYS = ["schema", "domain", "field", "column", "table", "er"]


def _kb_complete(output_root: str, benchmark: str, db_name: str) -> bool:
    """该库的 K1..K6 知识库是否已完整落盘（六层 JSONL 均存在且非空）"""
    from infra.storage import JSONLKnowledgeStore
    d = Path(output_root) / benchmark / db_name
    return all(
        (d / JSONLKnowledgeStore.LAYER_FILES[k]).exists()
        and (d / JSONLKnowledgeStore.LAYER_FILES[k]).stat().st_size > 0
        for k in _KB_LAYER_KEYS
    )


def _count_records(path: Path) -> int:
    """统计 training_data.jsonl 已落盘的样本条数（文件不存在返回 0）"""
    if not path.exists():
        return 0
    return sum(1 for line in open(path, encoding="utf-8") if line.strip())


@cli.command("run-benchmark")
@click.option("--benchmark", "-b", required=True, help="benchmark 名（spider/bird/spider2/ehrsql/science_benchmark）")
@click.option("--count", "-n", default=None, type=int, help="每个库合成样本数（与 --total 二选一）")
@click.option("--total", "-t", default=None, type=int,
              help="benchmark 合成总量（论文 Table synth_source_stats），均分到每个 train 库")
@click.option("--max-iters", default=3, type=int, help="Phase 3 Eq.4 修正循环最大迭代")
@click.option("--db-root", default=os.getenv("SEMANTICSQL_DB_ROOT", "datasets"),
              help="数据库根目录")
@click.option("--output-root", default=os.getenv("SEMANTICSQL_OUTPUT_ROOT", "history"),
              help="产物根目录（默认 history；批量实验用 data，按 benchmark/database 分层）")
@click.option("--batch-size", default=25, type=int,
              help="每批次合成+落盘的样本数（分批落盘，中断最多损失一个批次）")
@click.option("--shard", type=int, help="分片编号（0 起），与 --num-shards 配合把库列表错开并行")
@click.option("--num-shards", type=int, help="总分片数；>1 时本 worker 只跑 train_dbs[shard::num_shards]")
@click.option("--limit", type=int, help="只跑前 N 个库（调试用，不传则跑全部）")
@click.option("--debug", is_flag=True, help="启用 DEBUG 日志")
def run_benchmark(benchmark, count, total, max_iters, db_root, output_root, batch_size, shard, num_shards, limit, debug):
    """一键跑整个 benchmark：自动遍历所有 train 库，跳过 dev/test（防泄露）

    自动完成：扫描 {db_root}/{benchmark}/databases/ → 排除评估库 →
    逐库执行三阶段（Analysis→Generation→Diagnosis）→ 产物存到
    {output_root}/{benchmark}/{database}/。

    数据量两种指定方式（二选一，都不传则每库 10 条）：
      --total 30000   # 论文总量，均分到每个库（如 BIRD 95 库 → 315/316 条/库）
      --count 100     # 每库固定条数

    \b
    示例：
      # bird 全部 train 库，按论文总量 30000 均分
      python cli.py run-benchmark -b bird --total 30000

      # 调试：只跑前 2 个库
      python cli.py run-benchmark -b spider --total 40000 --limit 2
    """
    _setup_logging(debug)
    from infra.dataset_split import list_train_databases

    train_dbs = list_train_databases(benchmark, db_root)
    if not train_dbs:
        click.echo(f"❌ {benchmark} 没有可用的 train 库（检查 datasets/{benchmark}/databases/ 是否存在）")
        sys.exit(1)

    if limit:
        train_dbs = train_dbs[:limit]

    # 每库数量：--total 均分优先，其次 --count 固定
    if total is not None:
        per_db_counts = _split_total(total, len(train_dbs))
        click.echo(f"🚀 run-benchmark: {benchmark}，{len(train_dbs)} 个 train 库，"
                   f"总量 {total} 均分（{per_db_counts[0]}~{per_db_counts[-1]} 条/库）")
    else:
        per_db_counts = [count if count is not None else 10] * len(train_dbs)
        click.echo(f"🚀 run-benchmark: {benchmark}，{len(train_dbs)} 个 train 库，每库 {per_db_counts[0]} 条")

    # 分片：库列表按编号错开（shard i 取 i::num_shards），多 worker 并行互不重复；
    # 计数先在全量列表上均分再切片，保证各片合计仍等于总量
    if num_shards is not None and num_shards > 1:
        if shard is None:
            raise click.ClickException("使用 --num-shards 时必须同时指定 --shard")
        if not (0 <= shard < num_shards):
            raise click.ClickException(f"--shard 必须在 [0, {num_shards}) 内")
        train_dbs = train_dbs[shard::num_shards]
        per_db_counts = per_db_counts[shard::num_shards]
        click.echo(f"🧩 分片 {shard}/{num_shards}: 本片 {len(train_dbs)} 个库")
    click.echo(f"📁 产物存到 {output_root}/{benchmark}/<database>/")
    click.echo(f"🛡️  已自动排除 dev/test 评估库（防数据泄露）")
    click.echo(f"🔄 断点续跑：已有产物的库自动跳过，中断后重跑会从未完成的库继续")
    click.echo("")

    total_triples = 0
    total_ok = 0
    failed_dbs = []
    skipped_dbs = []
    for i, (db_name, per_db) in enumerate(zip(train_dbs, per_db_counts), 1):
        # 断点续跑：按已落盘样本条数判断（而非仅看文件存在）
        out_path = Path(output_root) / benchmark / db_name / "training_data.jsonl"
        have = _count_records(out_path)
        if have >= per_db:
            click.echo(f"[{i}/{len(train_dbs)}] {benchmark}/{db_name} ... ⏭️  已有 {have}/{per_db} 条，跳过")
            skipped_dbs.append(db_name)
            continue

        sqlite_path = str(Path(db_root) / benchmark / "databases" / db_name / f"{db_name}.sqlite")
        click.echo(f"[{i}/{len(train_dbs)}] {benchmark}/{db_name}（已有 {have}/{per_db} 条）...")

        # 从零起跑（无已落盘样本）时清空旧的中间层，
        # 保证 questions/sql/diagnosis_trace/corpus_manifest 的追加语义干净
        if have == 0:
            for fname in ("questions.jsonl", "sql_results.jsonl",
                          "diagnosis_trace.jsonl", "corpus_manifest.jsonl"):
                stale = Path(output_root) / benchmark / db_name / fname
                if stale.exists():
                    stale.unlink()

        try:
            pipeline = PipelineExecutor.for_sqlite(
                sqlite_path=sqlite_path,
                database_name=db_name,
                benchmark=benchmark,
                history_dir=str(Path(output_root) / benchmark / db_name),
            )
            # 复用已有知识：K1..K6 六层完整落盘的库跳过 Phase 1（省大量重复分析）
            if _kb_complete(output_root, benchmark, db_name):
                click.echo(f"  ♻️  复用已有 K1..K6（跳过 Phase 1）")
            else:
                pipeline.run_analysis()

            # 分批合成 + 即时落盘：中断最多损失一个批次（batch_size 条）
            produced = have
            attempts = 0
            max_attempts = per_db * 3 + batch_size  # 安全阀：准入率极低时避免死循环
            while produced < per_db and attempts < max_attempts:
                n = min(batch_size, per_db - produced)
                triples = pipeline.run_generation(count=n)
                attempts += n
                if not triples:
                    continue
                triples = pipeline.run_diagnosis(triples, max_iters=max_iters)
                _save_triples(triples, str(out_path), accepted_only=True,
                              append=produced > 0)
                produced = _count_records(out_path)
                ok = sum(1 for t in triples if t.sql_result.execution_success)
                total_ok += ok
                click.echo(f"  ✅ 批次完成：累计 {produced}/{per_db}"
                           f"（本批 {len(triples)} 条，{ok} 执行通过）")

            if produced < per_db:
                click.echo(f"  ⚠️  达到尝试上限，仅 {produced}/{per_db} 条（准入率过低），继续下一库")
            total_triples += produced - have
        except Exception as e:
            click.echo(f"  ❌ 失败: {e}")
            failed_dbs.append(db_name)

    click.echo("")
    click.echo(f"📊 汇总：{len(train_dbs)} 库"
               f"（新跑 {len(train_dbs) - len(skipped_dbs) - len(failed_dbs)},"
               f" 跳过 {len(skipped_dbs)}, 失败 {len(failed_dbs)}）"
               f"，共 {total_triples} 条（{total_ok} 执行通过）")
    if failed_dbs:
        click.echo(f"⚠️  失败的库: {', '.join(failed_dbs)}")


# ----------------------------------------------------------------
# 工具：加载/保存训练数据
# ----------------------------------------------------------------
def _load_triples(input_path: str) -> list:
    """从 Phase 2 产出的 JSONL 重建 list[Triple]（供 diagnose 命令用）"""
    from models.synthesis import Triple, Question, SQLResult, Rationale
    path = Path(input_path)
    if not path.exists():
        return []
    triples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            q = Question(
                question_id=rec.get("question_id", ""),
                text=rec.get("question", ""),
            )
            s = SQLResult(sql=rec.get("answer", rec.get("sql", "")))
            triples.append(Triple(question=q, sql_result=s))
    return triples
def _save_triples(triples: list, output: str, accepted_only: bool = False,
                  append: bool = False) -> None:
    """把 list[Triple] 写成 JSONL；训练导出仅接收已通过准入的样本。

    append=True 时追加写入（分批落盘的续写模式），否则覆盖。
    """
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    # 延迟导入，避免 Phase 2 未迁移时 cli import 失败
    from models.synthesis import Triple
    with open(output, "a" if append else "w", encoding="utf-8") as f:
        for t in triples:
            if isinstance(t, Triple):
                if accepted_only and t.rationale.admission_decision != "accepted":
                    continue
                f.write(json.dumps(t.to_training_record(), ensure_ascii=False) + "\n")
            else:
                f.write(json.dumps(t, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    cli()
