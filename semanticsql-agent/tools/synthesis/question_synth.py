"""Phase 2 / q: Question Synthesis Tool（tools/synthesis/question_synth.py）

基于 K1~K6 知识库，按 (场景 × 子场景 × 复杂度) 三层循环用 LLM 合成自然语言问题 q。
产物：list[Question]（论文 §III.D 的 q，Triple 的第一元）。

迁移自 tools/generation_tools/question_generator.py：
- 保留三层 for 循环场景驱动逻辑（scenarios.yaml × operation_mapping.yaml × complexity.yaml）
- 改为依赖注入（BaseSemanticTool），不再内部 create_llm()
- 输入改读 kbase（K1 schema / K4 列语义 / K5 表语义 / K6 关系），不再直接读 JSONL
- 输出改为 models.synthesis.Question（不再写 questions_generated.jsonl）
- 删除 object.__setattr__、"请继续执行 X 工具" 指引字符串、jsonlines 直写
- 表-列验证改用 kbase.get_schema()，不再维护 table_column_mapping
"""

import logging
import random
import uuid
from pathlib import Path
from typing import Any, Optional

import yaml

from tools.base_tool import BaseSemanticTool
from models.knowledge import SchemaMetadata
from models.synthesis import Question, GenerationMetadata


# YAML 配置里要跳过的元数据键（不是真实场景）
_META_KEYS = {"scenario_types", "total_scenarios", "total_sub_scenarios"}
# 复杂度级别顺序
_COMPLEXITY_ORDER = ["simple", "moderate", "complex", "expert"]
# 简单/中等/复杂/专家 → 论文 ℓ ∈ {1,2,3,4}
_COMPLEXITY_TO_LEVEL = {"simple": 1, "moderate": 2, "complex": 3, "expert": 4}


