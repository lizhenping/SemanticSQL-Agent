"""Phase 2 / (s, r): SQL Synthesis Tool（tools/synthesis/sql_synth.py）

基于 K1~K6 + 已合成的 Question q，用 LLM 生成 SQL s 和结构化推理链 r。
产物：Triple(q, s, r)（论文 §III.D 的核心三元组）。

迁移自 tools/generation_tools/sql_generation_tool.py：
- 保留 LLM 生成 SQL + 上下文聚合 + SQL 后处理逻辑
- 改为依赖注入（BaseSemanticTool），不再内部 create_llm()
- 输入改读 kbase（K1/K4/K5/K6）+ Question，不再直接读 JSONL
- 输出改为 models.synthesis.Triple（不再写 sql_results.jsonl）
- ⭐ 删除内嵌 reflection（_run_reflection）：反思归 Phase 3（S6），
  Phase 2 只管生成，Diagnose→Correct 循环由 pipeline.run_diagnosis() 编排
- 补齐论文要求的 sql_strategy（原代码完全缺失，models.synthesis.SQLStrategy 已定义）
- 删除 object.__setattr__、log_sql_activity、jsonlines 直写
"""

import logging
import re
from typing import Optional

from tools.base_tool import BaseSemanticTool
from models.knowledge import SchemaMetadata
from models.synthesis import (
    Question,
    SQLResult,
    Triple,
    Rationale,
    GenerationMetadata,
    TableSelection,
    ColumnOperation,
    SQLStrategy,
)


