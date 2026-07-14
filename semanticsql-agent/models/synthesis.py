"""生成数据模型（论文 §III.D + Fig.training_data_format）

对应论文 Phase 2 的产物 (q, s, r) 三元组。
Rationale r 严格对齐论文 Fig.training_data_format 的结构化 think 对象：
focus / metadata / table_selection / column_selection / sql_strategy / expected_output
（当前代码完全缺失 sql_strategy，本模型补齐）。
"""

from typing import Optional

from pydantic import BaseModel, Field

from models.diagnosis import Error, Correction


class GenerationMetadata(BaseModel):
    """生成场景元数据（论文 σ=(C,T), ℓ）"""

    main_scenario: str = ""        # C 域上下文
    sub_scenario: str = ""         # T 分析任务类型
    complexity_level: int = 1      # ℓ ∈ {1,2,3,4} = L1..L4
    use_case: str = ""             # 操作用例


class TableSelection(BaseModel):
    """r.table_selection（论文 Fig.）"""

    tables_used: list[str] = Field(default_factory=list)
    reasoning: str = ""


class ColumnOperation(BaseModel):
    """r.column_selection 单项（论文 Fig.）"""

    name: str
    type: str = ""                 # 数据类型
    operation: str = ""            # SELECT/WHERE/GROUP BY/ORDER BY/AGG
    purpose: str = ""


class SQLStrategy(BaseModel):
    """r.sql_strategy（论文 Fig.，当前代码完全缺失，必须补）。

    记录 SQL 生成的策略选择，是论文结构化 think 的核心组成，
    也是 Phase 3 诊断时追溯 SQL 设计意图的依据。
    """

    operations: list[str] = Field(default_factory=list)   # 如 ["SELECT","ORDER BY DESC","LIMIT"]
    approach: str = ""            # 整体方法描述
    no_need: list[str] = Field(default_factory=list)      # 明确不需要的操作（如 JOIN/GROUP BY/MAX()）


class Rationale(BaseModel):
    """结构化推理链 r（论文 Fig.training_data_format 核心）。

    Phase 2 生成时填充 focus/metadata/table_selection/column_selection/
    sql_strategy/expected_output；
    Phase 3 反思阶段追加 errors 和 correction_history。
    """

    focus: str = ""
    metadata: GenerationMetadata = Field(default_factory=GenerationMetadata)
    table_selection: TableSelection = Field(default_factory=TableSelection)
    column_selection: list[ColumnOperation] = Field(default_factory=list)
    sql_strategy: SQLStrategy = Field(default_factory=SQLStrategy)
    expected_output: str = ""

    # Phase 3 反思阶段填充（论文 §III.E 要求）
    errors: list[Error] = Field(default_factory=list)
    correction_history: list[Correction] = Field(default_factory=list)


class Question(BaseModel):
    """q：自然语言问题"""

    question_id: str
    text: str = ""
    question_focus: str = ""       # 问题关注点（生成阶段产出）
    business_rules: list[dict] = Field(default_factory=list)  # 复杂查询的业务规则


class SQLResult(BaseModel):
    """s + 执行结果"""

    sql: str = ""
    dialect: str = "mysql"
    executed: bool = False
    execution_success: Optional[bool] = None
    result_count: Optional[int] = None
    execution_error: Optional[str] = None
    corrected_by_reflection: bool = False   # 是否经 Phase 3 修正


class Triple(BaseModel):
    """论文核心产物 (q, s, r)。

    一条合成训练样本。Phase 2 产出（q,r 完整 + s 已生成），
    Phase 3 可能修正三者的任意部分。
    """

    question: Question
    sql_result: SQLResult = Field(default_factory=SQLResult)
    rationale: Rationale = Field(default_factory=Rationale)

    @property
    def question_id(self) -> str:
        return self.question.question_id

    def to_training_record(self) -> dict:
        """转为论文 Fig.training_data_format 的 JSON 记录。

        合并 (q, s, r) 为单条训练数据，供 cli.save_training_data 写出。
        column_selection 输出为 {columns_used: [...]} 对齐论文格式。
        """
        return {
            "question": self.question.text,
            "think": {
                "focus": self.rationale.focus,
                "metadata": self.rationale.metadata.model_dump(),
                "table_selection": self.rationale.table_selection.model_dump(),
                "column_selection": {
                    "columns_used": [c.model_dump() for c in self.rationale.column_selection],
                },
                "sql_strategy": self.rationale.sql_strategy.model_dump(),
                "expected_output": self.rationale.expected_output,
            },
            "answer": self.sql_result.sql,
        }
