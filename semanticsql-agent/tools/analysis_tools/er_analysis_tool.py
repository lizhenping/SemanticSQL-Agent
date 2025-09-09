"""
ER关系分析工具 - 极简架构重构版本
基于新的BaseSemanticSQLTool，实现完全自主的ER关系分析
"""

from typing import Dict, Any, List, Optional
import json
import re

from tools.base_tool import BaseSemanticSQLTool
from models.schemas import PredicateType, EntityType
from models.exceptions import raise_tool_error, raise_dependency_error


class ERAnalysisTool(BaseSemanticSQLTool):
    """ER关系分析工具 - 极简重构版本
    
    职责：
    - 基于数据库结构和表语义进行ER关系分析
    - 识别表间的物理关系、逻辑关系和语义关系
    - 构建完整的实体关系图谱
    - 为后续工具提供关系知识上下文
    
    设计原则：
    - 依赖记忆：基于schema_extraction、table_analysis工具的结果
    - 智能推断：结合外键约束和业务语义推断关系
    - 三元组输出：结构化关系知识表示
    """
    
    name: str = "er_analysis"
    description: str = "分析数据库表间的ER关系，构建实体关系图谱"
    
    def __init__(self, **kwargs):
        """初始化ER分析工具"""
        super().__init__(**kwargs)
        # 使用object.__setattr__避免Pydantic验证问题
        object.__setattr__(self, 'relationship_patterns', self._init_relationship_patterns())
    
    def _run(self, *args, **kwargs) -> str:
        """执行工具分析"""
        # 提取输入文本
        input_text = args[0] if args else kwargs.get('input', '')
        # 1. 清空上次执行的三元组
        self._clear_generated_triples()
        self._log_execution_start(input_text)
        
        try:
            # 2. 检查依赖：需要schema_extraction和table_analysis工具的结果
            self._check_dependencies(["schema_extraction", "table_analysis"])
            
            # 3. 获取依赖分析结果
            analysis_context = self._gather_analysis_context()
            
            # 4. 分析ER关系
            er_analysis = self._analyze_er_relationships(analysis_context)
            
            # 5. 生成ER关系三元组
            self._generate_er_triples(er_analysis, analysis_context)
            
            # 6. 持久化三元组到记忆系统
            self._persist_triples()
            
            # 7. 构建执行结果
            result_message = self._build_result_message(er_analysis)
            
            self._log_execution_end(f"分析了 {er_analysis['total_relationships']} 个关系")
            return result_message
            
        except Exception as e:
            error_msg = f"ER关系分析失败: {str(e)}"
            self.logger.error(f"❌ {self.name}: {error_msg}")
            return f"❌ {error_msg}"
    
    # ========== 核心业务逻辑 ==========
    def _gather_analysis_context(self) -> Dict[str, Any]:
        """收集分析上下文"""
        # 获取基础结构信息
        schema_memory = self.get_memory_by_source_tool("schema_extraction")
        schema_info = self._extract_schema_info(schema_memory)
        
        # 获取表语义分析结果
        table_memory = self.get_memory_by_source_tool("table_analysis")
        table_semantics = self._extract_table_semantics(table_memory)
        
        # 尝试获取领域信息（可选）
        domain_memory = self.get_memory_by_source_tool("domain_analysis")
        domain_info = self._extract_domain_info(domain_memory) if domain_memory else {"primary_domain": "通用业务"}
        
        # 尝试获取列分析信息（可选）
        column_memory = self.get_memory_by_source_tool("column_analysis")
        column_info = self._extract_column_info(column_memory) if column_memory else {}
        
        return {
            "schema_info": schema_info,
            "table_semantics": table_semantics,
            "domain_info": domain_info,
            "column_info": column_info
        }
    
    def _extract_schema_info(self, schema_memory: List[Dict[str, Any]]) -> Dict[str, Any]:
        """从记忆中提取结构信息"""
        if not schema_memory:
            raise_dependency_error(self.name, "schema_extraction", "数据库结构信息")
        
        # 从三元组中重建结构信息
        tables = set()
        table_columns = {}
        foreign_key_relationships = []
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
                    source_parts = subject.split(".", 1)
                    target_parts = obj.split(".", 1)
                    if len(source_parts) == 2 and len(target_parts) == 2:
                        foreign_key_relationships.append({
                            "source_table": source_parts[0],
                            "source_column": source_parts[1], 
                            "target_table": target_parts[0],
                            "target_column": target_parts[1]
                        })
        
        return {
            "database_name": database_name,
            "tables": list(tables),
            "table_columns": table_columns,
            "foreign_key_relationships": foreign_key_relationships
        }
    
    def _extract_table_semantics(self, table_memory: List[Dict[str, Any]]) -> Dict[str, Any]:
        """从记忆中提取表语义信息"""
        table_entity_types = {}
        table_business_purposes = {}
        table_entities = {}
        table_importance = {}
        table_dependencies = []
        
        for triple in table_memory:
            subject = triple.get("subject", "")
            predicate = triple.get("predicate", "")
            obj = triple.get("object", "")
            
            if predicate == "has_entity_type":
                table_entity_types[subject] = obj
            elif predicate == "has_business_purpose":
                table_business_purposes[subject] = obj
            elif predicate == "represents_entity":
                table_entities[subject] = obj
            elif predicate == "has_importance_level":
                table_importance[subject] = obj
            elif predicate == "depends_on":
                table_dependencies.append({"source": subject, "target": obj})
        
        return {
            "table_entity_types": table_entity_types,
            "table_business_purposes": table_business_purposes,
            "table_entities": table_entities,
            "table_importance": table_importance,
            "table_dependencies": table_dependencies
        }
    
    def _extract_domain_info(self, domain_memory: List[Dict[str, Any]]) -> Dict[str, Any]:
        """从记忆中提取领域信息"""
        primary_domain = "通用业务"
        core_entities = []
        
        for triple in domain_memory:
            subject = triple.get("subject", "")
            predicate = triple.get("predicate", "")
            obj = triple.get("object", "")
            
            if predicate == PredicateType.BELONGS_TO.value:
                primary_domain = obj
            elif predicate == PredicateType.CONTAINS.value:
                core_entities.append(obj)
        
        return {
            "primary_domain": primary_domain,
            "core_entities": core_entities
        }
    
    def _extract_column_info(self, column_memory: List[Dict[str, Any]]) -> Dict[str, Any]:
        """从记忆中提取列信息"""
        column_entities = {}
        
        for triple in column_memory:
            subject = triple.get("subject", "")
            predicate = triple.get("predicate", "")
            obj = triple.get("object", "")
            
            if predicate == "belongs_to_entity":
                column_entities[subject] = obj
        
        return {
            "column_entities": column_entities
        }
    
    def _init_relationship_patterns(self) -> Dict[str, Dict[str, Any]]:
        """初始化关系模式库"""
        return {
            "一对多关系": {
                "indicators": ["foreign_key", "parent_child", "master_detail"],
                "cardinality": "1:N",
                "description_template": "{parent}实体与{child}实体之间的一对多关系",
                "strength": 0.9
            },
            "多对多关系": {
                "indicators": ["junction_table", "many_foreign_keys", "bridge"],
                "cardinality": "M:N",
                "description_template": "{entity1}实体与{entity2}实体之间的多对多关系",
                "strength": 0.8
            },
            "组合关系": {
                "indicators": ["detail_table", "line_item", "composition"],
                "cardinality": "1:N",
                "description_template": "{whole}实体组合包含{part}实体",
                "strength": 0.85
            },
            "聚合关系": {
                "indicators": ["aggregation", "grouping", "collection"],
                "cardinality": "1:N",
                "description_template": "{container}实体聚合{contained}实体",
                "strength": 0.7
            },
            "依赖关系": {
                "indicators": ["reference", "lookup", "dependency"],
                "cardinality": "N:1",
                "description_template": "{dependent}实体依赖{independent}实体",
                "strength": 0.6
            },
            "继承关系": {
                "indicators": ["inheritance", "is_a", "subtype"],
                "cardinality": "1:1",
                "description_template": "{child}实体继承{parent}实体",
                "strength": 0.9
            }
        }
    
    def _analyze_er_relationships(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """分析ER关系"""
        schema_info = context["schema_info"]
        table_semantics = context["table_semantics"]
        domain_info = context["domain_info"]
        column_info = context["column_info"]
        
        tables = schema_info["tables"]
        foreign_key_relationships = schema_info["foreign_key_relationships"]
        table_entity_types = table_semantics["table_entity_types"]
        table_entities = table_semantics["table_entities"]
        table_dependencies = table_semantics["table_dependencies"]
        
        # 分析物理关系
        physical_relationships = self._analyze_physical_relationships(
            foreign_key_relationships, table_entities
        )
        
        # 分析逻辑关系
        logical_relationships = self._analyze_logical_relationships(
            physical_relationships, table_semantics, domain_info
        )
        
        # 分析语义关系
        semantic_relationships = self._analyze_semantic_relationships(
            logical_relationships, table_entity_types, domain_info
        )
        
        # 分析关系强度和重要性
        relationship_strength = self._calculate_relationship_strength(
            physical_relationships + logical_relationships
        )
        
        # 构建关系图谱
        relationship_graph = self._build_relationship_graph(
            physical_relationships + logical_relationships
        )
        
        return {
            "physical_relationships": physical_relationships,
            "logical_relationships": logical_relationships,
            "semantic_relationships": semantic_relationships,
            "relationship_strength": relationship_strength,
            "relationship_graph": relationship_graph,
            "total_relationships": len(physical_relationships) + len(logical_relationships) + len(semantic_relationships),
            "domain": domain_info["primary_domain"],
            "analysis_details": {
                "tables_analyzed": len(tables),
                "foreign_keys_found": len(foreign_key_relationships),
                "high_strength_relationships": len([r for r in relationship_strength if r["strength"] > 0.8])
            }
        }
    
    def _analyze_physical_relationships(self, foreign_key_relationships: List[Dict],
                                      table_entities: Dict[str, str]) -> List[Dict[str, Any]]:
        """分析物理关系（基于外键约束）"""
        physical_relationships = []
        
        for fk in foreign_key_relationships:
            source_table = fk["source_table"]
            target_table = fk["target_table"]
            source_column = fk["source_column"]
            target_column = fk["target_column"]
            
            source_entity = table_entities.get(source_table, source_table)
            target_entity = table_entities.get(target_table, target_table)
            
            relationship = {
                "type": "physical",
                "relationship_id": f"{source_table}_fk_{target_table}",
                "source_table": source_table,
                "target_table": target_table,
                "source_entity": source_entity,
                "target_entity": target_entity,
                "source_column": source_column,
                "target_column": target_column,
                "cardinality": "N:1",  # 外键通常是多对一
                "relationship_type": "foreign_key",
                "description": f"{source_entity}通过{source_column}引用{target_entity}的{target_column}",
                "strength": 0.95,  # 物理关系强度最高
                "confidence": 1.0
            }
            
            physical_relationships.append(relationship)
        
        return physical_relationships
    
    def _analyze_logical_relationships(self, physical_relationships: List[Dict],
                                     table_semantics: Dict[str, Any],
                                     domain_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """分析逻辑关系（基于业务语义）"""
        logical_relationships = []
        table_entity_types = table_semantics["table_entity_types"]
        table_dependencies = table_semantics["table_dependencies"]
        
        # 基于物理关系推断逻辑关系
        for physical in physical_relationships:
            source_table = physical["source_table"]
            target_table = physical["target_table"]
            source_entity_type = table_entity_types.get(source_table, "普通业务表")
            target_entity_type = table_entity_types.get(target_table, "普通业务表")
            
            # 根据实体类型推断逻辑关系类型
            logical_type = self._infer_logical_relationship_type(
                source_entity_type, target_entity_type, source_table, target_table
            )
            
            logical_relationship = {
                "type": "logical",
                "relationship_id": f"{source_table}_logical_{target_table}",
                "source_table": source_table,
                "target_table": target_table,
                "source_entity": physical["source_entity"],
                "target_entity": physical["target_entity"],
                "logical_type": logical_type["type"],
                "cardinality": logical_type["cardinality"],
                "description": logical_type["description"],
                "strength": logical_type["strength"],
                "confidence": 0.8,
                "business_meaning": self._generate_business_meaning(
                    physical, logical_type, domain_info["primary_domain"]
                )
            }
            
            logical_relationships.append(logical_relationship)
        
        # 分析隐式逻辑关系（没有外键但有业务关联）
        implicit_relationships = self._analyze_implicit_logical_relationships(
            table_semantics, domain_info
        )
        logical_relationships.extend(implicit_relationships)
        
        return logical_relationships
    
    def _infer_logical_relationship_type(self, source_type: str, target_type: str,
                                       source_table: str, target_table: str) -> Dict[str, Any]:
        """推断逻辑关系类型"""
        source_table_lower = source_table.lower()
        target_table_lower = target_table.lower()
        
        # 组合关系：明细表到主表
        if source_type == "明细子表" and target_type in ["主数据表", "交易事务表"]:
            return {
                "type": "组合关系",
                "cardinality": "N:1",
                "description": f"{source_table}是{target_table}的组成部分",
                "strength": 0.9
            }
        
        # 依赖关系：事务表到主数据表
        if source_type == "交易事务表" and target_type == "主数据表":
            return {
                "type": "依赖关系", 
                "cardinality": "N:1",
                "description": f"{source_table}依赖{target_table}的主数据",
                "strength": 0.85
            }
        
        # 参考关系：业务表到字典表
        if target_type == "字典码表":
            return {
                "type": "参考关系",
                "cardinality": "N:1",
                "description": f"{source_table}参考{target_table}的码表数据",
                "strength": 0.7
            }
        
        # 关联关系：关联表
        if source_type == "关联映射表":
            return {
                "type": "多对多关系",
                "cardinality": "M:N",
                "description": f"{source_table}维护多对多关联关系",
                "strength": 0.8
            }
        
        # 默认一对多关系
        return {
            "type": "一对多关系",
            "cardinality": "1:N",
            "description": f"{target_table}与{source_table}之间的一对多关系",
            "strength": 0.6
        }
    
    def _generate_business_meaning(self, physical: Dict[str, Any], logical_type: Dict[str, Any],
                                 domain: str) -> str:
        """生成业务含义"""
        source_entity = physical["source_entity"]
        target_entity = physical["target_entity"]
        relationship_type = logical_type["type"]
        
        meaning_templates = {
            "组合关系": f"在{domain}业务中，{source_entity}是{target_entity}的重要组成部分",
            "依赖关系": f"在{domain}业务中，{source_entity}的业务流程依赖于{target_entity}的基础数据",
            "参考关系": f"在{domain}业务中，{source_entity}需要参考{target_entity}的标准化数据",
            "多对多关系": f"在{domain}业务中，{source_entity}与{target_entity}之间存在复杂的关联关系",
            "一对多关系": f"在{domain}业务中，一个{target_entity}可以关联多个{source_entity}"
        }
        
        return meaning_templates.get(relationship_type, 
                                   f"在{domain}业务中，{source_entity}与{target_entity}存在业务关联")
    
    def _analyze_implicit_logical_relationships(self, table_semantics: Dict[str, Any],
                                              domain_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """分析隐式逻辑关系"""
        implicit_relationships = []
        table_dependencies = table_semantics["table_dependencies"]
        table_entities = table_semantics["table_entities"]
        
        # 基于表依赖关系生成隐式逻辑关系
        for dep in table_dependencies:
            source_table = dep["source"]
            target_table = dep["target"]
            
            implicit_relationship = {
                "type": "logical",
                "relationship_id": f"{source_table}_implicit_{target_table}",
                "source_table": source_table,
                "target_table": target_table,
                "source_entity": table_entities.get(source_table, source_table),
                "target_entity": table_entities.get(target_table, target_table),
                "logical_type": "业务依赖",
                "cardinality": "N:1",
                "description": f"{source_table}在业务上依赖{target_table}",
                "strength": 0.6,
                "confidence": 0.7,
                "business_meaning": f"在{domain_info['primary_domain']}业务中，{source_table}的业务逻辑依赖{target_table}"
            }
            
            implicit_relationships.append(implicit_relationship)
        
        return implicit_relationships
    
    def _analyze_semantic_relationships(self, logical_relationships: List[Dict],
                                      table_entity_types: Dict[str, str],
                                      domain_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """分析语义关系"""
        semantic_relationships = []
        domain = domain_info["primary_domain"]
        
        for logical in logical_relationships:
            source_table = logical["source_table"]
            target_table = logical["target_table"]
            source_entity = logical["source_entity"]
            target_entity = logical["target_entity"]
            logical_type = logical["logical_type"]
            
            # 推断语义关系类型
            semantic_type = self._map_logical_to_semantic(logical_type)
            
            semantic_relationship = {
                "type": "semantic",
                "relationship_id": f"{source_table}_semantic_{target_table}",
                "source_concept": f"{source_entity}概念",
                "target_concept": f"{target_entity}概念",
                "semantic_type": semantic_type,
                "domain_context": domain,
                "conceptual_description": self._generate_conceptual_description(
                    source_entity, target_entity, semantic_type, domain
                ),
                "strength": logical["strength"] * 0.8,  # 语义关系强度略低于逻辑关系
                "abstraction_level": self._determine_abstraction_level(logical_type)
            }
            
            semantic_relationships.append(semantic_relationship)
        
        return semantic_relationships
    
    def _map_logical_to_semantic(self, logical_type: str) -> str:
        """将逻辑关系映射为语义关系"""
        mapping = {
            "组合关系": "part-of",
            "依赖关系": "depends-on", 
            "参考关系": "refers-to",
            "多对多关系": "associates-with",
            "一对多关系": "contains",
            "业务依赖": "relies-on"
        }
        
        return mapping.get(logical_type, "relates-to")
    
    def _generate_conceptual_description(self, source_entity: str, target_entity: str,
                                       semantic_type: str, domain: str) -> str:
        """生成概念描述"""
        descriptions = {
            "part-of": f"在{domain}领域的概念模型中，{source_entity}概念是{target_entity}概念的组成部分",
            "depends-on": f"在{domain}领域的概念模型中，{source_entity}概念依赖于{target_entity}概念",
            "refers-to": f"在{domain}领域的概念模型中，{source_entity}概念引用{target_entity}概念",
            "associates-with": f"在{domain}领域的概念模型中，{source_entity}概念与{target_entity}概念相互关联",
            "contains": f"在{domain}领域的概念模型中，{target_entity}概念包含{source_entity}概念",
            "relies-on": f"在{domain}领域的概念模型中，{source_entity}概念依赖{target_entity}概念"
        }
        
        return descriptions.get(semantic_type, 
                              f"在{domain}领域的概念模型中，{source_entity}概念与{target_entity}概念存在语义关联")
    
    def _determine_abstraction_level(self, logical_type: str) -> str:
        """确定抽象层次"""
        abstraction_mapping = {
            "组合关系": "结构层",
            "依赖关系": "功能层",
            "参考关系": "数据层",
            "多对多关系": "关系层",
            "一对多关系": "层次层",
            "业务依赖": "业务层"
        }
        
        return abstraction_mapping.get(logical_type, "概念层")
    
    def _calculate_relationship_strength(self, relationships: List[Dict]) -> List[Dict[str, Any]]:
        """计算关系强度"""
        relationship_strength = []
        
        for rel in relationships:
            strength_info = {
                "relationship_id": rel["relationship_id"],
                "source": rel["source_table"],
                "target": rel["target_table"],
                "strength": rel["strength"],
                "confidence": rel["confidence"],
                "type": rel["type"],
                "strength_category": self._categorize_strength(rel["strength"])
            }
            relationship_strength.append(strength_info)
        
        return sorted(relationship_strength, key=lambda x: x["strength"], reverse=True)
    
    def _categorize_strength(self, strength: float) -> str:
        """分类关系强度"""
        if strength >= 0.9:
            return "强关系"
        elif strength >= 0.7:
            return "中等关系"
        elif strength >= 0.5:
            return "弱关系"
        else:
            return "微弱关系"
    
    def _build_relationship_graph(self, relationships: List[Dict]) -> Dict[str, Any]:
        """构建关系图谱"""
        nodes = set()
        edges = []
        node_degrees = {}
        
        for rel in relationships:
            source = rel["source_table"]
            target = rel["target_table"]
            
            nodes.add(source)
            nodes.add(target)
            
            edges.append({
                "source": source,
                "target": target,
                "type": rel.get("logical_type", rel.get("relationship_type", "unknown")),
                "weight": rel["strength"]
            })
            
            # 计算节点度数
            node_degrees[source] = node_degrees.get(source, 0) + 1
            node_degrees[target] = node_degrees.get(target, 0) + 1
        
        # 识别核心节点（度数最高）
        core_nodes = sorted(node_degrees.items(), key=lambda x: x[1], reverse=True)[:3]
        
        return {
            "nodes": list(nodes),
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "core_nodes": [{"node": node, "degree": degree} for node, degree in core_nodes],
            "graph_density": len(edges) / (len(nodes) * (len(nodes) - 1)) if len(nodes) > 1 else 0.0
        }
    
    def _generate_er_triples(self, analysis: Dict[str, Any], context: Dict[str, Any]) -> None:
        """生成ER关系三元组"""
        database_name = context["schema_info"]["database_name"]
        
        # 1. 生成物理关系三元组
        for rel in analysis["physical_relationships"]:
            self.add_analysis_triple(
                subject=rel["source_table"],
                predicate="has_physical_relationship",
                object=rel["target_table"],
                subject_type=EntityType.TABLE.value,
                object_type=EntityType.TABLE.value,
                confidence=rel["confidence"]
            )
            
            # 关系类型信息
            self.add_analysis_triple(
                subject=rel["relationship_id"],
                predicate="has_cardinality", 
                object=rel["cardinality"],
                subject_type="Relationship",
                object_type="Cardinality",
                confidence=1.0
            )
        
        # 2. 生成逻辑关系三元组
        for rel in analysis["logical_relationships"]:
            self.add_analysis_triple(
                subject=rel["source_table"],
                predicate="has_logical_relationship",
                object=rel["target_table"],
                subject_type=EntityType.TABLE.value,
                object_type=EntityType.TABLE.value,
                confidence=rel["confidence"]
            )
            
            # 逻辑关系类型
            self.add_analysis_triple(
                subject=rel["relationship_id"],
                predicate="has_logical_type",
                object=rel["logical_type"],
                subject_type="LogicalRelationship",
                object_type="LogicalType",
                confidence=rel["confidence"]
            )
            
            # 业务含义
            self.add_analysis_triple(
                subject=rel["relationship_id"],
                predicate="has_business_meaning",
                object=rel["business_meaning"],
                subject_type="LogicalRelationship",
                object_type="BusinessMeaning",
                confidence=rel["confidence"]
            )
        
        # 3. 生成语义关系三元组
        for rel in analysis["semantic_relationships"]:
            self.add_analysis_triple(
                subject=rel["source_concept"],
                predicate="has_semantic_relationship",
                object=rel["target_concept"],
                subject_type="Concept",
                object_type="Concept",
                confidence=0.8
            )
            
            # 语义类型
            self.add_analysis_triple(
                subject=rel["relationship_id"],
                predicate="has_semantic_type",
                object=rel["semantic_type"],
                subject_type="SemanticRelationship",
                object_type="SemanticType",
                confidence=0.8
            )
        
        # 4. 生成关系图谱三元组
        graph = analysis["relationship_graph"]
        for core_node_info in graph["core_nodes"]:
            self.add_analysis_triple(
                subject=database_name,
                predicate="has_core_entity",
                object=core_node_info["node"],
                subject_type=EntityType.DATABASE.value,
                object_type=EntityType.TABLE.value,
                confidence=0.9
            )
        
        self.logger.info(f"📝 生成了 {len(self._generated_triples)} 个ER关系三元组")
    
    def _build_result_message(self, analysis: Dict[str, Any]) -> str:
        """构建执行结果消息"""
        total_relationships = analysis["total_relationships"]
        physical_count = len(analysis["physical_relationships"])
        logical_count = len(analysis["logical_relationships"])
        semantic_count = len(analysis["semantic_relationships"])
        domain = analysis["domain"]
        graph = analysis["relationship_graph"]
        triple_count = len(self._generated_triples)
        
        # 构建关系强度统计
        strength_stats = {}
        for rel in analysis["relationship_strength"]:
            category = rel["strength_category"]
            strength_stats[category] = strength_stats.get(category, 0) + 1
        
        strength_desc = []
        for category, count in strength_stats.items():
            strength_desc.append(f"  • {category}: {count}个")
        
        # 构建核心节点描述
        core_nodes = graph["core_nodes"]
        core_desc = ""
        if core_nodes:
            core_names = [node["node"] for node in core_nodes[:3]]
            core_desc = f"\n  • 核心节点: {', '.join(core_names)}"
        
        result = f"""✅ ER关系分析完成

🎯 关系分析结果:
  • 关系总数: {total_relationships}个
  • 物理关系: {physical_count}个
  • 逻辑关系: {logical_count}个
  • 语义关系: {semantic_count}个
  • 业务域: {domain}
  • 生成三元组: {triple_count}个{core_desc}

📊 关系强度分布:
{chr(10).join(strength_desc) if strength_desc else "  • 暂无强度统计"}

🕸️ 关系图谱特征:
  • 节点数: {graph['node_count']}个表
  • 边数: {graph['edge_count']}个关系
  • 图密度: {graph['graph_density']:.3f}
  
📈 分析质量:
  • 分析表数: {analysis['analysis_details']['tables_analyzed']}
  • 外键发现: {analysis['analysis_details']['foreign_keys_found']}个
  • 强关系数: {analysis['analysis_details']['high_strength_relationships']}个

💾 ER关系知识已存储到记忆系统，可供后续工具使用"""
        
        return result


# ========== 便利函数 ==========
def create_er_analysis_tool(memory_manager: Optional['Neo4jMemoryManager'] = None) -> ERAnalysisTool:
    """创建ER分析工具的便利函数"""
    return ERAnalysisTool(memory_manager=memory_manager)