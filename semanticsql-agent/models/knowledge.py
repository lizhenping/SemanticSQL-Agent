"""知识库数据模型 K1..K6（论文 §III.C Table II）

对应论文的六阶段知识抽取产物。所有字段对齐 JSONL 实际存储结构，
同时为 nl2sql 移植过来的算法提供类型化接口。

设计原则：
- 纯数据，零外部依赖（最内层 models）
- 字段名与 JSONL 实际存储一致，避免序列化层翻译
- FieldCategory 对齐 nl2sql 的分类 + 论文 K3 语义
"""

from enum import Enum
from typing import Optional, Any

from pydantic import BaseModel, Field


class FieldCategory(str, Enum):
    """K3 字段类型分类（对齐 nl2sql FieldCategory + 论文 K3）。

    语义校验关键：IDENTIFIER 不可聚合（Fig.1 的 AVG(CDSCode) 解法），
    MEASURE 才可 SUM/AVG。
    """

    IDENTIFIER = "identifier"   # 标识符（如 CDSCode），不可聚合
    MEASURE = "measure"         # 度量（可 SUM/AVG）
    DIMENSION = "dimension"     # 维度（可 GROUP BY）
    DATETIME = "datetime"
    TEXT = "text"
    BOOLEAN = "boolean"
    OTHER = "other"


# ============================================================
# K1: Schema Metadata（元数据）
# ============================================================

class ColumnInfo(BaseModel):
    """K1 基础列元数据"""

    name: str
    data_type: str
    nullable: bool = True
    primary_key: bool = False
    foreign_key: bool = False
    default: Optional[str] = None
    comment: Optional[str] = None
    sample_values: list[Any] = Field(default_factory=list)
    entropy_level: str = "medium"  # low / medium / high（由 K1 计算 cardinality ratio）


class TableInfo(BaseModel):
    """K1 基础表元数据"""

    name: str
    columns: list[ColumnInfo] = Field(default_factory=list)
    primary_keys: list[str] = Field(default_factory=list)
    row_count: Optional[int] = None
    comment: Optional[str] = None


class SchemaMetadata(BaseModel):
    """K1 完整 schema（DatabaseSchema）"""

    database_name: str
    database_desc: str = ""
    tables: list[TableInfo] = Field(default_factory=list)

    def get_table(self, table_name: str) -> Optional[TableInfo]:
        """按名查表"""
        for t in self.tables:
            if t.name == table_name:
                return t
        return None

    def get_column(self, table_name: str, column_name: str) -> Optional[ColumnInfo]:
        """按 表.列 查列"""
        t = self.get_table(table_name)
        if t is None:
            return None
        for c in t.columns:
            if c.name == column_name:
                return c
        return None

    def all_table_names(self) -> list[str]:
        return [t.name for t in self.tables]


# ============================================================
# K2: Domain Knowledge（域约束）
# ============================================================

class DomainKnowledge(BaseModel):
    """K2 域知识"""

    domain_type: str = ""
    description: str = ""
    business_concepts: list[str] = Field(default_factory=list)
    naming_patterns: list[str] = Field(default_factory=list)


# ============================================================
# K3: Field Type Analysis（字段类型）
# ============================================================

class FieldClassification(BaseModel):
    """K3 单字段分类"""

    table_name: str
    column_name: str
    category: FieldCategory
    confidence: float = 0.8
    reasoning: str = ""
    data_type: Optional[str] = None

    @property
    def field_key(self) -> str:
        """统一键 "table.column"（nl2sql 约定）"""
        return f"{self.table_name}.{self.column_name}"


# ============================================================
# K4: Column Analysis（列语义）
# ============================================================

class ColumnSemantics(BaseModel):
    """K4 列语义描述"""

    table_name: str
    column_name: str
    description: str
    confidence: float = 0.8
    source: str = "generated"      # "existing" | "generated" | "corrected"
    corrected: bool = False
    correction_reason: Optional[str] = None
    field_category: Optional[FieldCategory] = None
    data_type: Optional[str] = None
    is_nullable: Optional[bool] = None
    is_primary_key: Optional[bool] = None

    @property
    def field_key(self) -> str:
        return f"{self.table_name}.{self.column_name}"


# ============================================================
# K5: Table Analysis（表语义）
# ============================================================

class TableSemantics(BaseModel):
    """K5 表语义描述"""

    table_name: str
    description: str
    business_type: str = "data_table"  # entity/relation/config/log/data_table
    confidence: float = 0.8
    key_columns: list[str] = Field(default_factory=list)


# ============================================================
# K6: Relation Analysis（跨表关系 / ER）
# ============================================================

class CrossTableRelation(BaseModel):
    """K6 跨表关系（ER）

    统一表示物理外键和概念关系。source/target 约定：
    source_table.source_column → target_table.target_column
    """

    source_table: str
    source_column: Optional[str] = None
    target_table: str
    target_column: Optional[str] = None
    relationship_type: str = "many_to_one"
    confidence: float = 0.5
    reason: str = ""

    def involves(self, table_name: str) -> bool:
        """该关系是否涉及指定表"""
        return table_name in (self.source_table, self.target_table)
