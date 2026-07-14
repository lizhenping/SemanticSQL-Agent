"""K1: Schema Extraction Tool（tools/analysis/schema_extraction.py）

从数据库提取元数据，构建 SchemaMetadata → 写入 KnowledgeBase K1。

迁移自 tools/analysis_tools/schema_extraction_tool.py：
- 保留核心 DB 查询逻辑（INFORMATION_SCHEMA 查询、采样值、熵计算）
- 改为依赖注入（BaseSemanticTool）
- 删除"请继续执行 X 工具"指引字符串
- 输出改为 models.knowledge.SchemaMetadata
- 支持 MySQL 和 SQLite（论文数据集全是 sqlite）
"""

import logging
from typing import Any, Optional

from tools.base_tool import BaseSemanticTool
from models.knowledge import SchemaMetadata, TableInfo, ColumnInfo


class SchemaExtractionTool(BaseSemanticTool):
    """K1：从数据库提取元数据

    用法：
        tool = SchemaExtractionTool(llm=None, db=db_manager, kbase=kbase)
        schema = tool.run(database_name="financial")
        # 自动写入 kbase.set_schema(schema)
    """

    def __init__(self, **kwargs):
        super().__init__(name="schema_extraction_tool", **kwargs)

    def run(self, database_name: str = "") -> SchemaMetadata:
        """提取 schema → 写入 K1 → 返回 SchemaMetadata

        Args:
            database_name: 数据库名（sqlite 时为文件路径的 stem）
        """
        self.logger.info(f"🔧 {self.name}: 开始提取数据库结构")

        if self.db is None:
            raise RuntimeError(f"{self.name} 未注入 db（DatabaseManager）")

        # 初始化连接（如果尚未初始化）
        if self.db.engine is None:
            self.db.initialize()

        # 根据数据库类型选择提取方式
        if self.db.db_type == "sqlite":
            schema = self._extract_sqlite_schema(database_name)
        else:
            schema = self._extract_mysql_schema(database_name)

        # 写入 K1
        if self.kbase:
            self.kbase.set_schema(schema)

        self.logger.info(f"✅ {self.name}: 提取完成，{len(schema.tables)} 表")
        return schema

    # ============================================================
    # SQLite 提取（论文数据集全部是 sqlite）
    # ============================================================

    def _extract_sqlite_schema(self, database_name: str) -> SchemaMetadata:
        """从 SQLite 提取 schema（通过 SQLAlchemy inspector）"""
        from sqlalchemy import inspect

        inspector = inspect(self.db.engine)
        table_names = inspector.get_table_names()

        tables = []
        for table_name in table_names:
            table_info = self._extract_sqlite_table(inspector, table_name)
            tables.append(table_info)

        db_name = database_name or self.db.database
        return SchemaMetadata(database_name=db_name, tables=tables)

    def _extract_sqlite_table(self, inspector, table_name: str) -> TableInfo:
        """提取单个 SQLite 表的信息"""
        columns_raw = inspector.get_columns(table_name)
        pk_info = inspector.get_pk_constraint(table_name)
        fk_info = inspector.get_foreign_keys(table_name)

        pk_names = pk_info.get("constrained_columns", []) if pk_info else []
        fk_columns = set()
        for fk in fk_info:
            fk_columns.update(fk.get("constrained_columns", []))

        # 采样值（每列取少量 distinct 值）
        sample_values = self._sample_sqlite_values(table_name)
        # 行数（用于 entropy 计算）
        row_count = self._get_row_count(table_name)

        columns = []
        for col_raw in columns_raw:
            col_name = col_raw["name"]
            # 真实计算 entropy_level：COUNT(DISTINCT col) / row_count
            entropy_level = self._compute_entropy_level(table_name, col_name, row_count)
            columns.append(ColumnInfo(
                name=col_name,
                data_type=str(col_raw.get("type", "")),
                nullable=col_raw.get("nullable", True),
                primary_key=col_name in pk_names,
                foreign_key=col_name in fk_columns,
                default=str(col_raw["default"]) if col_raw.get("default") else None,
                comment=None,  # sqlite 通常无 comment
                sample_values=sample_values.get(col_name, []),
                entropy_level=entropy_level,
            ))

        return TableInfo(
            name=table_name,
            columns=columns,
            primary_keys=pk_names,
            row_count=row_count,
            comment=None,
        )

    def _compute_entropy_level(
        self, table_name: str, col_name: str, row_count: Optional[int]
    ) -> str:
        """计算列的熵值等级（基于 cardinality ratio）。

        COUNT(DISTINCT col) / row_count:
          - < 0.1  -> low（重复度高，枚举/状态字段）
          - 0.1~0.7 -> medium（分类/级别字段）
          - > 0.7  -> high（唯一性强，标识符/名称字段）
        """
        from sqlalchemy import text
        if not row_count or row_count == 0:
            return "medium"
        try:
            with self.db.engine.connect() as conn:
                result = conn.execute(text(
                    f"SELECT COUNT(DISTINCT `{col_name}`) FROM `{table_name}` "
                    f"WHERE `{col_name}` IS NOT NULL"
                ))
                distinct_count = result.fetchone()[0]
                if not distinct_count:
                    return "medium"
                ratio = distinct_count / row_count
                if ratio < 0.1:
                    return "low"
                elif ratio > 0.7:
                    return "high"
                else:
                    return "medium"
        except Exception:
            return "medium"

    def _sample_sqlite_values(self, table_name: str, limit: int = 5) -> dict:
        """采样每列的 distinct 值（供合成数据用）"""
        from sqlalchemy import text
        samples = {}
        try:
            with self.db.engine.connect() as conn:
                # 获取列名
                result = conn.execute(text(f"PRAGMA table_info(`{table_name}`)"))
                columns = [row[1] for row in result]
                for col in columns:
                    try:
                        result = conn.execute(text(
                            f"SELECT DISTINCT `{col}` FROM `{table_name}` "
                            f"WHERE `{col}` IS NOT NULL LIMIT {limit}"
                        ))
                        values = [row[0] for row in result]
                        if values:
                            # 截断过长的字符串
                            samples[col] = [
                                str(v)[:40] if isinstance(v, str) else v
                                for v in values
                            ]
                    except Exception:
                        pass
        except Exception as e:
            self.logger.warning(f"采样 {table_name} 值失败: {e}")
        return samples

    def _get_row_count(self, table_name: str) -> Optional[int]:
        """获取表行数"""
        from sqlalchemy import text
        try:
            with self.db.engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM `{table_name}`"))
                return result.fetchone()[0]
        except Exception:
            return None

    # ============================================================
    # MySQL 提取（保留原有逻辑，供 MySQL 模式使用）
    # ============================================================

    def _extract_mysql_schema(self, database_name: str) -> SchemaMetadata:
        """从 MySQL 提取 schema（通过 INFORMATION_SCHEMA）"""
        db_name = database_name or self.db.database

        # 获取所有表名
        all_tables = self._mysql_get_table_names()
        filtered_tables = self._filter_tables(all_tables, ["aid_info"])

        tables = []
        for table_name in filtered_tables:
            table_info = self._mysql_extract_table(table_name)
            tables.append(table_info)

        return SchemaMetadata(database_name=db_name, tables=tables)

    def _mysql_get_table_names(self) -> list:
        """获取所有表名（MySQL）"""
        sql = f"SELECT TABLE_NAME as table_name FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = '{self.db.database}'"
        result = self.db.execute_sql_safe(sql)
        if result.get("success") and result.get("data"):
            return [row["table_name"] for row in result["data"]]
        return []

    def _mysql_extract_table(self, table_name: str) -> TableInfo:
        """提取单个 MySQL 表"""
        # 获取表注释
        table_comment = self._mysql_get_table_comment(table_name)

        # 获取列信息
        columns_raw = self._mysql_get_columns(table_name)

        columns = []
        for row in columns_raw:
            col_name = row["column_name"]
            columns.append(ColumnInfo(
                name=col_name,
                data_type=row["data_type"],
                nullable=row.get("is_nullable", "YES") == "YES",
                primary_key=row.get("column_key") == "PRI",
                foreign_key=False,  # MySQL FK 检测保留在原逻辑
                comment=row.get("column_comment") or None,
                sample_values=[],  # MySQL 采样保留在原逻辑
            ))

        return TableInfo(
            name=table_name,
            columns=columns,
            primary_keys=[c.name for c in columns if c.primary_key],
            comment=table_comment or None,
        )

    def _mysql_get_table_comment(self, table_name: str) -> str:
        """获取表注释（MySQL）"""
        sql = (
            f"SELECT TABLE_COMMENT as table_comment FROM INFORMATION_SCHEMA.TABLES "
            f"WHERE TABLE_SCHEMA = '{self.db.database}' AND TABLE_NAME = '{table_name}'"
        )
        result = self.db.execute_sql_safe(sql)
        if result.get("success") and result.get("data"):
            return result["data"][0].get("table_comment", "") or ""
        return ""

    def _mysql_get_columns(self, table_name: str) -> list:
        """获取列信息（MySQL）"""
        sql = f"""
        SELECT COLUMN_NAME as column_name, DATA_TYPE as data_type,
               IS_NULLABLE as is_nullable, COLUMN_KEY as column_key,
               COLUMN_COMMENT as column_comment
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = '{self.db.database}' AND TABLE_NAME = '{table_name}'
        ORDER BY ORDINAL_POSITION
        """
        result = self.db.execute_sql_safe(sql)
        if result.get("success") and result.get("data"):
            return result["data"]
        return []

    def _filter_tables(self, table_names: list, blacklist: list) -> list:
        """过滤表名（黑名单）"""
        if not blacklist:
            return table_names
        return [t for t in table_names if not any(b in t for b in blacklist)]
