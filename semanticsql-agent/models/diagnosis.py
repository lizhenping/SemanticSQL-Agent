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
)


class ErrorType(str, Enum):
    """错误类型（对齐论文 §III.E + 现有 _classify_error）。

    分两类，呼应论文修改后的"程序化校验 + LLM 语义审查"混合：
    - 结构性错误（程序化校验产出）：COLUMN_* / JOIN_* / AGGREGATION_* / TABLE_* / SYNTAX / TYPE / EXECUTION / EMPTY
    - 语义性错误（LLM 审查产出）：SEMANTIC_INCONSISTENCY
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


class ErrorLocation(BaseModel):
    """错误在 r 中的定位（论文要求 positions in r）"""

    clause: str = ""           # SELECT / WHERE / JOIN / GROUP BY / ORDER BY 等
    column: Optional[str] = None
    table: Optional[str] = None


class Error(BaseModel):
    """单个错误（论文 E 的元素）"""

    type: ErrorType
    location: ErrorLocation = Field(default_factory=ErrorLocation)
    detail: str = ""
    evidence_ref: Optional[str] = None   # 指向 Evidence 的 key，便于 Retrieve 路由

    def with_location(self, clause: str = "", column: Optional[str] = None,
                      table: Optional[str] = None) -> "Error":
        """流式设置 location，便于 check 函数链式构造"""
        self.location = ErrorLocation(clause=clause, column=column, table=table)
        return self


class Evidence(BaseModel):
    """修正证据 Φ（论文 Retrieve 产物）。

    按错误类型从 K 的对应层取证：
    - columns（K4）：列语义正确描述，供 Correct 替换错误列引用
    - field_types（K3）：字段类型，供聚合错误时找正确 measure 列
    - relations（K6）：关系/外键，供 JOIN 错误时找正确连接键
    - domain_rules（K2）：域规则，供语义审查参考
    """

    columns: dict[str, ColumnSemantics] = Field(default_factory=dict)
    field_types: dict[str, FieldCategory] = Field(default_factory=dict)
    relations: list[CrossTableRelation] = Field(default_factory=list)
    domain_rules: Optional[DomainKnowledge] = None

    def is_empty(self) -> bool:
        return (
            not self.columns
            and not self.field_types
            and not self.relations
            and self.domain_rules is None
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
