"""知识库 K 唯一真相源（core/knowledge_store.py）

论文 §III.C 的 K = K1..K6，类型化访问层。
所有工具通过此类读写 K，不再直接碰 JSONL 文件（DRY）。

封装 KnowledgeStore，提供：
- 类型化 get/set（K1..K6 各有专属方法）
- Diagnose 专用：程序化校验（check_columns/check_joins/check_aggregation）
- Retrieve 专用：按错误取证（retrieve_evidence）

设计原则：
- DRY：6 个 JSONL 的读写逻辑只此一处，替代散落的路径计算
- K3 加载修复：当前 query_evidence 缺 field 层，本类统一加载全部 6 层
"""

import logging
from typing import Optional

from models.knowledge import (
    FieldCategory,
    ColumnInfo,
    TableInfo,
    SchemaMetadata,
    DomainKnowledge,
    FieldClassification,
    ColumnSemantics,
    TableSemantics,
    CrossTableRelation,
)
from models.diagnosis import Error, ErrorType, ErrorLocation, Evidence
from infra.storage import KnowledgeStore
from infra.sql_ast import AggregateCall, JoinClause


class KnowledgeBase:
    """论文 §III.C 的知识库 K = K1..K6

    用法：
        store = JSONLKnowledgeStore(history_dir)
        kbase = KnowledgeBase("financial", store)

        # Phase 1 写入
        kbase.set_schema(schema_metadata)          # K1
        kbase.set_domain(domain_knowledge)          # K2
        kbase.set_field_types(field_classifications) # K3
        kbase.set_column_semantics(column_semantics) # K4
        kbase.set_table_semantics(table_semantics)   # K5
        kbase.set_relations(cross_table_relations)   # K6

        # Phase 2 生成读取
        schema = kbase.get_schema()
        columns = kbase.get_columns("projects")

        # Phase 3 诊断校验
        errors = kbase.check_aggregation(aggregates)

        # Phase 3 取证
        evidence = kbase.retrieve_evidence(errors)
    """

    def __init__(self, database_name: str, store: KnowledgeStore):
        self.database_name = database_name
        self.store = store
        self.logger = logging.getLogger(__name__)

        # 缓存（懒加载）
        self._schema: Optional[SchemaMetadata] = None
        self._domain: Optional[DomainKnowledge] = None
        self._field_types: Optional[list[FieldClassification]] = None
        self._column_semantics: Optional[list[ColumnSemantics]] = None
        self._table_semantics: Optional[list[TableSemantics]] = None
        self._relations: Optional[list[CrossTableRelation]] = None

    # ============================================================
    # 写入（Phase 1 各阶段调用）
    # ============================================================

    def set_schema(self, schema: SchemaMetadata) -> None:
        """写入 K1：数据库元数据"""
        self.store.save("schema", schema.model_dump())
        self._schema = schema
        self.logger.info(f"K1 schema 已写入: {len(schema.tables)} 表")

    def set_domain(self, domain: DomainKnowledge) -> None:
        """写入 K2：域知识"""
        self.store.save("domain", domain.model_dump())
        self._domain = domain
        self.logger.info(f"K2 domain 已写入: {domain.domain_type}")

    def set_field_types(self, fields: list[FieldClassification]) -> None:
        """写入 K3：字段类型分类"""
        self.store.save("field", [f.model_dump() for f in fields])
        self._field_types = fields
        self.logger.info(f"K3 field_types 已写入: {len(fields)} 字段")

    def set_column_semantics(self, cols: list[ColumnSemantics]) -> None:
        """写入 K4：列语义描述"""
        self.store.save("column", [c.model_dump() for c in cols])
        self._column_semantics = cols
        self.logger.info(f"K4 column_semantics 已写入: {len(cols)} 列")

    def set_table_semantics(self, tables: list[TableSemantics]) -> None:
        """写入 K5：表语义描述"""
        self.store.save("table", [t.model_dump() for t in tables])
        self._table_semantics = tables
        self.logger.info(f"K5 table_semantics 已写入: {len(tables)} 表")

    def set_relations(self, rels: list[CrossTableRelation]) -> None:
        """写入 K6：跨表关系（ER）"""
        self.store.save("er", [r.model_dump() for r in rels])
        self._relations = rels
        self.logger.info(f"K6 relations 已写入: {len(rels)} 关系")

    # ============================================================
    # 读取（Phase 2 生成 + Phase 3 诊断）
    # ============================================================

    def get_schema(self) -> SchemaMetadata:
        """读取 K1"""
        if self._schema is None:
            records = self.store.load("schema")
            if records:
                self._schema = SchemaMetadata(**records[0])
            else:
                self._schema = SchemaMetadata(database_name=self.database_name)
        return self._schema

    def get_domain(self) -> DomainKnowledge:
        """读取 K2"""
        if self._domain is None:
            records = self.store.load("domain")
            if records:
                self._domain = DomainKnowledge(**records[0])
            else:
                self._domain = DomainKnowledge()
        return self._domain

    def get_field_types(self) -> list[FieldClassification]:
        """读取 K3（当前 query_evidence 缺这个！本类统一加载）"""
        if self._field_types is None:
            records = self.store.load("field")
            self._field_types = [FieldClassification(**r) for r in records]
        return self._field_types

    def get_column_semantics(self) -> list[ColumnSemantics]:
        """读取 K4"""
        if self._column_semantics is None:
            records = self.store.load("column")
            self._column_semantics = [ColumnSemantics(**r) for r in records]
        return self._column_semantics

    def get_table_semantics(self) -> list[TableSemantics]:
        """读取 K5"""
        if self._table_semantics is None:
            records = self.store.load("table")
            self._table_semantics = [TableSemantics(**r) for r in records]
        return self._table_semantics

    def get_relations(self) -> list[CrossTableRelation]:
        """读取 K6"""
        if self._relations is None:
            records = self.store.load("er")
            self._relations = [CrossTableRelation(**r) for r in records]
        return self._relations

    # ============================================================
    # 便捷查询方法
    # ============================================================

    def get_columns(self, table_name: str) -> list[ColumnSemantics]:
        """按表名查列语义（K4）"""
        return [c for c in self.get_column_semantics() if c.table_name == table_name]

    def get_column(self, table_name: str, column_name: str) -> Optional[ColumnSemantics]:
        """按 表.列 查单列语义（K4）"""
        for c in self.get_column_semantics():
            if c.table_name == table_name and c.column_name == column_name:
                return c
        return None

    def get_field_type(self, table_name: str, column_name: str) -> Optional[FieldCategory]:
        """按 表.列 查字段类型（K3）

        这是 Fig.1 AVG(CDSCode) 反例的检测基础：
        查 K3 得 CDSCode=identifier -> 聚合不合法
        """
        for f in self.get_field_types():
            if f.table_name == table_name and f.column_name == column_name:
                return f.category
        return None

    def get_all_field_types(self) -> dict[str, FieldCategory]:
        """全量字段类型（K3），返回 {"table.column": category}"""
        return {f.field_key: f.category for f in self.get_field_types()}

    def get_table_semantic(self, table_name: str) -> Optional[TableSemantics]:
        """按表名查表语义（K5）"""
        for t in self.get_table_semantics():
            if t.table_name == table_name:
                return t
        return None

    def get_foreign_keys(self) -> list[CrossTableRelation]:
        """获取外键关系（K6 子集）"""
        return [r for r in self.get_relations()
                if r.relationship_type in ("many_to_one", "one_to_many")]

    def get_table_names(self) -> list[str]:
        """获取所有表名（K1）"""
        return self.get_schema().all_table_names()

    # ============================================================
    # Diagnose 专用：程序化校验（论文 §III.E L268）
    # ============================================================

    def check_columns(self, ast_columns: list[tuple[str, str]]) -> list[Error]:
        """列存在性 + K4 语义校验（论文 "checks whether referenced columns exist"）

        Args:
            ast_columns: [(table, column), ...] 来自 SQLAstParser.extract_columns

        Returns:
            错误列表（列不存在或语义不匹配）
        """
        errors = []
        schema = self.get_schema()

        for table, column in ast_columns:
            if column == "*":
                continue

            # 检查列是否存在
            col_info = schema.get_column(table, column)
            if col_info is None:
                # 尝试在所有表里找（可能 SQL 没限定表名）
                found = any(
                    schema.get_column(t, column) is not None
                    for t in schema.all_table_names()
                )
                if not found:
                    errors.append(Error(
                        type=ErrorType.COLUMN_NOT_FOUND,
                        location=ErrorLocation(column=column, table=table),
                        detail=f"列 {table}.{column} 在数据库中不存在",
                    ))
                    continue

            # 检查 K4 语义（可选：描述是否为空）
            col_sem = self.get_column(table, column)
            if col_sem and not col_sem.description:
                errors.append(Error(
                    type=ErrorType.COLUMN_SEMANTIC_MISMATCH,
                    location=ErrorLocation(column=column, table=table),
                    detail=f"列 {table}.{column} 缺少语义描述",
                ))

        return errors

    def check_joins(self, joins: list[JoinClause]) -> list[Error]:
        """JOIN vs K6 外键校验（论文 "verifies JOIN conditions consistent with K6"）

        Args:
            joins: 来自 SQLAstParser.extract_joins

        Returns:
            错误列表（JOIN 不匹配外键结构）
        """
        errors = []
        fks = self.get_foreign_keys()

        # 构建合法 JOIN 对的集合 {(src_table, src_col, tgt_table, tgt_col)}
        valid_joins = set()
        for fk in fks:
            valid_joins.add((fk.source_table, fk.source_column, fk.target_table, fk.target_column))
            # 反向也合法
            valid_joins.add((fk.target_table, fk.target_column, fk.source_table, fk.source_column))

        for join in joins:
            # 检查 JOIN 的列对是否匹配某个外键
            forward = (join.left_table, join.left_column, join.right_table, join.right_column)
            reverse = (join.right_table, join.right_column, join.left_table, join.left_column)

            if forward not in valid_joins and reverse not in valid_joins:
                # 可能是合法的非外键 JOIN（如自然连接），记为警告而非硬错误
                # 只在 K6 有外键信息时才报错
                if fks:
                    errors.append(Error(
                        type=ErrorType.JOIN_INVALID,
                        location=ErrorLocation(
                            clause="JOIN",
                            table=f"{join.left_table} JOIN {join.right_table}",
                        ),
                        detail=f"JOIN {join.left_table}.{join.left_column} = "
                               f"{join.right_table}.{join.right_column} 不匹配 K6 外键结构",
                    ))

        return errors

    def check_aggregation(self, aggregates: list[AggregateCall]) -> list[Error]:
        """聚合参数 vs K3 类型校验（论文 "validating aggregation against K3"）

        这是论文 Fig.1（AVG(CDSCode)）反例的程序化检测：
        AVG -> 要求 measure，查 K3 得 CDSCode=identifier -> aggregation_type_mismatch

        Args:
            aggregates: 来自 SQLAstParser.extract_aggregates

        Returns:
            错误列表（聚合类型不匹配）
        """
        errors = []
        # 只有 SUM/AVG 对数值类型有要求；COUNT/MIN/MAX 相对宽松
        numeric_only_funcs = {"SUM", "AVG"}

        for agg in aggregates:
            if agg.func not in numeric_only_funcs:
                continue

            field_type = self.get_field_type(agg.table, agg.column)
            if field_type is None:
                # K3 没有该字段的分类，跳过（无法判断）
                continue

            if field_type != FieldCategory.MEASURE:
                errors.append(Error(
                    type=ErrorType.AGGREGATION_TYPE_MISMATCH,
                    location=ErrorLocation(
                        clause=agg.clause or "SELECT",
                        column=agg.column,
                        table=agg.table,
                    ),
                    detail=f"{agg.func}({agg.table}.{agg.column}) 要求 measure 类型，"
                           f"实际为 {field_type.value}（{self._category_description(field_type)}）",
                    evidence_ref=f"K3:{agg.table}.{agg.column}",
                ))

        return errors

    # ============================================================
    # Retrieve 专用：按错误取证（论文 §III.E Retrieve）
    # ============================================================

    def retrieve_evidence(self, errors: list[Error]) -> Evidence:
        """按错误类型路由到对应 K 层取证（论文 Φ）

        论文 §III.E: "Retrieve queries K using detected errors E to extract evidence Φ"

        路由规则：
        - column_* -> 取 K4 列语义（正确描述供 Correct 替换）
        - join_*   -> 取 K6 关系（正确 FK 供 Correct 修正 JOIN）
        - aggregation_* -> 取 K3 字段类型（正确 measure 列供 Correct 替换）
        """
        evidence = Evidence()

        for err in errors:
            if err.type in (ErrorType.COLUMN_NOT_FOUND, ErrorType.COLUMN_SEMANTIC_MISMATCH):
                # 取 K4：相关表的列语义
                if err.location.table:
                    for col in self.get_columns(err.location.table):
                        evidence.columns[col.field_key] = col

            elif err.type == ErrorType.JOIN_INVALID:
                # 取 K6：全部外键关系
                for fk in self.get_foreign_keys():
                    evidence.relations.append(fk)

            elif err.type == ErrorType.AGGREGATION_TYPE_MISMATCH:
                # 取 K3：相关表的字段类型
                if err.location.table:
                    for ft in self.get_field_types():
                        if ft.table_name == err.location.table:
                            evidence.field_types[ft.field_key] = ft.category

        # K2 域规则总是包含（供 LLM 语义审查参考）
        evidence.domain_rules = self.get_domain()

        return evidence

    # ============================================================
    # 辅助
    # ============================================================

    def _category_description(self, category: FieldCategory) -> str:
        """字段类型的可读描述"""
        descriptions = {
            FieldCategory.IDENTIFIER: "标识符，不可聚合",
            FieldCategory.MEASURE: "度量值，可聚合",
            FieldCategory.DIMENSION: "维度，可分组",
            FieldCategory.DATETIME: "日期时间",
            FieldCategory.TEXT: "文本",
            FieldCategory.BOOLEAN: "布尔",
            FieldCategory.OTHER: "其他",
        }
        return descriptions.get(category, str(category))

    def summary(self) -> dict:
        """K 的摘要统计（调试用）"""
        return {
            "database": self.database_name,
            "K1_schema": f"{len(self.get_schema().tables)} 表",
            "K2_domain": self.get_domain().domain_type or "未设置",
            "K3_field_types": f"{len(self.get_field_types())} 字段",
            "K4_column_semantics": f"{len(self.get_column_semantics())} 列",
            "K5_table_semantics": f"{len(self.get_table_semantics())} 表",
            "K6_relations": f"{len(self.get_relations())} 关系",
        }
