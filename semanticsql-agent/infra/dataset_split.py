"""数据集隔离层（infra/dataset_split.py）

防止数据泄露（data leakage）：合成训练数据时，绝不能用到评估（dev/test）用的库。

论文 §IV 的评估协议：在 dev/test 集上评估生成质量。若合成阶段"见过"这些库的
schema，会高估效果。本模块是合成前的强制闸门。

隔离策略（按 benchmark 实际情况分三类）：
1. spider / bird：train 库与 dev 库不重叠 → 维护 dev 库黑名单，合成时拒绝
2. science_benchmark：train 与 dev 共用同一批库（按 QA 切分）→ 库级不隔离，
   但 pipeline 只从 schema 合成、不读官方 QA，所以合成问题不会与 eval QA 重复
3. ehrsql：仅 2 个库，train/eval/test 共用 → 同 science，靠 pipeline 不读 QA 隔离
4. spider2：官方 SQLite 子集本身就是合成用，无 dev/test 泄露风险

数据来源：从各 benchmark 的 qa/eval/*.json 提取的 dev 库清单（见本文件 EVAL_DBs）。
"""

import logging
from pathlib import Path
from typing import Optional


class DatasetSplitError(Exception):
    """数据隔离违规：试图在评估库上合成训练数据"""


# ============================================================
# 各 benchmark 的评估（dev/test）库黑名单
# 从 数据集/<benchmark>/qa/eval/*.json 提取，禁止用于合成
# ============================================================

EVAL_DBS: dict[str, set[str]] = {
    "spider": {
        # dev.json 的 20 个库
        "battle_death", "car_1", "concert_singer", "course_teach",
        "cre_Doc_Template_Mgt", "dog_kennels", "employee_hire_evaluation",
        "flight_2", "museum_visit", "network_1", "news_report",
        "perpetual_student", "riding_club", "sports_competition",
        "voter_1", "world_1", "tvshow", "student_1", "storm_record",
        "tracking_software_problems",
        # test.json 的 40 个库（test_gold.sql 对应，不公开 gold 但库公开）
        "documents_products", "gas_company", "game_injury", "apartment_rentals",
        "loan_1", "student_2", "tracking_grants_for_research", "shipping_records",
        "assets_maintenance", "bike_1", "manufacturer", "climbing",
        "railway", "icfp_1", "local_govt_in_detail", "race_track",
        "insurance_policies", "farm", "musical", "games_1",
        "program_exhibition", "museum", "preschool", "sports_1",
        "public_review", "wrestler", "ship_1", "hockey_1",
        "codebase_subsite", "concert_singer", "debate", "film_rank",
        "feeding_the_homeless", "architecture", "company_1", "device",
        "election", "school_busines", "coffee_1", "swimming",
    },
    "bird": {
        # dev.json 的 11 个库
        "california_schools", "card_games", "codebase_community",
        "debit_card_specializing", "european_football_2", "financial",
        "formula_1", "student_club", "superhero", "thrombosis_prediction",
        "toxicology",
    },
    # science_benchmark / ehrsql：train 与 eval 共用同一批库，
    # 库级无法隔离；靠 pipeline 不读官方 QA 天然隔离（合成的问题不会与 eval QA 重复）
    "science_benchmark": set(),
    "ehrsql": set(),
    "spider2": set(),
}


def assert_train_only(benchmark: str, database: str) -> None:
    """校验某库是否允许用于合成（必须在 train 划分，不在 dev/test）

    Args:
        benchmark: spider / bird / spider2 / ehrsql / science_benchmark
        database: 数据库名

    Raises:
        DatasetSplitError: 该库属于评估集，禁止用于合成
    """
    eval_dbs = EVAL_DBS.get(benchmark, set())
    if database in eval_dbs:
        raise DatasetSplitError(
            f"数据泄露防护：库 '{database}' 属于 {benchmark} 的评估集（dev/test），"
            f"不能用于合成训练数据。请改用 train 划分的库。\n"
            f"  spider train 库示例: activity_1, academic, baseball_1, ...\n"
            f"  bird train 库示例: address, airline, app_store, ..."
        )


def is_eval_db(benchmark: str, database: str) -> bool:
    """判断某库是否属于评估集（不抛错，返回布尔）"""
    return database in EVAL_DBS.get(benchmark, set())


def list_train_databases(benchmark: str, db_root: str) -> list[str]:
    """列出某 benchmark 下所有可用于合成的库（排除 dev/test）

    扫描 {db_root}/{benchmark}/databases/ 目录，过滤掉评估库。

    Args:
        benchmark: benchmark 名
        db_root: 数据集根目录

    Returns:
        可用于合成的库名列表（按库名字母序）
    """
    eval_dbs = EVAL_DBS.get(benchmark, set())
    dbs_dir = Path(db_root) / benchmark / "databases"
    if not dbs_dir.exists():
        return []
    train_dbs = []
    for db_dir in dbs_dir.iterdir():
        if not db_dir.is_dir():
            continue
        db_name = db_dir.name
        if db_name in eval_dbs:
            continue
        sqlite_file = db_dir / f"{db_name}.sqlite"
        if sqlite_file.exists():
            train_dbs.append(db_name)
    return sorted(train_dbs)