class SQLSynthTool(BaseSemanticTool):
    """Phase 2 (s, r)：基于 q + K 生成 SQL 和推理链

    用法：
        tool = SQLSynthTool(llm=llm, kbase=kbase, prompt_manager=pm, db=db)
        triple = tool.run(question)
        # triple.sql_result.sql 是生成的 SQL
        # triple.rationale 是结构化推理链
    """

    def __init__(self, dialect: str = "sqlite", **kwargs):
        super().__init__(name="sql_synth_tool", **kwargs)
        # 论文数据集全是 sqlite；MySQL 场景可注入 mysql
        self.dialect = dialect

    def run(
        self,
        question: Question,
        execute: bool = True,
        schema: SchemaMetadata = None,
    ) -> Triple:
        """对单个 Question 生成 SQL + Rationale → 返回 Triple

        Args:
            question: Phase 2 上一步合成的 Question
            execute: 是否执行 SQL 验证（默认 True，执行失败不抛错，记入 SQLResult）
            schema: 可选 K1 schema；None 则从 kbase 读
        """
        self.logger.info(f"🔧 {self.name}: 生成 SQL for {question.question_id}")

        if self.llm is None:
            raise RuntimeError(f"{self.name} 未注入 llm")
        if self.kbase is None:
            raise RuntimeError(f"{self.name} 未注入 kbase，无法读取 K1~K6")

        if schema is None:
            schema = self.kbase.get_schema()

        # 1. 聚合 K1~K6 上下文成 prompt 可用结构
        context = self._build_context(schema, question)

        # 2. 渲染 prompt + LLM 生成
        sql, rationale_raw = self._generate_sql_with_llm(question, context)

        # 3. 后处理 SQL
        sql = self._postprocess_sql(sql)

        # 4. 执行验证（可选）
        sql_result = self._maybe_execute(sql, execute)

        # 5. 组装 Rationale（论文 Fig.training_data_format 结构）
        rationale = self._build_rationale(question, rationale_raw, context)

        return Triple(question=question, sql_result=sql_result, rationale=rationale)

    # ============================================================
    # 上下文聚合（替代原 _gather_jsonl_context，改读 kbase）
    # ============================================================

    def _build_context(self, schema: SchemaMetadata, question: Question) -> dict:
        """聚合 K1/K4/K5/K6 + Question 成 SQL 生成上下文"""
        # K1 schema → tables
        tables: dict[str, dict] = {}
        for table in schema.tables:
            # K5 表描述
            t_desc = ""
            if self.kbase:
                ts = self.kbase.get_table_semantic(table.name)
                if ts:
                    t_desc = ts.description
            cols = []
            for col in table.columns:
                # K4 列描述
                c_desc = ""
                if self.kbase:
                    cs = self.kbase.get_column(table.name, col.name)
                    if cs:
                        c_desc = cs.description
                cols.append({
                    "name": col.name,
                    "type": col.data_type,
                    "comment": c_desc or (col.comment or ""),
                    "is_primary": col.primary_key,
                    "is_foreign": col.foreign_key,
                    "is_nullable": col.nullable,
                })
            tables[table.name] = {
                "name": table.name,
                "comment": t_desc or (table.comment or ""),
                "columns": cols,
            }

        # K6 外键关系
        foreign_keys = self._extract_foreign_keys(schema)

        return {
            "schema_info": {"tables": tables},
            "foreign_keys": foreign_keys,
            "question_data": {
                "question_text": question.text,
                "question_focus": question.question_focus,
                "business_rules": question.business_rules,
            },
        }

    def _extract_foreign_keys(self, schema: SchemaMetadata) -> list[dict]:
        """从 K6 取外键关系（优先用 kbase，回退到列名启发式）"""
        fks: list[dict] = []
        if self.kbase:
            for rel in self.kbase.get_relations():
                fks.append({
                    "from_table": rel.source_table,
                    "to_table": rel.target_table,
                    "column_name": rel.source_column or "",
                    "from": f"{rel.source_table}.{rel.source_column}" if rel.source_column else rel.source_table,
                    "to": f"{rel.target_table}.{rel.target_column}" if rel.target_column else rel.target_table,
                    "relationship_type": rel.relationship_type,
                })
        if fks:
            return fks

        # 回退：列名 *_id 启发式（与 er_analysis 一致）
        table_names = set(schema.all_table_names())
        for table in schema.tables:
            for col in table.columns:
                ref = None
                if col.name.endswith("_id"):
                    ref = col.name[:-3]
                elif col.name.endswith("id") and len(col.name) > 2:
                    ref = col.name[:-2]
                if ref and ref in table_names:
                    fks.append({
                        "from_table": table.name,
                        "to_table": ref,
                        "column_name": col.name,
                        "from": f"{table.name}.{col.name}",
                        "to": f"{ref}.id",
                        "relationship_type": "many_to_one",
                    })
        return fks

    # ============================================================
    # LLM 生成（保留原 _generate_sql_with_context 逻辑）
    # ============================================================

    def _generate_sql_with_llm(
        self, question: Question, context: dict
    ) -> tuple[str, dict]:
        """渲染 prompt + 调 LLM → (sql, rationale_raw_dict)"""
        enhanced = self._build_enhanced_context(question, context)
        q_data = context["question_data"]

        prompt = self._render_prompt(
            "tools/sql_generation.j2",
            question=q_data["question_text"],
            context=enhanced,
            dialect=self.dialect,
            question_focus=q_data.get("question_focus", ""),
            expected_output="",  # Phase 2 不预知答案，expected_output 留 Phase 3 校验
            business_rules=q_data.get("business_rules", []),
            join_relationships=context.get("foreign_keys", []),
        )

        response = self._llm_generate(prompt)
        sql, rationale_raw = self._parse_sql_and_rationale(response)
        return sql, rationale_raw

    def _parse_sql_and_rationale(self, response: str) -> tuple[str, dict]:
        """从 LLM 响应解析 (sql, rationale)。

        模板要求 LLM 返回 {"sql": "...", "rationale": {...}} 的 JSON。
        若解析失败，退化为只提取 SQL（rationale 留空，Phase 3 可补）。
        """
        import json

        # 尝试解析完整 JSON
        try:
            start = response.find("{")
            end = response.rfind("}")
            if start >= 0 and end > start:
                parsed = json.loads(response[start:end + 1])
                sql = parsed.get("sql", "")
                rationale = parsed.get("rationale", {})
                if not sql:
                    sql = self._extract_sql_from_response(response)
                if not isinstance(rationale, dict):
                    rationale = {}
                return sql, rationale
        except (json.JSONDecodeError, ValueError):
            pass

        # 退化为只提取 SQL
        return self._extract_sql_from_response(response), {}

    def _build_enhanced_context(self, question: Question, context: dict) -> str:
        """构建给 LLM 的增强上下文文本（保留原 _build_enhanced_context 逻辑）"""
        parts: list[str] = []
        schema_info = context.get("schema_info", {})
        tables = schema_info.get("tables", {})
        foreign_keys = context.get("foreign_keys", [])

        # 数据库结构（相关表）
        if tables:
            parts.append("数据库结构：")
            for table_name, t_info in tables.items():
                parts.append(f"\n表: {table_name}")
                if t_info.get("comment"):
                    parts.append(f"  说明: {t_info['comment']}")
                parts.append("  列:")
                for col in t_info.get("columns", [])[:15]:
                    line = f"    - {col.get('name')} ({col.get('type')})"
                    if col.get("comment"):
                        line += f" -- {col['comment']}"
                    if col.get("is_primary"):
                        line += " [PK]"
                    if col.get("is_foreign"):
                        line += " [FK]"
                    parts.append(line)

        # 外键关系
        if foreign_keys:
            parts.append("\n外键关系:")
            for rel in foreign_keys[:10]:
                parts.append(f"  - {rel.get('from', '')} → {rel.get('to', '')}")

        return "\n".join(parts)

    # ============================================================
    # SQL 后处理（保留原 _extract_sql_from_response + _postprocess_sql）
    # ============================================================

    def _extract_sql_from_response(self, response: str) -> str:
        """从 LLM 响应提取 SQL"""
        # ```sql ... ```
        m = re.search(r"```sql\s*(.*?)\s*```", response, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1).strip()
        # ``` ... ```（无 sql 标识）
        m = re.search(r"```\s*(.*?)\s*```", response, re.DOTALL)
        if m:
            content = m.group(1).strip()
            if any(k in content.upper() for k in ("SELECT", "WITH", "INSERT", "UPDATE", "DELETE")):
                return content
        return response.strip()

    def _postprocess_sql(self, sql: str) -> str:
        """清理 markdown 标记 + 规范化空白 + 确保分号结尾"""
        sql = re.sub(r"```sql\s*", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"```\s*", "", sql)
        sql = re.sub(r"\s+", " ", sql).strip()
        if not sql.endswith(";"):
            sql += ";"
        return sql

    # ============================================================
    # 执行验证（保留原 _execute_sql_safely，改用注入的 db）
    # ============================================================

    def _maybe_execute(self, sql: str, execute: bool) -> SQLResult:
        """可选执行 SQL，结果记入 SQLResult（不抛错，失败也是有效信号）"""
        result = SQLResult(sql=sql, dialect=self.dialect)
        if not execute or self.db is None:
            result.executed = False
            return result

        try:
            ret = self.db.execute_sql_safe(sql, limit=100)
            if ret.get("success"):
                data = ret.get("data", [])
                result.executed = True
                result.execution_success = True
                result.result_count = len(data)
            else:
                result.executed = True
                result.execution_success = False
                result.execution_error = ret.get("error", "execution failed")
        except Exception as e:
            result.executed = True
            result.execution_success = False
            result.execution_error = str(e)
            self.logger.warning(f"SQL 执行失败: {e}")
        return result

    # ============================================================
    # Rationale 组装（论文 Fig.training_data_format）
    # ============================================================

    def _build_rationale(
        self, question: Question, rationale_raw: dict, context: dict
    ) -> Rationale:
        """组装结构化推理链 r（focus/metadata/table_selection/column_selection/sql_strategy）

        rationale_raw 是 LLM 返回的嵌套 JSON，对齐论文 Fig.training_data_format：
            {
              "focus": "...",
              "table_selection": {"tables_used": [...], "reasoning": "..."},
              "column_selection": {"columns_used": [{name, type, operation, purpose}]},
              "sql_strategy": {"operations": [...], "approach": "...", "no_need": [...]},
              "expected_output": "..."
            }
        """
        q_data = context["question_data"]
        metadata = GenerationMetadata(
            main_scenario=question.business_rules[0].get("main_scenario", "") if question.business_rules else "",
            sub_scenario=question.business_rules[0].get("sub_scenario", "") if question.business_rules else "",
            use_case=question.business_rules[0].get("use_case", "") if question.business_rules else "",
        )

        # table_selection（嵌套结构）
        ts_raw = rationale_raw.get("table_selection", {}) or {}
        table_selection = TableSelection(
            tables_used=ts_raw.get("tables_used", []),
            reasoning=ts_raw.get("reasoning", ""),
        )

        # column_selection（嵌套在 columns_used 里，对齐论文格式）
        cs_raw = rationale_raw.get("column_selection", {}) or {}
        columns_list = cs_raw.get("columns_used", []) if isinstance(cs_raw, dict) else cs_raw
        column_selection: list[ColumnOperation] = []
        for col in columns_list:
            if isinstance(col, dict):
                column_selection.append(ColumnOperation(
                    name=col.get("name", ""),
                    type=col.get("type", ""),
                    operation=col.get("operation", ""),
                    purpose=col.get("purpose", ""),
                ))

        # sql_strategy
        strategy_raw = rationale_raw.get("sql_strategy", {}) or {}
        sql_strategy = SQLStrategy(
            operations=strategy_raw.get("operations", []),
            approach=strategy_raw.get("approach", ""),
            no_need=strategy_raw.get("no_need", []),
        )

        return Rationale(
            focus=rationale_raw.get("focus", "") or q_data.get("question_focus", question.question_focus),
            metadata=metadata,
            table_selection=table_selection,
            column_selection=column_selection,
            sql_strategy=sql_strategy,
            expected_output=rationale_raw.get("expected_output", ""),
        )
