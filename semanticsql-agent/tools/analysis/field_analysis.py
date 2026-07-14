"""K3: Field Analysis Tool（tools/analysis/field_analysis.py）

基于 K1 schema，用 LLM 把每个字段分到 FieldCategory → 写入 K3。
K3 是论文 Fig.1（AVG(CDSCode)）反例的程序化检测基础：
identifier 不可聚合，measure 才可 SUM/AVG。

迁移自 tools/analysis_tools/field_analysis_tool.py：
- 保留逐字段 LLM 分类逻辑
- 改为依赖注入（BaseSemanticTool）
- 输入改读 kbase.get_schema()（K1），不再直接读 JSONL
- 输出改为 list[FieldClassification]，通过 kbase.set_field_types() 写入
- 删除 object.__setattr__、"请继续执行 X 工具" 指引字符串
"""

import logging
from typing import Optional

from tools.base_tool import BaseSemanticTool
from models.knowledge import (
    SchemaMetadata,
    FieldClassification,
    FieldCategory,
)


# 字符串 -> 枚举 映射（保留原 _parse_category 逻辑）
_CATEGORY_MAP = {c.value: c for c in FieldCategory}


class FieldAnalysisTool(BaseSemanticTool):
    """K3：字段类型分类

    用法：
        tool = FieldAnalysisTool(llm=llm_client, kbase=kbase, prompt_manager=pm)
        fields = tool.run()
        # 自动写入 kbase.set_field_types(fields)
    """

    def __init__(self, **kwargs):
        super().__init__(name="field_analysis_tool", **kwargs)

    def run(self, schema: SchemaMetadata = None) -> list[FieldClassification]:
        """逐字段分类 → 写入 K3 → 返回 list[FieldClassification]"""
        self.logger.info(f"🔧 {self.name}: 开始字段类型分析")

        if self.llm is None:
            raise RuntimeError(f"{self.name} 未注入 llm")

        # 1. 取 K1 schema
        if schema is None:
            if self.kbase is None:
                raise RuntimeError(f"{self.name} 未注入 kbase，无法读取 K1 schema")
            schema = self.kbase.get_schema()
        if not schema.tables:
            raise RuntimeError(f"{self.name}: K1 schema 为空，请先执行 schema_extraction")

        # 2. 逐字段 LLM 分类
        classifications: list[FieldClassification] = []
        for table in schema.tables:
            for col in table.columns:
                cls = self._classify_field(table.name, col)
                if cls is not None:
                    classifications.append(cls)

        # 3. 写入 K3
        if self.kbase:
            self.kbase.set_field_types(classifications)

        self.logger.info(f"✅ {self.name}: 分类完成 {len(classifications)} 个字段")
        return classifications

    # ============================================================
    # 逐字段 LLM 分类（保留原 _classify_field_with_llm 逻辑）
    # ============================================================

    def _classify_field(
        self, table_name: str, col
    ) -> Optional[FieldClassification]:
        """对单列做 LLM 分类"""
        try:
            # 从 K2 取领域信息，K4 取已有列描述（若已有）
            domain_type = ""
            domain_description = ""
            business_desc = ""
            if self.kbase:
                domain = self.kbase.get_domain()
                domain_type = domain.domain_type
                domain_description = domain.description
                # K4 可能在 K3 之前还没生成，先查一下
                col_sem = self.kbase.get_column(table_name, col.name)
                if col_sem:
                    business_desc = col_sem.description

            prompt = self._render_tool_prompt(
                "field_analysis",
                database_name=self.kbase.database_name if self.kbase else "unknown",
                table_name=table_name,
                field_name=f"{table_name}.{col.name}",
                data_type=col.data_type,
                sample_values=col.sample_values,
                entropy_level=col.entropy_level,
                is_primary=col.primary_key,
                is_foreign=col.foreign_key,
                is_nullable=col.nullable,
                domain_type=domain_type,
                domain_description=domain_description,
                business_desc=business_desc,
            )
            response = self._llm_generate_json(prompt)

            category_str = str(response.get("category", "other")).lower()
            category = _CATEGORY_MAP.get(category_str, FieldCategory.OTHER)
            reasoning = str(response.get("category_desc", "")).strip()

            return FieldClassification(
                table_name=table_name,
                column_name=col.name,
                category=category,
                confidence=0.8,
                reasoning=reasoning,
                data_type=col.data_type,
            )
        except Exception as e:
            self.logger.warning(f"字段 {table_name}.{col.name} 分类失败: {e}")
            return None
