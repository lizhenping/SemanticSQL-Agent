"""K6: ER Relation Analysis Tool（tools/analysis/er_analysis.py）

基于 K1~K5，用 LLM 推断表间概念 ER 关系 → 写入 K6（list[CrossTableRelation]）。
K6 是 Phase 2 多表 JOIN 和 Phase 3 JOIN 校验（论文 §III.E check_joins）的关键证据：
  论文 "verifies JOIN conditions consistent with K6"。

迁移自 tools/analysis_tools/er_analysis_tool.py：
- 保留 LLM 生成 + 实体/属性/关系校验逻辑
- 改为依赖注入（BaseSemanticTool）
- 输入改读 kbase 的 K1~K5，不再直接读 JSONL
- 输出改为 list[CrossTableRelation]，通过 kbase.set_relations() 写入
- 把 LLM 的嵌套 business_domain/er_relation 结构扁平化为 CrossTableRelation 列表
- 删除 object.__setattr__、"请继续执行 X 工具" 指引字符串
"""

import logging
import re
from typing import Optional

from tools.base_tool import BaseSemanticTool
from models.knowledge import (
    SchemaMetadata,
    CrossTableRelation,
)


class ERAnalysisTool(BaseSemanticTool):
    """K6：跨表关系（ER）推断

    用法：
        tool = ERAnalysisTool(llm=llm_client, kbase=kbase, prompt_manager=pm)
        rels = tool.run()
        # 自动写入 kbase.set_relations(rels)
    """

    def __init__(self, **kwargs):
        super().__init__(name="er_analysis_tool", **kwargs)

    def run(self, schema: SchemaMetadata = None) -> list[CrossTableRelation]:
        """推断 ER 关系 → 写入 K6 → 返回 list[CrossTableRelation]"""
        self.logger.info(f"🔧 {self.name}: 开始 ER 关系分析")

        if self.llm is None:
            raise RuntimeError(f"{self.name} 未注入 llm")

        # 1. 取 K1 schema
        if schema is None:
            if self.kbase is None:
                raise RuntimeError(f"{self.name} 未注入 kbase，无法读取 K1 schema")
            schema = self.kbase.get_schema()
        if not schema.tables:
            raise RuntimeError(f"{self.name}: K1 schema 为空，请先执行 schema_extraction")

        # 2. 聚合 K1~K5 上下文
        context = self._gather_database_context(schema)

        # 3. LLM 生成 ER 关系
        er_result = self._perform_er_analysis(context)

        # 4. 扁平化为 CrossTableRelation 列表 + 校验
        relations = self._to_cross_table_relations(er_result, context)

        # 5. 写入 K6
        if self.kbase:
            self.kbase.set_relations(relations)

        self.logger.info(f"✅ {self.name}: 推断 {len(relations)} 个关系")
        return relations

    # ============================================================
    # 上下文聚合（替代原 _gather_database_context_from_jsonl）
    # ============================================================

    def _gather_database_context(self, schema: SchemaMetadata) -> dict:
        """从 kbase 聚合 K1~K5 成 LLM 模板期望的 context 结构"""
        tables: dict[str, dict] = {}
        for table in schema.tables:
            # K5 表描述
            table_desc = ""
            if self.kbase:
                ts = self.kbase.get_table_semantic(table.name)
                if ts:
                    table_desc = ts.description
            tables[table.name] = {
                "name": table.name,
                "description": table_desc or (table.comment or ""),
                "columns": [],
            }
            for col in table.columns:
                # K4 列描述
                col_desc = ""
                if self.kbase:
                    cs = self.kbase.get_column(table.name, col.name)
                    if cs:
                        col_desc = cs.description
                tables[table.name]["columns"].append({
                    "name": col.name,
                    "data_type": col.data_type or "unknown",
                    "comment": col_desc or (col.comment or ""),
                    "is_primary_key": col.primary_key,
                    "is_foreign": col.foreign_key,
                    "sample_values": col.sample_values,
                })

        domain_desc = self.kbase.get_domain().description if self.kbase else ""
        return {
            "database_name": self.kbase.database_name if self.kbase else schema.database_name,
            "database_desc": domain_desc,
            "tables": tables,
        }

    # ============================================================
    # LLM 分析（保留原 _perform_er_analysis 逻辑）
    # ============================================================

    def _perform_er_analysis(self, context: dict) -> dict:
        """调 LLM 生成 business_domain + er_relation 结构"""
        prompt_data = {
            "formatted_schema": self._format_schema_with_descriptions(context),
            "fk_info": self._format_foreign_key_info(context),
            "tables": context["tables"],
            "database_name": context["database_name"],
        }
        prompt = self._render_prompt("tools/er_analysis_conceptual.j2", **prompt_data)
        response = self._llm_generate_json(prompt)
        return self._validate_er_analysis(response, context)

    def _format_schema_with_descriptions(self, context: dict) -> str:
        """格式化带注释的表结构"""
        lines = ["数据库表结构（包含业务注释）："]
        for table_name, table_info in context["tables"].items():
            lines.append(f"\n表: {table_name}")
            if table_info.get("description"):
                lines.append(f"  注释: {table_info['description']}")
            lines.append("  列:")
            for column in table_info["columns"]:
                info = f"    - {column['name']} ({column.get('data_type', 'unknown')})"
                if column.get("is_primary_key"):
                    info += " [主键]"
                if column.get("is_foreign"):
                    info += " [外键]"
                if column.get("comment"):
                    info += f" -- {column['comment']}"
                lines.append(info)
        return "\n".join(lines)

    def _format_foreign_key_info(self, context: dict) -> str:
        """基于列名模式推测外键关系"""
        tables = context["tables"]
        lines = ["外键关系信息："]
        fk_relations = []
        for table_name, table_info in tables.items():
            for column in table_info.get("columns", []):
                col_name = column.get("name", "")
                # *_id 或 *id 模式
                ref_table = None
                if col_name.endswith("_id"):
                    ref_table = col_name[:-3]
                elif col_name.endswith("id") and len(col_name) > 2:
                    ref_table = col_name[:-2]
                if ref_table and (ref_table in tables or f"{ref_table}s" in tables):
                    target = ref_table if ref_table in tables else f"{ref_table}s"
                    fk_relations.append(
                        f"  {table_name}.{col_name} -> {target}.id (推测外键)"
                    )
        if fk_relations:
            lines.extend(fk_relations)
        else:
            lines.append("  未发现明显的外键关系")
        return "\n".join(lines)

    # ============================================================
    # 校验（保留原 _validate_er_analysis 核心校验）
    # ============================================================

    def _validate_er_analysis(self, er_analysis: dict, context: dict) -> dict:
        """校验 LLM 返回的 business_domain + er_relation 结构"""
        tables = context["tables"]
        if "business_domain" not in er_analysis:
            raise RuntimeError(f"{self.name}: LLM 响应缺少 business_domain 字段")
        if "er_relation" not in er_analysis:
            raise RuntimeError(f"{self.name}: LLM 响应缺少 er_relation 字段")

        er_relation = er_analysis["er_relation"]
        er_relation.setdefault("entities", [])
        er_relation.setdefault("inter_entity_relations", [])

        # 校验实体属性引用的表/列确实存在
        table_columns = {
            t: {c["name"] for c in info["columns"]} for t, info in tables.items()
        }
        valid_entities = []
        for entity in er_relation["entities"]:
            if "name" not in entity:
                continue
            valid_attrs = []
            for attr in entity.get("attributes", []):
                if not all(k in attr for k in ("column", "table")):
                    continue
                if attr["table"] not in table_columns:
                    continue
                if attr["column"] not in table_columns[attr["table"]]:
                    continue
                valid_attrs.append(attr)
            entity["attributes"] = valid_attrs
            if valid_attrs:
                valid_entities.append(entity)
        er_relation["entities"] = valid_entities

        # 校验实体间关系两端都存在
        entity_names = {e["name"] for e in valid_entities}
        valid_relations = []
        for rel in er_relation["inter_entity_relations"]:
            if not all(k in rel for k in ("from_entity", "to_entity", "relation_type")):
                continue
            if rel["from_entity"] not in entity_names or rel["to_entity"] not in entity_names:
                continue
            valid_relations.append(rel)
        er_relation["inter_entity_relations"] = valid_relations

        return er_analysis

    # ============================================================
    # 扁平化为 CrossTableRelation（K6 目标结构）
    # ============================================================

    def _to_cross_table_relations(
        self, er_result: dict, context: dict
    ) -> list[CrossTableRelation]:
        """把 LLM 的嵌套结构转为 list[CrossTableRelation]

        转换来源（按可靠性排序）：
        1. K1 schema 的物理外键元数据（最可靠，如 concert_singer 有真实 FK 约束）
        2. 推测外键（*_id / *id 列名，大小写不敏感 + 表名归一）
        3. LLM 实体间关系 inter_entity_relations: 实体名 -> 表名映射后生成
        """
        relations: list[CrossTableRelation] = []
        er_relation = er_result.get("er_relation", {})
        tables = context["tables"]
        seen: set[tuple] = set()

        # 0. 预建小写表名索引（供大小写不敏感匹配）
        table_names_lower = {t.lower(): t for t in tables}

        # 1. K1 物理外键（最可靠）
        if self.kbase:
            schema = self.kbase.get_schema()
            for table in schema.tables:
                for col in table.columns:
                    if col.foreign_key:
                        # SQLAlchemy inspector 不直接给引用表/列，用列名启发找目标
                        tgt = self._find_fk_target(col.name, table_names_lower)
                        if tgt:
                            key = (table.name, col.name, tgt[0], tgt[1])
                            if key not in seen:
                                seen.add(key)
                                relations.append(CrossTableRelation(
                                    source_table=table.name,
                                    source_column=col.name,
                                    target_table=tgt[0],
                                    target_column=tgt[1],
                                    relationship_type="many_to_one",
                                    confidence=0.9,
                                    reason="物理外键约束（K1）",
                                ))

        # 2. *_id / *id 命名推测（大小写不敏感，兜底补充）
        for table_name, table_info in tables.items():
            for column in table_info.get("columns", []):
                col_name = column.get("name", "")
                tgt = self._find_fk_target(col_name, table_names_lower)
                if not tgt:
                    continue
                key = (table_name, col_name, tgt[0], tgt[1])
                if key in seen:
                    continue
                seen.add(key)
                relations.append(CrossTableRelation(
                    source_table=table_name,
                    source_column=col_name,
                    target_table=tgt[0],
                    target_column=tgt[1],
                    relationship_type="many_to_one",
                    confidence=0.6,
                    reason="命名规则推测（*_id）",
                ))

        # 3. LLM 实体间关系（实体名 -> 表名映射）
        entity_to_table = self._build_entity_table_map(
            er_relation.get("entities", []), tables
        )
        for rel in er_relation.get("inter_entity_relations", []):
            src_table = entity_to_table.get(rel.get("from_entity", ""))
            tgt_table = entity_to_table.get(rel.get("to_entity", ""))
            if not src_table or not tgt_table:
                continue
            key = (src_table, tgt_table)
            if key in seen:
                continue
            seen.add(key)
            relations.append(CrossTableRelation(
                source_table=src_table,
                target_table=tgt_table,
                relationship_type=self._normalize_relation_type(rel.get("relation_type", "")),
                confidence=0.7,
                reason=rel.get("business_meaning", rel.get("relation_type", "")),
            ))

        return relations

    def _find_fk_target(
        self, col_name: str, table_names_lower: dict
    ) -> Optional[tuple]:
        """从列名推测外键目标表（大小写不敏感，返回 (table, pk_col)）"""
        low = col_name.lower()
        ref = None
        if low.endswith("_id"):
            ref = low[:-3]
        elif low.endswith("id") and len(low) > 2:
            ref = low[:-2]
        if not ref:
            return None
        # 目标表的主键列名通常和 FK 列名相同；尝试精确表名匹配
        if ref in table_names_lower:
            return (table_names_lower[ref], col_name)
        # 单复数归一
        if ref + "s" in table_names_lower:
            return (table_names_lower[ref + "s"], col_name)
        if ref.rstrip("s") in table_names_lower:
            return (table_names_lower[ref.rstrip("s")], col_name)
        return None

    def _build_entity_table_map(self, entities: list[dict], tables: dict) -> dict:
        """实体名 -> 表名映射（精确匹配优先，其次单复数归一）"""
        mapping: dict[str, str] = {}
        table_names = set(tables.keys())
        for entity in entities:
            name = entity.get("name", "")
            if not name:
                continue
            if name in table_names:
                mapping[name] = name
            elif name + "s" in table_names:
                mapping[name] = name + "s"
            elif name.rstrip("s") in table_names:
                mapping[name] = name.rstrip("s")
        return mapping

    def _normalize_relation_type(self, raw: str) -> str:
        """把 LLM 返回的关系类型描述归一到 many_to_one / one_to_many / many_to_many / one_to_one"""
        r = raw.lower().replace("-", "_").replace(" ", "_")
        if "many_to_many" in r or "m:n" in r or "n:m" in r:
            return "many_to_many"
        if "one_to_one" in r or "1:1" in r:
            return "one_to_one"
        if "one_to_many" in r or "1:n" in r:
            return "one_to_many"
        # 默认 many_to_one（最常见 FK 形态）
        return "many_to_one"
