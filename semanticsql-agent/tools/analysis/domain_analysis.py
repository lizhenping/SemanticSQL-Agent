"""K2: Domain Analysis Tool（tools/analysis/domain_analysis.py）

基于 K1 schema，用 LLM 识别业务领域类型/概念/命名规范 → 写入 K2。

迁移自 tools/analysis_tools/domain_analysis_tool.py：
- 保留核心 LLM 分析逻辑（六维业务分析 + 置信度计算）
- 改为依赖注入（BaseSemanticTool），不再内部 create_llm()
- 输入改读 kbase.get_schema()（K1），不再直接读 JSONL
- 输出改为 models.knowledge.DomainKnowledge，通过 kbase.set_domain() 写入
- 删除 object.__setattr__、"请继续执行 X 工具" 指引字符串
"""

import logging
from typing import Any

from tools.base_tool import BaseSemanticTool
from models.knowledge import DomainKnowledge, SchemaMetadata


class DomainAnalysisTool(BaseSemanticTool):
    """K2：业务领域分析

    用法：
        tool = DomainAnalysisTool(llm=llm_client, kbase=kbase, prompt_manager=pm)
        domain = tool.run()
        # 自动写入 kbase.set_domain(domain)
    """

    def __init__(self, **kwargs):
        super().__init__(name="domain_analysis_tool", **kwargs)

    def run(self, schema: SchemaMetadata = None) -> DomainKnowledge:
        """分析领域 → 写入 K2 → 返回 DomainKnowledge

        Args:
            schema: 可选，K1 schema；不传则从 kbase.get_schema() 读取
        """
        self.logger.info(f"🔧 {self.name}: 开始业务领域分析")

        # 1. 取 K1 schema（优先用参数，否则从 kbase 读）
        if schema is None:
            if self.kbase is None:
                raise RuntimeError(f"{self.name} 未注入 kbase，无法读取 K1 schema")
            schema = self.kbase.get_schema()
        if not schema.tables:
            raise RuntimeError(f"{self.name}: K1 schema 为空，请先执行 schema_extraction")

        # 2. 格式化为 DDL 供 LLM 分析
        ddl_content = self._format_schema_to_ddl(schema)

        # 3. LLM 六维业务分析
        domain = self._analyze_domain_with_llm(ddl_content)

        # 4. 写入 K2
        if self.kbase:
            self.kbase.set_domain(domain)

        self.logger.info(f"✅ {self.name}: 识别领域 {domain.domain_type}")
        return domain

    # ============================================================
    # DDL 格式化（保留原 _format_schema_to_ddl 核心逻辑）
    # ============================================================

    def _format_schema_to_ddl(self, schema: SchemaMetadata) -> str:
        """把 SchemaMetadata 格式化为 CREATE TABLE DDL 串"""
        ddl_lines = []
        for table in schema.tables:
            if not table.columns:
                continue
            ddl_lines.append(f"CREATE TABLE `{table.name}` (")

            column_defs = []
            primary_keys = []
            for col in table.columns:
                col_def = f"  `{col.name}` {col.data_type or 'VARCHAR(255)'}"
                if not col.nullable:
                    col_def += " NOT NULL"
                if col.comment:
                    col_def += f" COMMENT '{col.comment}'"
                column_defs.append(col_def)
                if col.primary_key:
                    primary_keys.append(col.name)

            if primary_keys:
                column_defs.append(f"  PRIMARY KEY (`{'`, `'.join(primary_keys)}`)")

            ddl_lines.append(",\n".join(column_defs))
            ddl_lines.append(");")
            ddl_lines.append("")

        ddl = "\n".join(ddl_lines)
        # 超长 DDL 截断（避免超出 LLM token 上限）
        if len(ddl) > 60000:
            ddl = self._optimize_ddl_for_llm(ddl)
        return ddl

    def _optimize_ddl_for_llm(self, ddl_content: str) -> str:
        """DDL 过长时只保留重要行"""
        keep_keywords = (
            "create table", "primary key", "foreign key",
            "not null", "unique", "id", "name", "status",
        )
        important = [
            line for line in ddl_content.split("\n")
            if line.strip() and any(k in line.lower() for k in keep_keywords)
        ]
        return "\n".join(important)

    # ============================================================
    # LLM 分析（保留原 _analyze_domain_with_llm 逻辑）
    # ============================================================

    def _analyze_domain_with_llm(self, ddl_content: str) -> DomainKnowledge:
        """用 LLM 做六维业务分析"""
        if self.llm is None:
            raise RuntimeError(f"{self.name} 未注入 llm")

        # 1. 渲染提示词（analysis/domain_analysis.j2）
        prompt = self._render_prompt("analysis/domain_analysis.j2", schema_ddl=ddl_content)

        # 2. 调 LLM
        response = self._llm_generate_json(prompt)

        # 3. 校验 + 构造 DomainKnowledge
        validated = self._validate_response(response)
        confidence = self._calculate_confidence(validated)

        return DomainKnowledge(
            domain_type=validated.get("domain_type", "未知领域"),
            description="; ".join(validated.get("business_rules", [])[:2]),
            business_concepts=validated.get("key_entities", []),
            naming_patterns=validated.get("special_fields", []),
        )

    def _validate_response(self, data: dict) -> dict:
        """校验 LLM 返回的六维字段结构"""
        required = (
            "domain_type",
            "business_problems",
            "solution_approaches",
            "key_entities",
            "business_rules",
            "special_fields",
        )
        validated: dict[str, Any] = {}
        for field in required:
            if field not in data:
                validated[field] = "" if field == "domain_type" else []
                continue
            if field == "domain_type":
                validated[field] = str(data[field]).strip()
            else:
                value = data[field]
                if isinstance(value, list):
                    validated[field] = [
                        str(item).strip() for item in value
                        if item and str(item).strip()
                    ]
                else:
                    validated[field] = []
        return validated

    def _calculate_confidence(self, data: dict) -> float:
        """按六维完整度计算置信度（0~1）"""
        score = 0.0
        if len(data.get("domain_type", "")) > 3:
            score += 0.2
        if len(data.get("business_problems", [])) >= 2:
            score += 0.2
        if len(data.get("solution_approaches", [])) >= 2:
            score += 0.2
        if len(data.get("key_entities", [])) >= 2:
            score += 0.2
        if len(data.get("business_rules", [])) >= 3:
            score += 0.2
        return min(score * 1.2, 1.0)