class QuestionSynthTool(BaseSemanticTool):
    """Phase 2 q：场景驱动的问题合成

    用法：
        tool = QuestionSynthTool(llm=llm, kbase=kbase, prompt_manager=pm)
        questions = tool.run(count=100)
    """

    def __init__(
        self,
        config_dir: Optional[str] = None,
        seed: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(name="question_synth_tool", **kwargs)
        # 配置目录（默认 semanticsql-agent/config）
        if config_dir is None:
            config_dir = Path(__file__).parent.parent.parent / "config"
        self.config_dir = Path(config_dir)
        # 加载三个 YAML（场景驱动配置，论文 σ=(C,T) 的 C/T 来源）
        self.scenarios = self._load_yaml("scenarios.yaml")
        self.operation_mapping = self._load_yaml("operation_mapping.yaml")
        self.complexity_config = self._load_yaml("complexity.yaml")
        # 可复现的随机源
        self._rng = random.Random(seed)

    # ============================================================
    # 主入口
    # ============================================================

    def run(self, count: int = 10, schema: SchemaMetadata = None) -> list[Question]:
        """合成 count 个自然语言问题 → 返回 list[Question]"""
        self.logger.info(f"🔧 {self.name}: 开始合成 {count} 个问题")

        if self.llm is None:
            raise RuntimeError(f"{self.name} 未注入 llm")
        if self.kbase is None:
            raise RuntimeError(f"{self.name} 未注入 kbase，无法读取 K1~K6")

        if schema is None:
            schema = self.kbase.get_schema()
        if not schema.tables:
            raise RuntimeError(f"{self.name}: K1 schema 为空，请先执行 Phase 1 Analysis")

        # 预聚合 K1/K4/K5/K6 成模板期望的结构
        tables_data = self._build_tables_context(schema)
        er_data = self._build_er_context()

        # 三层循环生成问题
        questions = self._generate_by_scenario_loop(count, tables_data, er_data)

        self.logger.info(f"✅ {self.name}: 合成完成 {len(questions)} 个问题")
        return questions

    # ============================================================
    # 三层循环（保留原 generate_questions 核心逻辑）
    # ============================================================

    def _generate_by_scenario_loop(
        self,
        count: int,
        tables_data: list[dict],
        er_data: dict,
    ) -> list[Question]:
        """遍历 (主场景 × 子场景 × 复杂度) 用 LLM 生成问题"""
        questions: list[Question] = []
        scenarios = self.scenarios["scenarios"]
        scenario_uc_map = self.operation_mapping["scenario_use_case_mapping"]
        use_case_operations = self.operation_mapping["use_case_operations"]

        # 第一轮：按 YAML 顺序穷举所有组合
        for main_key, main_data in scenarios.items():
            if main_key in _META_KEYS:
                continue
            for sub_key, sub_data in main_data.get("sub_scenarios", {}).items():
                for complexity in _COMPLEXITY_ORDER:
                    combo = self._resolve_combo(
                        main_key, sub_key, complexity, scenario_uc_map, use_case_operations
                    )
                    if combo is None:
                        continue
                    use_case_name, use_case = combo

                    q = self._generate_one(
                        main_data, sub_data, complexity,
                        use_case_name, use_case,
                        tables_data, er_data,
                    )
                    if q is not None:
                        questions.append(q)
                        self.logger.info(
                            f"生成 {len(questions)}/{count}: "
                            f"{main_key}/{sub_key}/{complexity}"
                        )
                        if len(questions) >= count:
                            return questions

        # 第二轮：不够 count 时随机采样补齐
        valid_mains = [k for k in scenarios if k not in _META_KEYS]
        while len(questions) < count and valid_mains:
            main_key = self._rng.choice(valid_mains)
            main_data = scenarios[main_key]
            sub_keys = list(main_data.get("sub_scenarios", {}).keys())
            if not sub_keys:
                continue
            sub_key = self._rng.choice(sub_keys)
            sub_data = main_data["sub_scenarios"][sub_key]
            complexity = self._rng.choice(_COMPLEXITY_ORDER)

            combo = self._resolve_combo(
                main_key, sub_key, complexity, scenario_uc_map, use_case_operations
            )
            if combo is None:
                continue
            use_case_name, use_case = combo

            q = self._generate_one(
                main_data, sub_data, complexity,
                use_case_name, use_case,
                tables_data, er_data,
            )
            if q is not None:
                questions.append(q)

        return questions

    def _resolve_combo(
        self,
        main_key: str,
        sub_key: str,
        complexity: str,
        scenario_uc_map: dict,
        use_case_operations: dict,
    ) -> Optional[tuple[str, dict]]:
        """解析某 (场景,子场景,复杂度) 对应的 use_case"""
        bucket = (
            scenario_uc_map.get(main_key, {})
            .get(sub_key, {})
            .get(complexity)
        )
        if not bucket:
            return None
        # bucket 是 [{use_case_name: weight}, ...]，拍平成名字列表
        names: list[str] = []
        for item in bucket:
            names.extend(item.keys())
        if not names:
            return None
        name = self._rng.choice(names)
        use_case = use_case_operations.get(
            name, use_case_operations.get("data_viewing", {})
        )
        return name, use_case

    def _generate_one(
        self,
        main_data: dict,
        sub_data: dict,
        complexity: str,
        use_case_name: str,
        use_case: dict,
        tables_data: list[dict],
        er_data: dict,
    ) -> Optional[Question]:
        """渲染 prompt + 调 LLM 生成单个 Question"""
        complexity_cfg = self.complexity_config["complexity_levels"][complexity]

        template_data = {
            "main_scenario": {
                "name": main_data.get("name", ""),
                "description": main_data.get("description", ""),
            },
            "sub_scenario": {
                "name": sub_data.get("name", ""),
                "focus_areas": sub_data.get("focus_areas", []),
            },
            "complexity": complexity,
            "complexity_config": complexity_cfg,
            "use_case": use_case,
            "tables": tables_data,
            "er_analysis": er_data,
        }

        try:
            prompt = self._render_prompt(
                "generation/question_generation.j2", **template_data
            )
            result = self._llm_generate_json(prompt)
        except Exception as e:
            self.logger.warning(f"LLM 生成失败 ({complexity}/{use_case_name}): {e}")
            return None

        return self._to_question(
            result, main_data, sub_data, complexity, use_case_name
        )

    def _to_question(
        self,
        result: dict,
        main_data: dict,
        sub_data: dict,
        complexity: str,
        use_case_name: str,
    ) -> Optional[Question]:
        """把 LLM JSON 响应封装成 models.synthesis.Question"""
        q_data = result.get("generated_question", {}) or result
        text = (q_data.get("question_text") or q_data.get("text") or "").strip()
        if not text:
            return None

        # 表-列引用校验（用 kbase，不另存 mapping）
        tables_used = self._extract_tables_used(result)
        columns_used = self._extract_columns_used(result)
        if not self._validate_refs(tables_used, columns_used):
            self.logger.warning("表-列引用校验失败，丢弃该问题")
            return None

        level = _COMPLEXITY_TO_LEVEL.get(complexity, 1)
        metadata = GenerationMetadata(
            main_scenario=main_data.get("name", ""),
            sub_scenario=sub_data.get("name", ""),
            complexity_level=level,
            use_case=use_case_name,
        )

        return Question(
            question_id=f"q-{uuid.uuid4().hex[:12]}",
            text=text,
            question_focus=q_data.get("question_focus", ""),
            business_rules=self._extract_business_rules(q_data),
        )

    # ============================================================
    # 上下文构建（替代原 _prepare_*_from_jsonl，改读 kbase）
    # ============================================================

    def _build_tables_context(self, schema: SchemaMetadata) -> list[dict]:
        """聚合 K1/K4/K5 成 question_generation.j2 期望的 tables 结构"""
        tables: list[dict] = []
        for table in schema.tables:
            # K5 表描述
            desc = ""
            if self.kbase:
                ts = self.kbase.get_table_semantic(table.name)
                if ts:
                    desc = ts.description

            cols = []
            for col in table.columns:
                # K4 列描述
                col_desc = ""
                if self.kbase:
                    cs = self.kbase.get_column(table.name, col.name)
                    if cs:
                        col_desc = cs.description
                cols.append({
                    "name": col.name,
                    "type": col.data_type,
                    "comment": col_desc or (col.comment or ""),
                    "description": col_desc or (col.comment or ""),
                    "classification": {"category": self._classify_type(col.data_type)},
                    "full_reference": f"{table.name}.{col.name}",
                })
            tables.append({
                "name": table.name,
                "description": desc or (table.comment or ""),
                "columns": cols,
            })
        tables.sort(key=lambda t: t["name"])
        return tables

    def _build_er_context(self) -> dict:
        """从 K6 构建 ER 上下文（conceptual/logical/physical）"""
        er_data: dict[str, list] = {"physical": [], "logical": [], "conceptual": []}
        if not self.kbase:
            return er_data
        for rel in self.kbase.get_relations():
            # logical：实体间关系
            er_data["logical"].append({
                "from": rel.source_table,
                "to": rel.target_table,
                "relationship": rel.relationship_type,
            })
            # conceptual：关系语义
            if rel.reason:
                er_data["conceptual"].append({
                    "relation_name": f"{rel.source_table}→{rel.target_table}",
                    "business_meaning": rel.reason,
                    "complexity_level": "medium",
                })
        return er_data

    def _classify_type(self, data_type: str) -> str:
        """SQL 类型粗分类（模板里用）"""
        t = (data_type or "").lower()
        if "int" in t or "decimal" in t or "float" in t or "double" in t or "numeric" in t:
            return "numeric"
        if "date" in t or "time" in t:
            return "date"
        if "varchar" in t or "text" in t or "char" in t:
            return "text"
        return "other"

    # ============================================================
    # 校验（替代原 _validate_columns_strict）
    # ============================================================

    def _extract_tables_used(self, result: dict) -> list[str]:
        """提取使用的表名（兼容 str / dict 两种格式）"""
        ta = result.get("table_analysis", {}) or {}
        raw = result.get("tables_used") or ta.get("tables_used") or []
        out: list[str] = []
        for item in raw:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                name = item.get("table_name") or item.get("name") or ""
                if name:
                    out.append(name)
        return out

    def _extract_columns_used(self, result: dict) -> list[str]:
        ca = result.get("column_analysis", {}) or {}
        raw = result.get("columns_used") or ca.get("columns_used") or []
        out: list[str] = []
        for item in raw:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                ref = item.get("column_full_name") or item.get("name") or ""
                if ref:
                    out.append(ref)
        return out

    def _validate_refs(self, tables_used: list, columns_used: list) -> bool:
        """用 kbase.get_schema() 校验 table.column 引用都存在（防御非 str）"""
        schema = self.kbase.get_schema()
        # 表名校验
        all_tables = set(schema.all_table_names())
        for t in tables_used:
            if not isinstance(t, str) or not t:
                continue
            if t not in all_tables:
                self.logger.debug(f"表 {t} 不在 schema，校验失败")
                return False
        # 列引用校验（必须是 table.column）
        for ref in columns_used:
            if not isinstance(ref, str) or "." not in ref:
                continue
            tname, cname = ref.split(".", 1)
            if schema.get_column(tname, cname) is None:
                self.logger.debug(f"列 {ref} 不在 schema，校验失败")
                return False
        return True

    def _extract_business_rules(self, q_data: dict) -> list[dict]:
        """提取业务规则（Question.business_rules）"""
        rules = q_data.get("business_rules", [])
        if not isinstance(rules, list):
            return []
        out = []
        for r in rules:
            if isinstance(r, str):
                out.append({"rule": r})
            elif isinstance(r, dict):
                out.append(r)
        return out

    # ============================================================
    # YAML 加载
    # ============================================================

    def _load_yaml(self, filename: str) -> dict:
        path = self.config_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"配置文件不存在: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
