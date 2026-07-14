"""K5: Table Analysis Tool（tools/analysis/table_analysis.py）

基于 K1 schema + K3 字段类型 + K4 列描述，用 LLM 为每表生成业务描述 + 业务类型
→ 写入 K5。K5 业务类型（entity/relation/config/log/data_table）是 Phase 2 选表
和 Phase 3 校验的关键语义。

迁移自 tools/analysis_tools/table_analysis_tool.py：
- 保留逐表 LLM 描述生成 + 字段分布统计 + 业务模式推断逻辑
- 改为依赖注入（BaseSemanticTool）
- 输入改读 kbase 的 K1/K3/K4，不再直接读 JSONL
- 输出改为 list[TableSemantics]，通过 kbase.set_table_semantics() 写入
- 删除 object.__setattr__、"请继续执行 X 工具" 指引字符串、jsonlines 直写
"""

import logging
from collections import Counter
from typing import Optional

from tools.base_tool import BaseSemanticTool
from models.knowledge import (
    SchemaMetadata,
    TableInfo,
    TableSemantics,
    FieldCategory,
)


class TableAnalysisTool(BaseSemanticTool):
    """K5：表语义描述生成

    用法：
        tool = TableAnalysisTool(llm=llm_client, kbase=kbase, prompt_manager=pm)
        tables = tool.run()
        # 自动写入 kbase.set_table_semantics(tables)
    """

    def __init__(self, **kwargs):
        super().__init__(name="table_analysis_tool", **kwargs)

    def run(self, schema: SchemaMetadata = None) -> list[TableSemantics]:
        """逐表生成描述 → 写入 K5 → 返回 list[TableSemantics]"""
        self.logger.info(f"🔧 {self.name}: 开始表语义分析")

        if self.llm is None:
            raise RuntimeError(f"{self.name} 未注入 llm")

        # 1. 取 K1 schema
        if schema is None:
            if self.kbase is None:
                raise RuntimeError(f"{self.name} 未注入 kbase，无法读取 K1 schema")
            schema = self.kbase.get_schema()
        if not schema.tables:
            raise RuntimeError(f"{self.name}: K1 schema 为空，请先执行 schema_extraction")

        # 2. 预索引 K3 字段类型 + K4 列描述
        field_types: dict[str, FieldCategory] = {}
        col_descs: dict[str, str] = {}
        if self.kbase:
            field_types = self.kbase.get_all_field_types()
            for col in self.kbase.get_column_semantics():
                col_descs[col.field_key] = col.description

        # 3. 逐表 LLM 生成描述
        semantics: list[TableSemantics] = []
        for table in schema.tables:
            desc = self._describe_table(table, field_types, col_descs)
            if desc is not None:
                semantics.append(desc)

        # 4. 写入 K5
        if self.kbase:
            self.kbase.set_table_semantics(semantics)

        self.logger.info(f"✅ {self.name}: 生成 {len(semantics)} 表描述")
        return semantics

    # ============================================================
    # 逐表 LLM 描述（保留原 _generate_table_description_with_llm 逻辑）
    # ============================================================

    def _describe_table(
        self,
        table: TableInfo,
        field_types: dict[str, FieldCategory],
        col_descs: dict[str, str],
    ) -> Optional[TableSemantics]:
        """对单表做 LLM 业务描述生成"""
        try:
            columns = [
                self._column_view(c, table.name, field_types, col_descs)
                for c in table.columns
            ]

            category_stats = self._analyze_field_category_distribution(columns)
            representative_samples = self._extract_representative_samples(columns)
            business_pattern = self._infer_table_business_pattern(category_stats)
            # 用 K1 真实计算的 entropy_level 汇总（不再用 category 猜）
            entropy_stats = self._compute_entropy_stats(table)
            entropy_guidance = self._get_entropy_guidance(entropy_stats)
            table_ddl = self._build_table_ddl_with_comments(table.name, columns)

            pk_count = sum(1 for c in table.columns if c.primary_key)
            fk_count = sum(1 for c in table.columns if c.foreign_key)

            prompt = self._render_tool_prompt(
                "table_description",
                table_name=table.name,
                database_name=self.kbase.database_name if self.kbase else "unknown",
                database_domain=(
                    self.kbase.get_domain().description if self.kbase else "general domain"
                ),
                table_schema_with_comments_ddl=table_ddl,
                total_columns=len(columns),
                field_category_stats=category_stats,
                entropy_stats=entropy_stats,
                entropy_guidance=entropy_guidance,
                representative_samples=representative_samples,
                table_business_pattern=business_pattern,
                primary_key_count=pk_count,
                foreign_key_count=fk_count,
            )
            response = self._llm_generate(prompt)
            description = self._clean_think_content(response)
            if len(description) < 2:
                return None

            business_type = self._infer_business_type(business_pattern)

            return TableSemantics(
                table_name=table.name,
                description=description,
                business_type=business_type,
                confidence=0.8,
                key_columns=[c["column_name"] for c in columns if c.get("is_primary")],
            )
        except Exception as e:
            self.logger.warning(f"表 {table.name} 描述生成失败: {e}")
            return None

    def _column_view(
        self,
        col,
        table_name: str,
        field_types: dict[str, FieldCategory],
        col_descs: dict[str, str],
    ) -> dict:
        """把 ColumnInfo 转成旧版 LLM 模板期望的 dict 视图"""
        field_key = f"{table_name}.{col.name}"
        category = field_types.get(field_key)
        return {
            "column_name": col.name,
            "data_type": col.data_type,
            "is_primary": col.primary_key,
            "is_foreign": col.foreign_key,
            "is_nullable": col.nullable,
            "category": category.value if category else "other",
            "category_desc": category.value if category else "other",
            "ai_business_desc": col_descs.get(field_key, "") or (col.comment or ""),
            "sample_values": col.sample_values,
        }

    # ============================================================
    # 表特征分析（保留原 _analyze/_infer/_extract 逻辑）
    # ============================================================

    def _analyze_field_category_distribution(self, columns: list[dict]) -> dict:
        """字段类别分布统计"""
        counts: Counter = Counter()
        examples: dict[str, list[str]] = {}
        for col in columns:
            cat = col.get("category", "other")
            counts[cat] += 1
            examples.setdefault(cat, [])
            if len(examples[cat]) < 3:
                examples[cat].append(col.get("column_name", ""))

        total = len(columns) or 1
        stats = {}
        for cat, n in counts.items():
            stats[cat] = {
                "category_desc": cat,
                "count": n,
                "percentage": round(n / total * 100, 1),
                "example_fields": examples[cat],
            }
        return stats

    def _extract_representative_samples(self, columns: list[dict]) -> list[dict]:
        """提取代表性样本值"""
        samples = []
        for col in columns:
            values = col.get("sample_values", [])
            if not values:
                continue
            formatted = []
            for v in values[:3]:
                if v is None:
                    continue
                s = str(v)
                if len(s) > 20:
                    s = s[:17] + "..."
                formatted.append(s)
            if formatted:
                samples.append({
                    "field_name": col.get("column_name", ""),
                    "category_desc": col.get("category_desc", "other"),
                    "samples": ", ".join(formatted),
                })
        return samples

    def _compute_entropy_stats(self, table) -> dict:
        """从 K1 真实计算的 ColumnInfo.entropy_level 汇总表级熵值分布。

        entropy_level 在 schema_extraction 时由 COUNT(DISTINCT)/row_count 计算：
          - low: cardinality < 0.1（枚举/状态字段）
          - medium: 0.1~0.7（分类/级别字段）
          - high: > 0.7（标识符/名称字段）
        """
        total = len(table.columns) or 1
        counts = {"low": 0, "medium": 0, "high": 0}
        for col in table.columns:
            level = getattr(col, "entropy_level", "medium")
            if level in counts:
                counts[level] += 1
            else:
                counts["medium"] += 1
        return {
            "low_count": counts["low"],
            "medium_count": counts["medium"],
            "high_count": counts["high"],
            "low_percentage": round(counts["low"] / total * 100, 1),
            "medium_percentage": round(counts["medium"] / total * 100, 1),
            "high_percentage": round(counts["high"] / total * 100, 1),
        }

    def _get_entropy_guidance(self, entropy_stats: dict) -> str:
        """根据熵值分布生成指导文本（对齐原 _get_entropy_guidance）"""
        low = entropy_stats.get("low_percentage", 0)
        high = entropy_stats.get("high_percentage", 0)
        medium = entropy_stats.get("medium_percentage", 0)
        if low > 60:
            return "数据重复度高，主要为状态、类型、等级等枚举类信息"
        if high > 40:
            return "数据多样性强，包含大量标识符、名称、金额等独特值"
        if medium > 50:
            return "数据分散适中，平衡了分类信息和个性化数据"
        return "数据特征混合，包含多种类型的业务信息"

    def _infer_table_business_pattern(self, category_stats: dict) -> str:
        """基于字段特征推断表的业务模式"""
        ident_count = category_stats.get("identifier", {}).get("count", 0)
        dim_count = category_stats.get("dimension", {}).get("count", 0)
        measure_count = category_stats.get("measure", {}).get("count", 0)

        if dim_count >= 3 and ident_count == 0:
            return "字典码表类型 - 主要存储枚举和分类信息"
        elif ident_count >= 2:
            return "主数据表类型 - 存储核心业务实体信息"
        elif measure_count > 0 and dim_count >= 3:
            return "事实表类型 - 记录业务交易和度量数据"
        elif dim_count >= 3:
            return "维度表类型 - 提供业务分析的分类维度"
        else:
            return "通用业务表 - 支持日常业务操作"

    def _infer_business_type(self, business_pattern: str) -> str:
        """把业务模式描述映射到 TableSemantics.business_type"""
        if "字典码表" in business_pattern or "枚举" in business_pattern:
            return "config"
        elif "主数据表" in business_pattern or "核心业务实体" in business_pattern:
            return "entity"
        elif "事实表" in business_pattern:
            return "data_table"
        elif "维度表" in business_pattern:
            return "dimension"
        else:
            return "data_table"

    def _build_table_ddl_with_comments(self, table_name: str, columns: list[dict]) -> str:
        """构建包含丰富元数据的表 DDL（保留原 _build_table_ddl_with_comments 逻辑）"""
        lines = [f"CREATE TABLE `{table_name}` ("]
        col_defs = []
        for col in columns:
            d = f"  `{col['column_name']}` {col.get('data_type') or 'VARCHAR(255)'}"
            if not col.get("is_nullable", True):
                d += " NOT NULL"
            if col.get("is_primary"):
                d += " PRIMARY KEY"

            comment_parts = []
            ai_desc = col.get("ai_business_desc", "")
            if ai_desc:
                comment_parts.append(ai_desc)
            cat_desc = col.get("category_desc", "")
            if cat_desc:
                comment_parts.append(f"[{cat_desc}]")
            values = col.get("sample_values", [])
            if values:
                formatted = []
                for v in values[:3]:
                    if v is None:
                        continue
                    s = str(v)
                    if len(s) > 15:
                        s = s[:12] + "..."
                    formatted.append(s)
                if formatted:
                    comment_parts.append(f"[样本:{','.join(formatted)}]")
            if comment_parts:
                d += f" COMMENT '{' '.join(comment_parts)}'"
            col_defs.append(d)
        lines.append(",\n".join(col_defs))
        lines.append(");")
        return "\n".join(lines)

    def _clean_think_content(self, text: str) -> str:
        """清理 <think> 标签"""
        import re
        if not isinstance(text, str):
            return ""
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL)
        return text.strip()
