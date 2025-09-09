"""
表语义分析工具 - 极简架构重构版本
基于新的BaseSemanticSQLTool，实现完全自主的表语义分析
"""

from typing import Dict, Any, List, Optional
import json
import re

from tools.base_tool import BaseSemanticSQLTool
from models.schemas import PredicateType, EntityType
from models.exceptions import raise_tool_error, raise_dependency_error


class TableAnalysisTool(BaseSemanticSQLTool):
    """表语义分析工具 - 极简重构版本
    
    职责：
    - 基于数据库结构和列语义进行表语义分析
    - 识别表的业务实体类型和职责
    - 分析表间关系和业务依赖
    - 为后续工具提供表语义上下文
    
    设计原则：
    - 依赖记忆：基于schema_extraction和column_analysis工具的结果
    - 智能推断：结合表结构特征和业务领域知识
    - 三元组输出：结构化表语义关系
    """
    
    name: str = "table_analysis"
    description: str = "分析数据库表语义，识别实体类型、业务职责和表间关系"
    
    def __init__(self, **kwargs):
        """初始化表分析工具"""
        super().__init__(**kwargs)
        # 使用object.__setattr__避免Pydantic验证问题
        object.__setattr__(self, 'entity_patterns', self._init_entity_patterns())
    
    def _run(self, *args, **kwargs) -> str:
        """执行工具分析"""
        # 提取输入文本
        input_text = args[0] if args else kwargs.get('input', '')
        # 1. 清空上次执行的三元组
        self._clear_generated_triples()
        self._log_execution_start(input_text)
        
        try:
            # 2. 检查依赖：需要schema_extraction和column_analysis工具的结果
            self._check_dependencies(["schema_extraction", "column_analysis"])
            
            # 3. 获取依赖分析结果
            analysis_context = self._gather_analysis_context()
            
            # 4. 分析表语义
            table_analysis = self._analyze_tables_semantics(analysis_context)
            
            # 5. 生成表语义三元组
            self._generate_table_triples(table_analysis, analysis_context)
            
            # 6. 持久化三元组到记忆系统
            self._persist_triples()
            
            # 7. 构建执行结果
            result_message = self._build_result_message(table_analysis)
            
            self._log_execution_end(f"分析了 {table_analysis['total_tables']} 个表")
            return result_message
            
        except Exception as e:
            error_msg = f"表语义分析失败: {str(e)}"
            self.logger.error(f"❌ {self.name}: {error_msg}")
            return f"❌ {error_msg}"
    
    # ========== 核心业务逻辑 ==========
    def _gather_analysis_context(self) -> Dict[str, Any]:
        """收集分析上下文"""
        # 获取基础结构信息
        schema_memory = self.get_memory_by_source_tool("schema_extraction")
        schema_info = self._extract_schema_info(schema_memory)
        
        # 获取列语义分析结果
        column_memory = self.get_memory_by_source_tool("column_analysis")
        column_semantics = self._extract_column_semantics(column_memory)
        
        # 尝试获取领域信息（可选）
        domain_memory = self.get_memory_by_source_tool("domain_analysis")
        domain_info = self._extract_domain_info(domain_memory) if domain_memory else {"primary_domain": "通用业务"}
        
        return {
            "schema_info": schema_info,
            "column_semantics": column_semantics,
            "domain_info": domain_info
        }
    
    def _extract_schema_info(self, schema_memory: List[Dict[str, Any]]) -> Dict[str, Any]:
        """从记忆中提取结构信息"""
        if not schema_memory:
            raise_dependency_error(self.name, "schema_extraction", "数据库结构信息")
        
        # 从三元组中重建结构信息
        tables = set()
        table_columns = {}
        column_details = {}
        foreign_keys = {}
        database_name = "unknown"
        
        for triple in schema_memory:
            subject = triple.get("subject", "")
            predicate = triple.get("predicate", "")
            obj = triple.get("object", "")
            
            if predicate == PredicateType.HAS_TABLE.value:
                database_name = subject
                tables.add(obj)
            elif predicate == PredicateType.HAS_COLUMN.value:
                table_name = subject
                column_name = obj
                if table_name not in table_columns:
                    table_columns[table_name] = []
                table_columns[table_name].append(column_name)
            elif predicate == PredicateType.REFERENCES.value:
                # 外键关系：source -> target
                if "." in subject and "." in obj:
                    source_table, source_col = subject.split(".", 1)
                    target_table, target_col = obj.split(".", 1)
                    if source_table not in foreign_keys:
                        foreign_keys[source_table] = []
                    foreign_keys[source_table].append({
                        "source_column": source_col,
                        "target_table": target_table,
                        "target_column": target_col
                    })
            elif predicate == "is_primary_key" and obj == "true":
                if subject not in column_details:
                    column_details[subject] = {}
                column_details[subject]["is_primary_key"] = True
        
        return {
            "database_name": database_name,
            "tables": list(tables),
            "table_columns": table_columns,
            "column_details": column_details,
            "foreign_keys": foreign_keys
        }
    
    def _extract_column_semantics(self, column_memory: List[Dict[str, Any]]) -> Dict[str, Any]:
        """从记忆中提取列语义信息"""
        column_enhanced_meanings = {}
        column_entities = {}
        semantic_groups = {}
        
        for triple in column_memory:
            subject = triple.get("subject", "")
            predicate = triple.get("predicate", "")
            obj = triple.get("object", "")
            
            if predicate == "has_enhanced_meaning":
                column_enhanced_meanings[subject] = obj
            elif predicate == "belongs_to_entity":
                column_entities[subject] = obj
            elif predicate == "contains_column":
                # semantic_group contains column
                semantic_type = subject
                column = obj
                if semantic_type not in semantic_groups:
                    semantic_groups[semantic_type] = []
                semantic_groups[semantic_type].append(column)
        
        return {
            "column_enhanced_meanings": column_enhanced_meanings,
            "column_entities": column_entities,
            "semantic_groups": semantic_groups
        }
    
    def _extract_domain_info(self, domain_memory: List[Dict[str, Any]]) -> Dict[str, Any]:
        """从记忆中提取领域信息"""
        primary_domain = "通用业务"
        core_entities = []
        business_concepts = []
        
        for triple in domain_memory:
            subject = triple.get("subject", "")
            predicate = triple.get("predicate", "")
            obj = triple.get("object", "")
            
            if predicate == PredicateType.BELONGS_TO.value:
                primary_domain = obj
            elif predicate == PredicateType.CONTAINS.value:
                core_entities.append(obj)
            elif predicate == "has_concept":
                business_concepts.append(obj)
        
        return {
            "primary_domain": primary_domain,
            "core_entities": core_entities,
            "business_concepts": business_concepts
        }
    
    def _init_entity_patterns(self) -> Dict[str, Dict[str, Any]]:
        """初始化实体类型模式库"""
        return {
            "主数据表": {
                "name_patterns": ["user", "customer", "member", "product", "item", "account", "client"],
                "characteristics": ["has_id_column", "few_foreign_keys", "many_referenced"],
                "purpose_template": "存储和管理{entity_name}的核心主数据，作为业务的基础实体",
                "importance": "critical",
                "confidence_boost": 0.9
            },
            "交易事务表": {
                "name_patterns": ["order", "transaction", "payment", "sale", "purchase", "booking"],
                "characteristics": ["has_time_columns", "has_status_column", "multiple_foreign_keys"],
                "purpose_template": "记录{entity_name}相关的业务交易和状态变化，支持核心业务流程",
                "importance": "critical",
                "confidence_boost": 0.95
            },
            "明细子表": {
                "name_patterns": ["_detail", "_item", "_line", "detail", "item"],
                "characteristics": ["has_parent_reference", "few_columns", "detail_oriented"],
                "purpose_template": "存储{entity_name}的详细信息和子项数据，支持精细化业务管理",
                "importance": "high",
                "confidence_boost": 0.85
            },
            "字典码表": {
                "name_patterns": ["dict", "lookup", "ref", "category", "type", "status", "code"],
                "characteristics": ["small_table", "has_name_column", "few_columns"],
                "purpose_template": "维护{entity_name}的分类码表和参考数据，支持标准化管理",
                "importance": "medium",
                "confidence_boost": 0.8
            },
            "关联映射表": {
                "name_patterns": ["_rel", "_map", "_link", "mapping", "relation"],
                "characteristics": ["multiple_foreign_keys", "few_own_columns", "bridge_table"],
                "purpose_template": "维护{entity_name}之间的多对多关联关系，支持复杂业务关系",
                "importance": "medium",
                "confidence_boost": 0.85
            },
            "日志记录表": {
                "name_patterns": ["log", "audit", "history", "trace", "event", "_log"],
                "characteristics": ["has_time_columns", "append_only", "audit_oriented"],
                "purpose_template": "记录{entity_name}的操作日志和历史信息，支持审计追踪",
                "importance": "low",
                "confidence_boost": 0.9
            },
            "配置参数表": {
                "name_patterns": ["config", "setting", "param", "option", "property"],
                "characteristics": ["key_value_structure", "small_table", "config_oriented"],
                "purpose_template": "管理{entity_name}的系统配置和参数设置，支持灵活配置",
                "importance": "medium",
                "confidence_boost": 0.8
            }
        }
    
    def _analyze_tables_semantics(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """分析表语义"""
        schema_info = context["schema_info"]
        column_semantics = context["column_semantics"]
        domain_info = context["domain_info"]
        
        tables = schema_info["tables"]
        table_columns = schema_info["table_columns"]
        column_details = schema_info["column_details"]
        foreign_keys = schema_info["foreign_keys"]
        column_entities = column_semantics["column_entities"]
        semantic_groups = column_semantics["semantic_groups"]
        
        analyzed_tables = []
        entity_type_distribution = {}
        table_relationships = []
        core_tables = []
        
        # 分析每个表
        for table_name in tables:
            columns = table_columns.get(table_name, [])
            table_fks = foreign_keys.get(table_name, [])
            
            # 推断实体名称和类型
            entity_name = self._infer_entity_name(table_name, domain_info)
            entity_type, confidence, characteristics = self._classify_table_entity_type(
                table_name, columns, table_fks, column_details, semantic_groups
            )
            
            # 生成业务职责描述
            business_purpose = self._generate_business_purpose(
                table_name, entity_name, entity_type, domain_info
            )
            
            # 评估表重要性
            importance = self._assess_table_importance(entity_type, len(columns), len(table_fks))
            
            # 分析表间关系
            relationships = self._analyze_table_relationships(table_name, table_fks)
            
            table_analysis = {
                "table_name": table_name,
                "entity_name": entity_name,
                "entity_type": entity_type,
                "business_purpose": business_purpose,
                "importance": importance,
                "confidence": confidence,
                "characteristics": characteristics,
                "column_count": len(columns),
                "foreign_key_count": len(table_fks),
                "relationships": relationships
            }
            
            analyzed_tables.append(table_analysis)
            
            # 更新统计
            entity_type_distribution[entity_type] = entity_type_distribution.get(entity_type, 0) + 1
            
            # 收集核心表
            if importance in ["critical", "high"]:
                core_tables.append(table_name)
            
            # 收集表关系
            table_relationships.extend(relationships)
        
        return {
            "analyzed_tables": analyzed_tables,
            "entity_type_distribution": entity_type_distribution,
            "table_relationships": table_relationships,
            "core_tables": core_tables,
            "total_tables": len(analyzed_tables),
            "domain": domain_info["primary_domain"],
            "analysis_details": {
                "high_confidence_tables": len([t for t in analyzed_tables if t["confidence"] > 0.8]),
                "unique_entity_types": len(entity_type_distribution),
                "total_relationships": len(table_relationships)
            }
        }
    
    def _infer_entity_name(self, table_name: str, domain_info: Dict[str, Any]) -> str:
        """推断实体名称"""
        # 清理表名
        clean_name = table_name.lower()
        clean_name = re.sub(r'^(t_|tbl_|tb_)', '', clean_name)  # 去前缀
        clean_name = re.sub(r'(_log|_history|_backup|_temp)$', '', clean_name)  # 去后缀
        
        # 实体映射词典
        entity_mapping = {
            "user": "用户", "customer": "客户", "member": "会员", "person": "人员",
            "product": "产品", "goods": "商品", "item": "商品", "commodity": "商品",
            "order": "订单", "payment": "支付", "transaction": "交易", "bill": "账单",
            "account": "账户", "profile": "档案", "info": "信息", "data": "数据",
            "category": "分类", "type": "类型", "dict": "字典", "config": "配置",
            "log": "日志", "audit": "审计", "history": "历史", "event": "事件"
        }
        
        # 查找映射
        for english, chinese in entity_mapping.items():
            if english in clean_name:
                return chinese
        
        # 使用业务概念
        for concept in domain_info.get("business_concepts", []):
            if concept.lower() in clean_name:
                return concept
        
        # 返回清理后的名称
        return clean_name.replace("_", "").capitalize()
    
    def _classify_table_entity_type(self, table_name: str, columns: List[str], 
                                   foreign_keys: List[Dict], column_details: Dict[str, Any],
                                   semantic_groups: Dict[str, List[str]]) -> tuple:
        """分类表实体类型"""
        table_lower = table_name.lower()
        best_match = None
        best_confidence = 0.0
        
        # 分析表结构特征
        characteristics = self._analyze_table_characteristics(
            table_name, columns, foreign_keys, column_details, semantic_groups
        )
        
        for entity_type, pattern_info in self.entity_patterns.items():
            confidence = 0.0
            
            # 名称模式匹配（权重40%）
            name_score = 0.0
            for pattern in pattern_info["name_patterns"]:
                if pattern in table_lower:
                    name_score = 1.0
                    break
                elif any(part in pattern for part in table_lower.split("_")):
                    name_score = 0.6
            
            # 结构特征匹配（权重60%）
            characteristic_score = 0.0
            matched_characteristics = []
            for char in pattern_info["characteristics"]:
                if char in characteristics:
                    characteristic_score += 1.0
                    matched_characteristics.append(char)
            
            characteristic_score = min(characteristic_score / len(pattern_info["characteristics"]), 1.0)
            
            # 综合置信度
            confidence = (name_score * 0.4 + characteristic_score * 0.6) * pattern_info["confidence_boost"]
            
            if confidence > best_confidence and confidence > 0.3:
                best_confidence = confidence
                best_match = (entity_type, confidence, matched_characteristics)
        
        if best_match:
            return best_match
        else:
            return ("普通业务表", 0.2, ["unclassified"])
    
    def _analyze_table_characteristics(self, table_name: str, columns: List[str],
                                     foreign_keys: List[Dict], column_details: Dict[str, Any],
                                     semantic_groups: Dict[str, List[str]]) -> List[str]:
        """分析表结构特征"""
        characteristics = []
        table_columns = [f"{table_name}.{col}" for col in columns]
        
        # ID列特征
        if any("id" in col.lower() for col in columns):
            characteristics.append("has_id_column")
        
        # 主键特征  
        primary_key_count = sum(1 for col in columns 
                              if column_details.get(col, {}).get("is_primary_key", False))
        if primary_key_count > 0:
            characteristics.append("has_primary_key")
        
        # 外键特征
        if len(foreign_keys) == 0:
            characteristics.append("few_foreign_keys")
        elif len(foreign_keys) >= 2:
            characteristics.append("multiple_foreign_keys")
        
        # 表大小特征
        if len(columns) <= 5:
            characteristics.append("small_table")
        elif len(columns) <= 3:
            characteristics.append("few_columns")
        
        # 时间列特征
        time_columns = semantic_groups.get("时间字段", [])
        if any(col in time_columns for col in table_columns):
            characteristics.append("has_time_columns")
        
        # 状态列特征
        status_columns = semantic_groups.get("状态字段", [])
        if any(col in status_columns for col in table_columns):
            characteristics.append("has_status_column")
        
        # 名称列特征
        text_columns = semantic_groups.get("文本字段", [])
        if any(col in text_columns and "name" in col.lower() for col in table_columns):
            characteristics.append("has_name_column")
        
        # 特殊表类型特征
        table_lower = table_name.lower()
        if "_detail" in table_lower or "_item" in table_lower:
            characteristics.append("detail_oriented")
        elif "_log" in table_lower or "log" in table_lower:
            characteristics.append("append_only")
            characteristics.append("audit_oriented")
        elif "_config" in table_lower or "config" in table_lower:
            characteristics.append("config_oriented")
        elif len(foreign_keys) >= 2 and len(columns) - len(foreign_keys) <= 2:
            characteristics.append("bridge_table")
        
        return characteristics
    
    def _generate_business_purpose(self, table_name: str, entity_name: str, 
                                 entity_type: str, domain_info: Dict[str, Any]) -> str:
        """生成业务目的描述"""
        domain = domain_info["primary_domain"]
        pattern_info = self.entity_patterns.get(entity_type, {})
        template = pattern_info.get("purpose_template", "支持{entity_name}相关的业务功能")
        
        try:
            return template.format(
                entity_name=entity_name,
                table_name=table_name,
                domain=domain
            )
        except (KeyError, ValueError):
            return f"在{domain}领域中管理{entity_name}的相关数据"
    
    def _assess_table_importance(self, entity_type: str, column_count: int, fk_count: int) -> str:
        """评估表重要性"""
        # 基于实体类型的重要性
        type_importance = {
            "主数据表": "critical",
            "交易事务表": "critical", 
            "明细子表": "high",
            "字典码表": "medium",
            "关联映射表": "medium",
            "日志记录表": "low",
            "配置参数表": "medium",
            "普通业务表": "medium"
        }
        
        base_importance = type_importance.get(entity_type, "medium")
        
        # 基于结构复杂度调整
        if column_count >= 10 or fk_count >= 3:
            if base_importance == "medium":
                return "high"
            elif base_importance == "low":
                return "medium"
        elif column_count <= 3 and fk_count == 0:
            if base_importance == "high":
                return "medium"
            elif base_importance == "critical":
                return "high"
        
        return base_importance
    
    def _analyze_table_relationships(self, table_name: str, foreign_keys: List[Dict]) -> List[Dict[str, str]]:
        """分析表关系"""
        relationships = []
        
        for fk in foreign_keys:
            target_table = fk.get("target_table", "")
            relationship = {
                "type": "references",
                "target": target_table,
                "description": f"依赖{target_table}的数据"
            }
            relationships.append(relationship)
        
        return relationships
    
    def _generate_table_triples(self, analysis: Dict[str, Any], context: Dict[str, Any]) -> None:
        """生成表语义三元组"""
        database_name = context["schema_info"]["database_name"]
        analyzed_tables = analysis["analyzed_tables"]
        
        for table_info in analyzed_tables:
            table_name = table_info["table_name"]
            entity_name = table_info["entity_name"]
            entity_type = table_info["entity_type"]
            business_purpose = table_info["business_purpose"]
            importance = table_info["importance"]
            confidence = table_info["confidence"]
            relationships = table_info["relationships"]
            
            # 1. 表-实体类型关系
            self.add_analysis_triple(
                subject=table_name,
                predicate="has_entity_type",
                object=entity_type,
                subject_type=EntityType.TABLE.value,
                object_type="EntityType",
                confidence=confidence
            )
            
            # 2. 表-业务目的关系
            self.add_analysis_triple(
                subject=table_name,
                predicate="has_business_purpose",
                object=business_purpose,
                subject_type=EntityType.TABLE.value,
                object_type="BusinessPurpose",
                confidence=confidence
            )
            
            # 3. 表-实体名称关系
            self.add_analysis_triple(
                subject=table_name,
                predicate="represents_entity",
                object=entity_name,
                subject_type=EntityType.TABLE.value,
                object_type="BusinessEntity",
                confidence=0.8
            )
            
            # 4. 表-重要性关系
            self.add_analysis_triple(
                subject=table_name,
                predicate="has_importance_level",
                object=importance,
                subject_type=EntityType.TABLE.value,
                object_type="ImportanceLevel",
                confidence=confidence
            )
            
            # 5. 表间关系三元组
            for rel in relationships:
                if rel["type"] == "references":
                    self.add_analysis_triple(
                        subject=table_name,
                        predicate="depends_on",
                        object=rel["target"],
                        subject_type=EntityType.TABLE.value,
                        object_type=EntityType.TABLE.value,
                        confidence=0.9
                    )
        
        # 6. 核心表标记
        for core_table in analysis["core_tables"]:
            self.add_analysis_triple(
                subject=database_name,
                predicate="has_core_table",
                object=core_table,
                subject_type=EntityType.DATABASE.value,
                object_type=EntityType.TABLE.value,
                confidence=0.85
            )
        
        self.logger.info(f"📝 生成了 {len(self._generated_triples)} 个表语义三元组")
    
    def _build_result_message(self, analysis: Dict[str, Any]) -> str:
        """构建执行结果消息"""
        total_tables = analysis["total_tables"]
        entity_type_distribution = analysis["entity_type_distribution"]
        core_tables = analysis["core_tables"]
        table_relationships = analysis["table_relationships"]
        domain = analysis["domain"]
        triple_count = len(self._generated_triples)
        
        # 构建实体类型分布统计
        type_stats = []
        for entity_type, count in entity_type_distribution.items():
            type_stats.append(f"  • {entity_type}: {count}个")
        
        # 构建核心表描述
        core_desc = ""
        if core_tables:
            core_display = core_tables[:5]
            if len(core_tables) > 5:
                core_display.append(f"等{len(core_tables)}个")
            core_desc = f"\n  • 核心表: {', '.join(core_display)}"
        
        result = f"""✅ 表语义分析完成

🎯 分析结果:
  • 分析表总数: {total_tables}
  • 业务域: {domain}
  • 生成三元组: {triple_count}个{core_desc}

📊 实体类型分布:
{chr(10).join(type_stats)}

🔗 表间关系:
  • 发现关系: {len(table_relationships)}个
  • 依赖模式分析完成

📈 分析质量:
  • 高置信度表: {analysis['analysis_details']['high_confidence_tables']}个
  • 实体类型数: {analysis['analysis_details']['unique_entity_types']}种
  • 关系总数: {analysis['analysis_details']['total_relationships']}个

💾 表语义知识已存储到记忆系统，可供后续工具使用"""
        
        return result


# ========== 便利函数 ==========
def create_table_analysis_tool(memory_manager: Optional['Neo4jMemoryManager'] = None) -> TableAnalysisTool:
    """创建表分析工具的便利函数"""
    return TableAnalysisTool(memory_manager=memory_manager)