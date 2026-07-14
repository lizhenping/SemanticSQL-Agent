"""K4: Column Analysis Tool（tools/analysis/column_analysis.py）

基于 K1 schema + K3 字段类型，用 LLM 为每列生成业务描述 → 写入 K4。
K4 描述是 Phase 2 生成（选列、JOIN）和 Phase 3 校验（列存在性 + 语义）的关键证据。

迁移自 tools/analysis_tools/column_analysis_tool.py：
- 保留逐列 LLM 描述生成逻辑
- 改为依赖注入（BaseSemanticTool）
- 输入改读 kbase.get_schema()（K1）+ kbase.get_field_types()（K3），
  不再直接读 JSONL
- 输出改为 list[ColumnSemantics]，通过 kbase.set_column_semantics() 写入
- 删除 object.__setattr__、"请继续执行 X 工具" 指引字符串
"""

import logging
from typing import Optional

from tools.base_tool import BaseSemanticTool
from models.knowledge import (
    SchemaMetadata,
    TableInfo,
    ColumnInfo,
    ColumnSemantics,
    FieldCategory,
)


class ColumnAnalysisTool(BaseSemanticTool):
    """K4：列语义描述生成

    用法：
        tool = ColumnAnalysisTool(llm=llm_client, kbase=kbase, prompt_manager=pm)
        cols = tool.run()
        # 自动写入 kbase.set_column_semantics(cols)
    """

    def __init__(self, **kwargs):
        super().__init__(name="column_analysis_tool", **kwargs)

    def run(self, schema: SchemaMetadata = None) -> list[ColumnSemantics]:
        """逐列生成描述 → 写入 K4 → 返回 list[ColumnSemantics]"""
        self.logger.info(f"🔧 {self.name}: 开始列语义分析")

        if self.llm is None:
            raise RuntimeError(f"{self.name} 未注入 llm")

        # 1. 取 K1 schema
        if schema is None:
            if self.kbase is None:
                raise RuntimeError(f"{self.name} 未注入 kbase，无法读取 K1 schema")
            schema = self.kbase.get_schema()
        if not schema.tables:
            raise RuntimeError(f"{self.name}: K1 schema 为空，请先执行 schema_extraction")

        # 2. 预构造每表的 DDL（供 LLM 上下文）
        table_ddls = {t.name: self._format_table_ddl(t) for t in schema.tables}

        # 3. 预索引 K3 字段类型
        field_types: dict[str, FieldCategory] = {}
        if self.kbase:
            field_types = self.kbase.get_all_field_types()

        # 4. 逐列 LLM 生成描述
        semantics: list[ColumnSemantics] = []
        for table in schema.tables:
            for col in table.columns:
                desc = self._describe_column(table, col, table_ddls, field_types)
                if desc is not None:
                    semantics.append(desc)

        # 5. 写入 K4
        if self.kbase:
            self.kbase.set_column_semantics(semantics)

        self.logger.info(f"✅ {self.name}: 生成 {len(semantics)} 列描述")
        return semantics

    # ============================================================
    # DDL 格式化（保留原 _format_table_ddl 逻辑）
    # ============================================================

    def _format_table_ddl(self, table: TableInfo) -> str:
        """格式化单表 DDL（供 LLM 上下文）"""
        lines = [f"CREATE TABLE `{table.name}` ("]
        col_defs = []
        for col in table.columns:
            d = f"  `{col.name}` {col.data_type or 'VARCHAR(255)'}"
            if not col.nullable:
                d += " NOT NULL"
            if col.primary_key:
                d += " PRIMARY KEY"
            if col.comment:
                d += f" COMMENT '{col.comment}'"
            col_defs.append(d)
        lines.append(",\n".join(col_defs))
        lines.append(");")
        return "\n".join(lines)

    # ============================================================
    # 逐列 LLM 描述（保留原 _generate_column_description_with_llm 逻辑）
    # ============================================================

    def _describe_column(
        self,
        table: TableInfo,
        col: ColumnInfo,
        table_ddls: dict[str, str],
        field_types: dict[str, FieldCategory],
    ) -> Optional[ColumnSemantics]:
        """对单列做 LLM 业务描述生成"""
        try:
            field_key = f"{table.name}.{col.name}"
            category = field_types.get(field_key)

            prompt = self._render_tool_prompt(
                "column_description",
                table_name=table.name,
                column_name=col.name,
                database_name=self.kbase.database_name if self.kbase else "unknown",
                database_domain=(
                    self.kbase.get_domain().description if self.kbase else "general domain"
                ),
                table_ddl=table_ddls.get(table.name, ""),
                column_type=col.data_type,
                is_nullable=col.nullable,
                is_primary_key=col.primary_key,
                is_foreign_key=col.foreign_key,
                column_examples=col.sample_values,
                field_category=category.value if category else "other",
                # entropy_info: 从 K1 的 entropy_level 构造（真实计算的 cardinality ratio）
                entropy_info={"level": col.entropy_level},
                # dim_or_meas: 从 K3 field_category 映射
                dim_or_meas=category.value if category in (
                    FieldCategory.MEASURE, FieldCategory.DIMENSION
                ) else "dimension",
                # field_importance: 从 PK/FK + category 推导
                field_importance="high" if (col.primary_key or col.foreign_key) else (
                    "medium" if category in (FieldCategory.MEASURE, FieldCategory.DIMENSION)
                    else "low"
                ),
            )
            response = self._llm_generate(prompt)
            description = self._parse_description_response(response)
            if not description:
                return None

            return ColumnSemantics(
                table_name=table.name,
                column_name=col.name,
                description=description,
                confidence=0.8,
                source="generated",
                field_category=category,
                data_type=col.data_type,
                is_nullable=col.nullable,
                is_primary_key=col.primary_key,
            )
        except Exception as e:
            self.logger.warning(f"列 {table.name}.{col.name} 描述生成失败: {e}")
            return None

    def _parse_description_response(self, response: str) -> Optional[str]:
        """解析 LLM 描述响应（纯文本，去 think 标签）"""
        import re
        text = response.strip()
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL)
        text = text.strip()
        if len(text) < 2:
            return None
        return text
