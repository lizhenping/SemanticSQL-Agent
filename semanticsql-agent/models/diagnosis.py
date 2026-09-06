"""诊断数据模型（论文 §III.E Eq.4）

对应论文 Phase 3 的 Diagnose / Retrieve / Correct 三个算子的输入输出。
Error 对齐论文 E（detected error types + locations in r），
Evidence 对齐 Φ（corrective evidence retrieved from K），
Correction 对齐论文要求的"append to r preserve refinement history"。
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from models.knowledge import (
    ColumnSemantics,
    FieldCategory,
    CrossTableRelation,
    DomainKnowledge,
    TableSemantics,
)


class ErrorType(str, Enum):
    """错误类型（对齐论文 §III.E + 现有 _classify_error）。

    分两类，呼应论文修改后的"程序化校验 + LLM 语义审查"混合：
    - 结构性错误（程序化校验产出）：COLUMN_* / JOIN_* / AGGREGATION_* / TABLE_* / SYNTAX / TYPE / EXECUTION / EMPTY
    - 语义性错误（LLM 审查产出）：SEMANTIC_INCONSISTENCY（带 SemanticClass 七类标注）
    """

    # 结构性错误（程序化校验，对齐论文 §III.E L268 的 checks/verifies/executes）
    COLUMN_NOT_FOUND = "column_not_found"
    COLUMN_SEMANTIC_MISMATCH = "column_semantic_mismatch"   # K4 语义不匹配
    JOIN_INVALID = "join_invalid"                           # K6 JOIN 不匹配外键
    AGGREGATION_TYPE_MISMATCH = "aggregation_type_mismatch"  # K3 聚合类型（Fig.1 解法）
    TABLE_NOT_FOUND = "table_not_found"
    SYNTAX_ERROR = "syntax_error"
    TYPE_ERROR = "type_error"
    EXECUTION_FAILED = "execution_failed"
    EMPTY_RESULT = "empty_result"

    # 语义性错误（LLM 审查，对齐论文 §III.E "semantic reviewer"）
    SEMANTIC_INCONSISTENCY = "semantic_inconsistency"
    SEMANTIC_REVIEW_FAILED = "semantic_review_failed"


class SemanticClass(str, Enum):
    """论文 Table semantic-taxonomy 的七类语义错误（§III.E + App.taxonomy）。

    Group I（意图错配，仅凭 (q, s) 即可判定，不取知识）：
      I-1 任务错配 / I-2 条件错配 / I-3 聚合或粒度错配 / I-4 排序或结果形式错配
    Group II（元素误用）：
      II-1 字段角色误用（证据 K3, K4）/ II-2 JOIN 误用（证据 K6）
    Group III（域规则违反）：
      III-1 域规则违反（证据 K2, K5, K6）
    """

    I_1_TASK_MISMATCH = "I-1"
    I_2_CONDITION_MISMATCH = "I-2"
    I_3_AGGREGATION_GRANULARITY_MISMATCH = "I-3"
    I_4_ORDERING_RESULT_FORM_MISMATCH = "I-4"
    II_1_FIELD_ROLE_MISUSE = "II-1"
    II_2_JOIN_MISUSE = "II-2"
    III_1_DOMAIN_RULE_VIOLATION = "III-1"


# 七类 → 取证所需的 K 层（论文 Table semantic-taxonomy 第三列）
SEMANTIC_CLASS_EVIDENCE: dict["SemanticClass", set[str]] = {
    SemanticClass.I_1_TASK_MISMATCH: set(),
    SemanticClass.I_2_CONDITION_MISMATCH: set(),
    SemanticClass.I_3_AGGREGATION_GRANULARITY_MISMATCH: set(),
    SemanticClass.I_4_ORDERING_RESULT_FORM_MISMATCH: set(),
    SemanticClass.II_1_FIELD_ROLE_MISUSE: {"K3", "K4"},
    SemanticClass.II_2_JOIN_MISUSE: {"K6"},
    SemanticClass.III_1_DOMAIN_RULE_VIOLATION: {"K2", "K5", "K6"},
}


class ErrorCategory(str, Enum):
    """错误的验证边界，避免把可执行性与语义正确性混为一谈。"""

    STRUCTURAL = "structural"
    SEMANTIC = "semantic"


class DetectorType(str, Enum):
    """错误发现者，用于分别报告确定性检查和 LLM 审查的效果。"""

    DETERMINISTIC = "deterministic"
    LLM = "llm"


class SampleDecision(str, Enum):
    """样本准入状态。只有 ACCEPTED 可以进入训练集。"""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNRESOLVED = "unresolved"


class ErrorLocation(BaseModel):
    """错误在 r 中的定位（论文要求 positions in r）"""

    clause: str = ""           # SELECT / WHERE / JOIN / GROUP BY / ORDER BY 等
    column: Optional[str] = None
    table: Optional[str] = None


class Error(BaseModel):
    """单个错误（论文 E 的元素）

    论文 §III.E：语义错误写作 e_j = (t_j, u_j, λ_j, v_j)，
    即 (类别, 受影响产物, 位置, 违反的条件)。对应字段：
    semantic_class=t_j, artifact=u_j, location=λ_j, detail=v_j。
    """

    type: ErrorType
    location: ErrorLocation = Field(default_factory=ErrorLocation)
    detail: str = ""
    evidence_ref: Optional[str] = None   # 指向 Evidence 的 key，便于 Retrieve 路由
    category: Optional[ErrorCategory] = None
    detector: Optional[DetectorType] = None
    # 论文七类语义错误类别（仅语义性错误填写）
    semantic_class: Optional[SemanticClass] = None
    # 受影响产物：q / s / r（论文 u_j；q 受影响 = 问题无效，不可修复 → 拒绝）
    artifact: Optional[str] = None
    # 违反的条件描述（论文 v_j）
    violated_condition: str = ""

    def model_post_init(self, __context) -> None:
        """为既有检查函数产生的 Error 补全可审计的来源和边界。"""
        if self.category is None:
            self.category = (
                ErrorCategory.SEMANTIC
                if self.type in {
                    ErrorType.SEMANTIC_INCONSISTENCY,
                    ErrorType.SEMANTIC_REVIEW_FAILED,
                    ErrorType.COLUMN_SEMANTIC_MISMATCH,
                }
                else ErrorCategory.STRUCTURAL
            )
        if self.detector is None:
            self.detector = (
                DetectorType.LLM
                if self.type == ErrorType.SEMANTIC_INCONSISTENCY
                else DetectorType.DETERMINISTIC
            )

    def with_location(self, clause: str = "", column: Optional[str] = None,
                      table: Optional[str] = None) -> "Error":
        """流式设置 location，便于 check 函数链式构造"""
        self.location = ErrorLocation(clause=clause, column=column, table=table)
        return self


class Evidence(BaseModel):
    """修正证据 Φ（论文 Retrieve 产物）。

    按错误类别从 K 的对应层取证（论文 Table semantic-taxonomy）：
    - columns（K4）：列语义正确描述，供 Correct 替换错误列引用（II-1）
    - field_types（K3）：字段类型，供聚合错误时找正确 measure 列（II-1）
    - relations（K6）：关系/外键，供 JOIN 错误时找正确连接键（II-2/III-1）
    - domain_rules（K2）：域规则（III-1）
    - table_constraints（K5）：表约束，供域规则违反修正参考（III-1）
    """

    columns: dict[str, ColumnSemantics] = Field(default_factory=dict)
    field_types: dict[str, FieldCategory] = Field(default_factory=dict)
    relations: list[CrossTableRelation] = Field(default_factory=list)
    domain_rules: Optional[DomainKnowledge] = None
    table_constraints: list[TableSemantics] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return (
            not self.columns
            and not self.field_types
            and not self.relations
            and self.domain_rules is None
            and not self.table_constraints
        )


class Correction(BaseModel):
    """单次修正记录（论文要求 append to r 保历史）。

    每次 Correct 算子执行后追加到 Rationale.correction_history，
    形成可追溯的精修轨迹（论文 §III.E "preserve the refinement history"）。
    """

    iteration: int
    errors_addressed: list[ErrorType] = Field(default_factory=list)
    sql_before: str = ""
    sql_after: str = ""
    summary: str = ""


class DiagnosisIteration(BaseModel):
    """Eq.4 的一次可复现检查，保存 Diagnose/Retrieve/Correct 的完整证据。"""

    iteration: int
    question: str = ""
    sql_before: str = ""
    rationale_focus: str = ""
    errors: list[Error] = Field(default_factory=list)
    evidence: Optional[Evidence] = None
    sql_after: Optional[str] = None
    execution_success_after: Optional[bool] = None
    execution_error_after: Optional[str] = None
    result_count_after: Optional[int] = None
    action: str = "verified"  # verified / corrected / max_iterations_reached


class DiagnosisTrace(BaseModel):
    """一个候选样本从原始生成到最终裁决的审计记录。"""

    question_id: str
    original_question: str = ""
    original_sql: str = ""
    max_correction_iterations: int = 0
    iterations: list[DiagnosisIteration] = Field(default_factory=list)
    final_question: str = ""
    final_sql: str = ""
    final_execution_success: Optional[bool] = None
    final_execution_error: Optional[str] = None
    final_result_count: Optional[int] = None
    decision: SampleDecision = SampleDecision.UNRESOLVED
    decision_reason: str = ""
