"""
领域分析工具 - 分析数据库的业务领域
基于 LangChain BaseTool
"""

from typing import Dict, Any, Type, List, Union
import json
from pydantic import BaseModel, Field, field_validator

from models.exceptions import ToolExecutionError
from prompts.manager import PromptManager
from utils.llm_client import LLMClient
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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 使用object.__setattr__避开Pydantic验证
        object.__setattr__(self, "prompt_manager", PromptManager())
        object.__setattr__(self, "llm_client", None)  # 将在运行时从agent获取

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

        # 只选择置信度高的表（>= 0.7），最多10个
        high_confidence_tables = [
            (name, info, conf) for name, info, conf in scored_tables if conf >= 0.7
        ]
        high_confidence_tables.sort(key=lambda x: x[2], reverse=True)

        for table_name, table_info, confidence in high_confidence_tables[:10]:
            # 提取关键列（最多5个）
            key_columns = self._extract_key_columns(
                table_info.get("columns", {}), table_info.get("primary_key", [])
            )

            simplified_table = {
                "name": table_name,
                "description": table_info.get("comment", "")[:100],  # 限制描述长度
                "type": self._determine_business_type(table_name, table_info),
                "key_columns": key_columns[:5],  # 严格限制为5个关键列
                "confidence": confidence,
                "row_count": table_info.get("row_count", 0),
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
        # 获取LLM客户端（从agent上下文获取）
        if not self.llm_client:
            self.llm_client = self._get_llm_client()

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
        try:
            prompt = self.prompt_manager.get_analysis_prompt(
                "domain_analysis", **prompt_params
            )
        except Exception as e:
            print(f"Warning: 提示词渲染失败，使用默认分析: {e}")
            return self._fallback_analysis(core_tables, stats)

        # 调用LLM进行分析
        try:
            llm_response = self.llm_client.generate(prompt)

            # 尝试解析JSON响应
            try:
                analysis_result = json.loads(llm_response)
                return analysis_result
            except json.JSONDecodeError:
                print(f"Warning: LLM返回非JSON格式，使用后备分析")
                return self._fallback_analysis(core_tables, stats)

        except Exception as e:
            print(f"Warning: LLM调用失败，使用后备分析: {e}")
            return self._fallback_analysis(core_tables, stats)

    def _get_llm_client(self) -> LLMClient:
        """获取LLM客户端"""
        try:
            # 尝试从agent内存或配置获取LLM客户端
            from config.settings import get_settings

            settings = get_settings()
            return LLMClient(
                model=settings.llm_model,
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key,
            )
        except Exception as e:
            print(f"Warning: 无法获取LLM客户端: {e}")
            raise ToolExecutionError(
                tool_name=self.name, reason="无法获取LLM服务，请检查配置"
            )

    def _fallback_analysis(
        self, core_tables: List[Dict[str, Any]], stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """后备分析方法（基于统计）"""
        # 使用统计信息生成基本分析结果
        return {
            "primary_domain": "未知领域",
            "domain_confidence": 0.5,
            "sub_domains": [],
            "business_entities": {
                t["name"]: {"entity_type": t["type"], "confidence": t["confidence"]}
                for t in core_tables
            },
            "business_processes": [],
            "data_characteristics": {
                "scale": "medium" if len(core_tables) > 5 else "small",
                "complexity": (
                    "moderate" if stats.get("total_key_columns", 0) > 15 else "simple"
                ),
                "time_sensitivity": any(
                    "time" in str(t.get("key_columns", [])).lower() for t in core_tables
                ),
                "entity_rich": stats.get("entity_tables", 0)
                > stats.get("config_tables", 0),
            },
            "recommendations": [
                "基于表结构特征生成适合的查询类型",
                "关注核心业务表的关联查询",
            ],
        }

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
                print(f"Warning: Failed to save domain analysis to memory: {e}")

    def _calculate_table_confidence(
        self, table_name: str, table_info: Dict[str, Any]
    ) -> float:
        """计算表的置信度分数（参考pipeline设计）"""
        confidence = 0.0

        # 基础分数：有主键
        if table_info.get("primary_keys"):
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

    # 以下方法已被LLM分析替代，保留用作fallback
    def _analyze_domain_patterns_legacy(
        self, tables: Dict[str, Any]
    ) -> Dict[str, float]:
        """分析领域模式（适配简化数据结构）"""
        domain_patterns = {
            "电商": [
                "product",
                "order",
                "cart",
                "payment",
                "customer",
                "inventory",
                "shop",
            ],
            "金融": [
                "account",
                "transaction",
                "balance",
                "payment",
                "invoice",
                "credit",
                "loan",
            ],
            "社交": ["user", "friend", "post", "comment", "like", "follow", "message"],
            "教育": [
                "student",
                "teacher",
                "course",
                "class",
                "exam",
                "score",
                "enrollment",
            ],
            "医疗": [
                "patient",
                "doctor",
                "appointment",
                "prescription",
                "diagnosis",
                "treatment",
            ],
            "物流": [
                "shipment",
                "delivery",
                "warehouse",
                "tracking",
                "carrier",
                "route",
            ],
            "人力资源": [
                "employee",
                "department",
                "salary",
                "attendance",
                "leave",
                "recruitment",
            ],
            "CRM": ["customer", "lead", "opportunity", "contact", "campaign", "deal"],
            "库存管理": [
                "inventory",
                "stock",
                "warehouse",
                "supplier",
                "purchase",
                "material",
            ],
            "内容管理": [
                "article",
                "page",
                "category",
                "tag",
                "media",
                "content",
                "publish",
            ],
        }

        domain_scores = {}
        table_names = [name.lower() for name in tables.keys()]
        all_columns = []

        # 收集所有列名（适配简化数据结构）
        for table_info in tables.values():
            key_columns = table_info.get("key_columns", [])
            all_columns.extend([col.lower() for col in key_columns])

        # 计算每个领域的匹配分数
        for domain, keywords in domain_patterns.items():
            score = 0.0
            matched_keywords = 0

            for keyword in keywords:
                # 检查表名
                table_matches = sum(1 for t in table_names if keyword in t)
                # 检查列名
                column_matches = sum(1 for c in all_columns if keyword in c)
                # 检查表描述
                description_matches = sum(
                    1
                    for table_info in tables.values()
                    if keyword in table_info.get("description", "").lower()
                )

                if table_matches > 0 or column_matches > 0 or description_matches > 0:
                    matched_keywords += 1
                    score += (
                        table_matches * 2 + column_matches + description_matches
                    )  # 表名权重更高

            if matched_keywords > 0:
                # 归一化分数
                domain_scores[domain] = score / (len(keywords) * len(tables))

        return domain_scores

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

    def _analyze_data_characteristics(self, tables: Dict[str, Any]) -> Dict[str, Any]:
        """分析数据特征（适配简化数据结构）"""
        characteristics = {
            "total_tables": len(tables),
            "total_key_columns": 0,
            "avg_key_columns_per_table": 0,
            "has_timestamps": False,
            "has_soft_delete": False,
            "has_versioning": False,
            "common_patterns": [],
            "table_types": {},
            "confidence_distribution": {},
        }

        total_key_columns = 0
        timestamp_tables = 0
        soft_delete_tables = 0
        version_tables = 0
        table_types = {}
        confidence_ranges = {"high": 0, "medium": 0, "low": 0}

        for table_info in tables.values():
            key_columns = table_info.get("key_columns", [])
            total_key_columns += len(key_columns)

            # 统计表类型
            table_type = table_info.get("type", "unknown")
            table_types[table_type] = table_types.get(table_type, 0) + 1

            # 统计置信度分布
            confidence = table_info.get("confidence", 0.0)
            if confidence >= 0.8:
                confidence_ranges["high"] += 1
            elif confidence >= 0.5:
                confidence_ranges["medium"] += 1
            else:
                confidence_ranges["low"] += 1

            # 检查关键列名模式
            column_names = [col.lower() for col in key_columns]

            # 检查时间戳
            if any(
                "created" in col or "updated" in col or "time" in col
                for col in column_names
            ):
                timestamp_tables += 1

            # 检查软删除
            if any(
                any(pattern in col for pattern in ["deleted", "delete"])
                for col in column_names
            ):
                soft_delete_tables += 1

            # 检查版本控制
            if any("version" in col for col in column_names):
                version_tables += 1

        characteristics["total_key_columns"] = total_key_columns
        characteristics["avg_key_columns_per_table"] = (
            total_key_columns / len(tables) if tables else 0
        )
        characteristics["has_timestamps"] = timestamp_tables > len(tables) * 0.5
        characteristics["has_soft_delete"] = soft_delete_tables > 0
        characteristics["has_versioning"] = version_tables > 0
        characteristics["table_types"] = table_types
        characteristics["confidence_distribution"] = confidence_ranges

        # 识别常见模式
        if characteristics["has_timestamps"]:
            characteristics["common_patterns"].append("时间戳审计")
        if characteristics["has_soft_delete"]:
            characteristics["common_patterns"].append("软删除")
        if characteristics["has_versioning"]:
            characteristics["common_patterns"].append("版本控制")
        if table_types.get("entity_table", 0) > table_types.get("config_table", 0):
            characteristics["common_patterns"].append("实体驱动设计")

        return characteristics

    def _generate_domain_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """生成领域相关建议（适配简化数据结构）"""
        recommendations = []

        domain = analysis.get("primary_domain", "")
        entities = analysis.get("business_entities", {})
        processes = analysis.get("business_processes", {})
        characteristics = analysis.get("data_characteristics", {})

        # 基于领域的建议
        if domain == "电商":
            recommendations.append("关注订单、商品、库存相关的查询")
            recommendations.append("考虑销售统计、库存预警等场景")
        elif domain == "金融":
            recommendations.append("重点关注交易、账户余额相关查询")
            recommendations.append("注意数据精度和事务一致性")
        elif domain == "社交":
            recommendations.append("关注用户关系、内容互动相关查询")
            recommendations.append("考虑社交网络分析和推荐算法")
        elif domain == "教育":
            recommendations.append("关注学生成绩、课程安排相关查询")
            recommendations.append("考虑教学质量分析和学习进度跟踪")

        # 基于实体分析的建议
        total_entities = len(entities)
        high_confidence_entities = sum(
            1 for e in entities.values() if e.get("confidence", 0) >= 0.8
        )

        if total_entities > 8:
            recommendations.append("系统较复杂，建议分模块生成查询")
        elif total_entities < 3:
            recommendations.append("系统结构简单，适合生成基础查询")

        if (
            high_confidence_entities / total_entities > 0.7
            if total_entities > 0
            else False
        ):
            recommendations.append("表结构清晰，可以生成复杂的关联查询")

        # 检查特定实体类型
        entity_categories = [e.get("business_category", "") for e in entities.values()]
        if "transaction" in entity_categories:
            recommendations.append("可以生成交易流程跟踪的查询")
        if "person" in entity_categories:
            recommendations.append("可以生成用户行为分析的查询")
        if "product" in entity_categories:
            recommendations.append("可以生成商品统计分析的查询")

        # 基于流程的建议
        core_processes = processes.get("核心流程", [])
        support_processes = processes.get("支撑流程", [])
        mgmt_processes = processes.get("管理流程", [])

        if len(core_processes) > 0:
            recommendations.append("存在核心业务流程，可生成业务流程分析查询")
        if len(mgmt_processes) > 0:
            recommendations.append("包含管理功能，可生成系统监控和配置查询")
        if len(support_processes) > len(core_processes):
            recommendations.append("支撑数据丰富，适合生成多维度分析查询")

        # 基于数据特征的建议
        if characteristics.get("has_timestamps", False):
            recommendations.append("支持时间维度分析，可生成趋势和历史查询")
        if characteristics.get("has_soft_delete", False):
            recommendations.append("使用软删除，可生成数据恢复和审计查询")
        if characteristics.get("has_versioning", False):
            recommendations.append("支持版本控制，可生成版本对比查询")

        confidence_dist = characteristics.get("confidence_distribution", {})
        if confidence_dist.get("high", 0) > confidence_dist.get("low", 0):
            recommendations.append("数据质量较高，适合生成复杂的分析查询")

        return recommendations

    async def _arun(self, input: Union[Dict[str, Any], str] = None, **kwargs) -> str:
        """异步执行（当前实现为同步）"""
        return self._run(input, **kwargs)
