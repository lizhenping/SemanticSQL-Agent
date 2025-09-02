"""
领域分析工具 - 分析数据库的业务领域
基于 LangChain BaseTool
"""

from typing import Dict, Any, Type, List, Union, Optional
import json
from pydantic import BaseModel, Field, field_validator
from langchain_openai import ChatOpenAI

from models.exceptions import ToolExecutionError
from prompts.manager import PromptManager
from .base_analysis_tool import BaseAnalysisTool, AnalysisToolInput


class DomainAnalysisInput(AnalysisToolInput):
    """领域分析输入"""

    input: Union[Dict[str, Any], str] = Field(
        default_factory=dict,
        description="输入参数（JSON字符串或字典，包含schema_info等）",
    )

    @field_validator("input", mode="before")
    @classmethod
    def parse_input_field(cls, v):
        """解析input字段的JSON字符串"""
        if isinstance(v, str):
            try:
                import json

                parsed = json.loads(v)
                if isinstance(parsed, dict):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass
        return v if v is not None else {}


class DomainAnalysisTool(BaseAnalysisTool):
    """业务领域分析工具 - 使用LLM驱动的分析"""

    name: str = "domain_analysis"
    description: str = "分析数据库的业务领域，识别主要业务场景和数据特征"
    args_schema: Type[BaseModel] = DomainAnalysisInput

    def __init__(self, llm: Optional[ChatOpenAI] = None, **kwargs):
        super().__init__(**kwargs)
        # 使用object.__setattr__避开Pydantic验证
        object.__setattr__(self, "prompt_manager", PromptManager())
        object.__setattr__(self, "llm", llm)  # 从Agent获取的LLM实例

    def _run(self, input: Union[Dict[str, Any], str] = None, **kwargs) -> str:
        """执行LLM驱动的领域分析"""
        try:
            # 获取schema_info数据
            schema_info = self._get_schema_info(input, kwargs)

            if not schema_info:
                raise ToolExecutionError(
                    tool_name=self.name,
                    reason="未找到数据库结构信息，请先执行schema_extraction",
                )

            # 步骤1: 简化和筛选数据
            core_tables = self._extract_core_tables(schema_info)

            # 步骤2: 准备统计信息
            stats = self._calculate_statistics(core_tables)

            # 步骤3: 使用LLM进行分析
            analysis_result = self._analyze_with_llm(schema_info, core_tables, stats)

            # 步骤4: 保存到memory
            self._save_to_memory(analysis_result)

            # 返回JSON字符串（LangChain要求）
            return json.dumps(analysis_result, ensure_ascii=False, indent=2)

        except Exception as e:
            raise ToolExecutionError(
                tool_name=self.name, reason=f"领域分析失败: {str(e)}"
            )

    def _get_schema_info(
        self, input_param: Union[Dict[str, Any], str], kwargs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """获取schema信息"""
        schema_info = {}

        # 方式1: 直接从input参数提取
        if input_param:
            schema_info = self.get_data_from_memory_or_param(input_param, "schema_info")

        # 方式2: 检查kwargs中是否有schema_info
        if not schema_info and "schema_info" in kwargs:
            schema_info = kwargs["schema_info"]

        # 方式3: 从memory获取
        if not schema_info and self._agent_memory:
            current_memory = self.get_current_memory()
            schema_info = self.get_analysis_from_memory(current_memory, "schema_info")

        return schema_info

    def _extract_core_tables(self, schema_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """提取核心表信息，参考pipeline设计"""
        tables = schema_info.get("tables", {})
        core_tables = []

        # 计算每个表的置信度分数
        scored_tables = []
        for table_name, table_info in tables.items():
            confidence = self._calculate_table_confidence(table_name, table_info)
            scored_tables.append((table_name, table_info, confidence))

        # 只选择置信度高的表（>= 0.7），最多7个（减少上下文长度）
        high_confidence_tables = [
            (name, info, conf) for name, info, conf in scored_tables if conf >= 0.7
        ]
        high_confidence_tables.sort(key=lambda x: x[2], reverse=True)

        for table_name, table_info, confidence in high_confidence_tables[:7]:  # 减少到7个表
            # 提取关键列（最多3个，进一步减少上下文）
            key_columns = self._extract_key_columns(
                table_info.get("columns", {}), table_info.get("primary_key", [])
            )

            simplified_table = {
                "name": table_name,
                "description": table_info.get("comment", "")[:50],  # 进一步限制描述长度
                "type": self._determine_business_type(table_name, table_info),
                "key_columns": key_columns[:3],  # 严格限制为3个关键列
                "confidence": confidence,
            }

            core_tables.append(simplified_table)

        return core_tables

    def _analyze_with_llm(
        self,
        schema_info: Dict[str, Any],
        core_tables: List[Dict[str, Any]],
        stats: Dict[str, Any],
    ) -> Dict[str, Any]:
        """使用LLM进行领域分析"""
        # 检查LLM实例是否可用
        if not self.llm:
            raise ToolExecutionError(
                tool_name=self.name, reason="LLM实例未提供，请确保Agent正确初始化了工具"
            )

        # 识别数据模式
        patterns = self._identify_data_patterns(core_tables)

        # 准备提示词参数
        prompt_params = {
            "database_name": schema_info.get("database_name", "unknown"),
            "total_tables": schema_info.get(
                "table_count", len(schema_info.get("tables", {}))
            ),
            "core_tables_count": len(core_tables),
            "core_tables": core_tables,
            "stats": stats,
            "patterns": patterns,
        }

        # 渲染提示词
        prompt = self.prompt_manager.get_analysis_prompt(
            "domain_analysis", **prompt_params
        )

        # 调用LLM进行分析
        llm_response = self.llm.invoke(prompt).content
        
        
        # 验证响应不为空
        if not llm_response or not llm_response.strip():
            raise ToolExecutionError(
                tool_name=self.name, 
                reason="LLM返回空响应，请检查LLM服务状态和提示词"
            )

        # 处理LLM响应中的thinking标签
        cleaned_response = llm_response.strip()
        
        # 移除<think>标签内容
        if "<think>" in cleaned_response:
            # 寻找JSON内容 - 通常在thinking之后
            if "}" in cleaned_response:
                # 寻找第一个{和最后一个}
                start_idx = cleaned_response.find("{")
                end_idx = cleaned_response.rfind("}") + 1
                if start_idx != -1 and end_idx > start_idx:
                    cleaned_response = cleaned_response[start_idx:end_idx]
                    pass

        # 解析JSON响应
        try:
            analysis_result = json.loads(cleaned_response)
            return analysis_result
        except json.JSONDecodeError as e:
            raise ToolExecutionError(
                tool_name=self.name,
                reason=f"LLM返回非JSON格式响应，解析失败: {str(e)}. 清理后内容: {cleaned_response[:500]}"
            )


    def _calculate_statistics(
        self, core_tables: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """计算核心表的统计信息，参考pipeline字段统计逻辑"""
        stats = {
            "entity_tables": 0,
            "relation_tables": 0,
            "config_tables": 0,
            "log_tables": 0,
            "total_key_columns": 0,
            "avg_key_columns": 0,
            # 参考pipeline增加的字段模式统计
            "field_patterns": {
                "id_fields": 0,
                "date_fields": 0,
                "status_fields": 0,
                "amount_fields": 0,
                "count_fields": 0,
            },
            "pattern_examples": {
                "id_fields": [],
                "date_fields": [],
                "status_fields": [],
                "amount_fields": [],
                "count_fields": [],
            },
        }

        if not core_tables:
            return stats

        total_key_columns = 0

        # 遍历所有核心表
        for table in core_tables:
            # 表类型统计
            table_type = table.get("type", "unknown")
            if table_type == "entity_table":
                stats["entity_tables"] += 1
            elif table_type == "relation_table":
                stats["relation_tables"] += 1
            elif table_type == "config_table":
                stats["config_tables"] += 1
            elif table_type == "log_table":
                stats["log_tables"] += 1

            # 关键字段统计
            key_columns = table.get("key_columns", [])
            total_key_columns += len(key_columns)

            # 字段模式分析（参考pipeline逻辑）
            table_name = table.get("name", "")
            for col_name in key_columns:
                self._update_field_pattern_stats(stats, table_name, col_name)

        # 计算平均值
        stats["total_key_columns"] = total_key_columns
        stats["avg_key_columns"] = (
            total_key_columns / len(core_tables) if core_tables else 0
        )

        return stats

    def _update_field_pattern_stats(
        self, stats: Dict[str, Any], table_name: str, col_name: str
    ):
        """更新字段模式统计，参考pipeline的_update_pattern_stats逻辑"""
        col_name_lower = col_name.lower()
        field_key = f"{table_name}.{col_name}"

        # ID字段 - 参考pipeline逻辑
        if col_name_lower.endswith("_id") or col_name_lower == "id":
            stats["field_patterns"]["id_fields"] += 1
            if len(stats["pattern_examples"]["id_fields"]) < 3:
                stats["pattern_examples"]["id_fields"].append(field_key)

        # 日期时间字段
        elif any(kw in col_name_lower for kw in ["date", "time", "created", "updated"]):
            stats["field_patterns"]["date_fields"] += 1
            if len(stats["pattern_examples"]["date_fields"]) < 3:
                stats["pattern_examples"]["date_fields"].append(field_key)

        # 状态字段
        elif any(kw in col_name_lower for kw in ["status", "state", "type"]):
            stats["field_patterns"]["status_fields"] += 1
            if len(stats["pattern_examples"]["status_fields"]) < 3:
                stats["pattern_examples"]["status_fields"].append(field_key)

        # 金额字段
        elif any(kw in col_name_lower for kw in ["amount", "price", "cost", "fee"]):
            stats["field_patterns"]["amount_fields"] += 1
            if len(stats["pattern_examples"]["amount_fields"]) < 3:
                stats["pattern_examples"]["amount_fields"].append(field_key)

        # 计数字段
        elif any(kw in col_name_lower for kw in ["count", "num", "qty", "quantity"]):
            stats["field_patterns"]["count_fields"] += 1
            if len(stats["pattern_examples"]["count_fields"]) < 3:
                stats["pattern_examples"]["count_fields"].append(field_key)

    def _identify_data_patterns(self, core_tables: List[Dict[str, Any]]) -> List[str]:
        """识别数据模式"""
        patterns = []

        # 检查时间戳模式
        has_timestamps = any(
            any(
                "time" in col.lower()
                or "date" in col.lower()
                or "created" in col.lower()
                for col in table.get("key_columns", [])
            )
            for table in core_tables
        )
        if has_timestamps:
            patterns.append("时间戳审计模式")

        # 检查软删除模式
        has_soft_delete = any(
            any(
                "deleted" in col.lower() or "is_delete" in col.lower()
                for col in table.get("key_columns", [])
            )
            for table in core_tables
        )
        if has_soft_delete:
            patterns.append("软删除模式")

        # 检查版本控制模式
        has_versioning = any(
            any("version" in col.lower() for col in table.get("key_columns", []))
            for table in core_tables
        )
        if has_versioning:
            patterns.append("版本控制模式")

        # 检查关系表模式
        relation_tables = [t for t in core_tables if t.get("type") == "relation_table"]
        if len(relation_tables) > 0:
            patterns.append("关系表模式")

        return patterns

    def _save_to_memory(self, analysis_result: Dict[str, Any]):
        """保存分析结果到memory"""
        if self._agent_memory:
            try:
                self._agent_memory.save_context(
                    inputs={"tool_name": "domain_analysis"}, outputs=analysis_result
                )
            except Exception as e:
                logger.warning(f"Failed to save domain analysis to memory: {e}")

    def _calculate_table_confidence(
        self, table_name: str, table_info: Dict[str, Any]
    ) -> float:
        """计算表的置信度分数（参考pipeline设计）"""
        confidence = 0.0

        # 基础分数：有主键
        if table_info.get("primary_key"):
            confidence += 0.3

        # 有注释说明
        if table_info.get("comment"):
            confidence += 0.2

        # 有数据记录
        if table_info.get("row_count", 0) > 0:
            confidence += 0.1

        # 表名符合业务命名规范
        if self._has_business_naming(table_name):
            confidence += 0.2

        # 列数量合理（3-50列）
        column_count = len(table_info.get("columns", {}))
        if 3 <= column_count <= 50:
            confidence += 0.1

        # 有关键业务字段
        columns = table_info.get("columns", {})
        if self._has_key_business_fields(columns):
            confidence += 0.1

        return min(confidence, 1.0)  # 最大置信度为1.0

    def _extract_key_columns(
        self, columns: Dict[str, Any], primary_keys: List[str]
    ) -> List[str]:
        """提取关键列名（参考pipeline设计）"""
        key_columns = []

        # 优先添加主键
        for pk in primary_keys:
            if pk in columns:
                key_columns.append(pk)

        # 添加其他重要列
        for col_name, col_info in columns.items():
            if col_name not in key_columns and len(key_columns) < 5:
                col_lower = col_name.lower()

                # ID列
                if "id" in col_lower:
                    key_columns.append(col_name)
                # 名称列
                elif any(keyword in col_lower for keyword in ["name", "title"]):
                    key_columns.append(col_name)
                # 时间列
                elif any(
                    keyword in col_lower
                    for keyword in ["time", "date", "created", "updated"]
                ):
                    key_columns.append(col_name)
                # 状态列
                elif any(
                    keyword in col_lower for keyword in ["status", "state", "type"]
                ):
                    key_columns.append(col_name)

        return key_columns[:5]  # 严格限制为5个

    def _has_business_naming(self, table_name: str) -> bool:
        """检查表名是否符合业务命名规范"""
        business_keywords = [
            "user",
            "order",
            "product",
            "customer",
            "contract",
            "equipment",
            "info",
            "data",
            "config",
            "log",
        ]
        table_lower = table_name.lower()
        return any(keyword in table_lower for keyword in business_keywords)

    def _has_key_business_fields(self, columns: Dict[str, Any]) -> bool:
        """检查是否有关键业务字段"""
        key_fields = [
            "id",
            "name",
            "status",
            "type",
            "time",
            "date",
            "created",
            "updated",
        ]
        for col_name in columns.keys():
            col_lower = col_name.lower()
            if any(keyword in col_lower for keyword in key_fields):
                return True
        return False

    def _determine_business_type(
        self, table_name: str, table_info: Dict[str, Any]
    ) -> str:
        """确定业务表类型（参考pipeline设计）"""
        table_lower = table_name.lower()

        # 配置表
        if any(keyword in table_lower for keyword in ["config", "setting", "param"]):
            return "config_table"

        # 日志表
        if any(keyword in table_lower for keyword in ["log", "history", "audit"]):
            return "log_table"

        # 关系表（通常包含多个外键）
        columns = table_info.get("columns", {})
        id_count = sum(1 for col in columns.keys() if "id" in col.lower())
        if id_count >= 2:
            return "relation_table"

        # 默认为实体表
        return "entity_table"

    def _identify_business_entities(self, tables: Dict[str, Any]) -> Dict[str, Any]:
        """识别业务实体（适配简化数据结构）"""
        entities = {}

        for table_name, table_info in tables.items():
            # 跳过明显的系统表
            if any(
                prefix in table_name.lower() for prefix in ["sys_", "log_", "temp_"]
            ):
                continue

            entity_info = {
                "table_name": table_name,
                "description": table_info.get("description", ""),
                "key_fields": table_info.get("key_columns", [])[:3],  # 最多3个关键字段
                "entity_type": table_info.get("type", "unknown"),
                "confidence": table_info.get("confidence", 0.0),
            }

            # 根据表类型和名称进一步细化实体类型
            table_lower = table_name.lower()
            if "user" in table_lower or "customer" in table_lower:
                entity_info["business_category"] = "person"
            elif "product" in table_lower or "item" in table_lower:
                entity_info["business_category"] = "product"
            elif "order" in table_lower or "transaction" in table_lower:
                entity_info["business_category"] = "transaction"
            elif "config" in table_lower or "setting" in table_lower:
                entity_info["business_category"] = "configuration"
            else:
                entity_info["business_category"] = "business_object"

            entities[table_name] = entity_info

        return entities

    def _identify_business_processes(
        self, tables: Dict[str, Any], entities: Dict[str, Any]
    ) -> Dict[str, Any]:
        """识别业务流程（适配简化数据结构）"""
        processes = {"核心流程": [], "支撑流程": [], "管理流程": []}

        for table_name, table_info in tables.items():
            table_type = table_info.get("type", "unknown")
            confidence = table_info.get("confidence", 0.0)
            description = table_info.get("description", "")

            process_info = {
                "table": table_name,
                "type": table_type,
                "confidence": confidence,
                "description": description,
                "key_columns": table_info.get("key_columns", [])[:3],
            }

            # 根据表类型和名称分类业务流程
            table_lower = table_name.lower()

            # 核心业务流程表
            if table_type == "entity_table" and any(
                process in table_lower
                for process in ["order", "payment", "transaction", "booking", "sale"]
            ):
                process_info["process_category"] = "transaction"
                processes["核心流程"].append(process_info)

            # 支撑流程表
            elif table_type == "entity_table" and any(
                support in table_lower
                for support in ["user", "product", "inventory", "customer", "item"]
            ):
                process_info["process_category"] = "support"
                processes["支撑流程"].append(process_info)

            # 管理流程表
            elif table_type in ["config_table", "log_table"] or any(
                mgmt in table_lower
                for mgmt in ["config", "setting", "log", "audit", "permission", "admin"]
            ):
                process_info["process_category"] = "management"
                processes["管理流程"].append(process_info)

            # 其他高置信度表归入支撑流程
            elif confidence >= 0.7:
                process_info["process_category"] = "support"
                processes["支撑流程"].append(process_info)

        return processes

    async def _arun(self, input: Union[Dict[str, Any], str] = None, **kwargs) -> str:
        """异步执行（当前实现为同步）"""
        return self._run(input, **kwargs)
