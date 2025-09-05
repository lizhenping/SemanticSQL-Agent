"""
ER关系分析工具 - 优化版本
简化设计，移除过度异常处理，按就近原则组织代码
"""

from typing import Dict, Any, Type, List, Tuple
from enum import Enum
import json
from dataclasses import dataclass
from pydantic import BaseModel, Field

from models.exceptions import ToolExecutionError
from prompts.manager import PromptManager
from ..base_tool import BaseSemanticSQLTool


# ========== 工具内部数据模型（就近原则）==========
class ERAnalysisInput(BaseModel):
    """ER关系分析输入参数"""
    include_physical: bool = Field(default=True, description="是否分析物理关系")
    include_logical: bool = Field(default=True, description="是否分析逻辑关系")
    include_semantic: bool = Field(default=True, description="是否分析语义关系")


class RelationType(str, Enum):
    """关系类型枚举"""
    FOREIGN_KEY = "foreign_key"      # 物理外键关系
    ONE_TO_ONE = "one_to_one"        # 一对一关系
    ONE_TO_MANY = "one_to_many"      # 一对多关系
    MANY_TO_MANY = "many_to_many"    # 多对多关系
    INHERITANCE = "inheritance"      # 继承关系
    COMPOSITION = "composition"      # 组合关系
    AGGREGATION = "aggregation"      # 聚合关系
    DEPENDENCY = "dependency"        # 依赖关系


class CardinalityType(str, Enum):
    """基数约束类型"""
    ONE_TO_ONE = "1:1"
    ONE_TO_MANY = "1:N"
    MANY_TO_ONE = "N:1"
    MANY_TO_MANY = "M:N"
    ZERO_TO_ONE = "0:1"
    ZERO_TO_MANY = "0:N"


@dataclass
class PhysicalRelation:
    """物理关系信息"""
    source_table: str
    target_table: str
    source_columns: List[str]
    target_columns: List[str]
    constraint_name: str
    relation_type: RelationType = RelationType.FOREIGN_KEY


class LogicalRelation(BaseModel):
    """逻辑关系信息"""
    source_entity: str
    target_entity: str
    relation_type: RelationType
    cardinality: CardinalityType
    relation_name: str
    description: str
    confidence: float = 0.8


class SemanticRelation(BaseModel):
    """语义关系信息"""
    source_concept: str
    target_concept: str
    semantic_type: str  # "is-a", "has-a", "uses", "contains", etc.
    business_description: str
    domain_context: str
    strength: float = 0.5  # 关系强度


class ERAnalysisTool(BaseSemanticSQLTool):
    """
ER关系分析工具 - 优化版本
    
    职责：
    - 分析数据库表之间的物理关系（外键约束）
    - 推断逻辑关系（业务关联）
    - 分析语义关系（概念关联）
    - 构建实体关系矩阵
    
    设计原则：
    - 单一职责：专注ER关系分析
    - 方法拆分：每个方法<30行
    - 类型安全：使用枚举和数据类
    - 简化异常：让异常自然传播
    """
    
    name: str = "er_analysis"
    description: str = "分析数据库表之间的物理、逻辑和语义关系"
    args_schema: Type[BaseModel] = ERAnalysisInput
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, 'prompt_manager', PromptManager())

    def _run(self, include_physical: bool = True, include_logical: bool = True, 
             include_semantic: bool = True, **kwargs) -> str:
        """执行ER关系分析 - 主流程"""
        # 获取分析上下文
        analysis_context = self._gather_analysis_context()
        
        # 分析物理关系
        physical_relations = []
        if include_physical:
            physical_relations = self._analyze_physical_relations(analysis_context)
        
        # 分析逻辑关系
        logical_relations = []
        if include_logical:
            logical_relations = self._analyze_logical_relations(analysis_context, physical_relations)
        
        # 分析语义关系
        semantic_relations = []
        if include_semantic:
            semantic_relations = self._analyze_semantic_relations(analysis_context, logical_relations)
        
        # 构建关系矩阵
        relationship_matrix = self._build_relationship_matrix(physical_relations, logical_relations)
        
        # 构建分析结果
        result = self._build_analysis_result(
            physical_relations, logical_relations, semantic_relations, 
            relationship_matrix, analysis_context
        )
        
        # 保存并返回
        self.save_to_memory("er_relations", result)
        return json.dumps(result, ensure_ascii=False)

    # ========== 核心分析逻辑 ==========
    def _gather_analysis_context(self) -> Dict[str, Any]:
        """获取分析上下文"""
        context = {
            "schema_info": self.get_from_memory("schema_extraction"),
            "column_meanings": self.get_from_memory("column_meanings"),
            "table_meanings": self.get_from_memory("table_meanings"),
            "domain_info": self.get_from_memory("domain_analysis")
        }
        
        if not context["schema_info"]:
            raise ToolExecutionError(
                tool_name=self.name,
                reason="无法获取数据库结构信息，需要先运行schema_extraction工具"
            )
        
        return context
    
    def _analyze_physical_relations(self, analysis_context: Dict[str, Any]) -> List[PhysicalRelation]:
        """分析物理关系（外键约束）"""
        physical_relations = []
        schema_info = analysis_context["schema_info"]
        tables = schema_info.get("tables", {})
        
        for table_name, table_info in tables.items():
            foreign_keys = table_info.get("foreign_keys", [])
            for fk in foreign_keys:
                relation = PhysicalRelation(
                    source_table=table_name,
                    target_table=fk.get("referred_table", ""),
                    source_columns=fk.get("constrained_columns", []),
                    target_columns=fk.get("referred_columns", []),
                    constraint_name=fk.get("constraint_name", "")
                )
                physical_relations.append(relation)
        
        return physical_relations

    def _analyze_logical_relations(self, analysis_context: Dict[str, Any], 
                                 physical_relations: List[PhysicalRelation]) -> List[LogicalRelation]:
        """分析逻辑关系（业务关联）"""
        logical_relations = []
        
        # 基于物理关系生成逻辑关系
        for physical in physical_relations:
            logical = self._create_logical_from_physical(physical, analysis_context)
            logical_relations.append(logical)
        
        # 推断隐式逻辑关系（没有外键但可能存在业务关联）
        implicit_relations = self._infer_implicit_logical_relations(analysis_context)
        logical_relations.extend(implicit_relations)
        
        return logical_relations
    
    def _create_logical_from_physical(self, physical: PhysicalRelation, 
                                    analysis_context: Dict[str, Any]) -> LogicalRelation:
        """从物理关系创建逻辑关系"""
        # 推断基数约束
        cardinality = self._infer_cardinality(physical, analysis_context)
        
        # 生成关系名称
        relation_name = f"{physical.source_table}_references_{physical.target_table}"
        
        # 生成描述
        description = self._generate_logical_description(physical, analysis_context)
        
        return LogicalRelation(
            source_entity=physical.source_table,
            target_entity=physical.target_table,
            relation_type=RelationType.ONE_TO_MANY,  # 大多数外键都是多对一
            cardinality=cardinality,
            relation_name=relation_name,
            description=description,
            confidence=0.9
        )
    
    def _infer_cardinality(self, physical: PhysicalRelation, 
                          analysis_context: Dict[str, Any]) -> CardinalityType:
        """推断基数约束"""
        # 简化实现：大多数情况下外键都是多对一
        # 实际实现中可以根据字段特征、索引信息等进行更精确的推断
        
        # 如果源字段是唯一索引，可能是一对一关系
        if len(physical.source_columns) == 1 and physical.source_columns[0].endswith("_id"):
            source_col = physical.source_columns[0]
            if source_col in ["user_id", "customer_id"] and "profile" in physical.source_table.lower():
                return CardinalityType.ONE_TO_ONE
        
        return CardinalityType.MANY_TO_ONE
    
    def _generate_logical_description(self, physical: PhysicalRelation, 
                                    analysis_context: Dict[str, Any]) -> str:
        """生成逻辑关系描述"""
        source_col = ", ".join(physical.source_columns)
        target_col = ", ".join(physical.target_columns)
        
        # 基于表语义生成更有意义的描述
        table_meanings = analysis_context.get("table_meanings", {})
        source_meaning = table_meanings.get(physical.source_table, {}).get("business_purpose", physical.source_table)
        target_meaning = table_meanings.get(physical.target_table, {}).get("business_purpose", physical.target_table)
        
        return f"{source_meaning}通过{source_col}字段引用{target_meaning}的{target_col}"
    
    def _infer_implicit_logical_relations(self, analysis_context: Dict[str, Any]) -> List[LogicalRelation]:
        """推断隐式逻辑关系（没有外键但可能存在业务关联）"""
        implicit_relations = []
        schema_info = analysis_context["schema_info"]
        tables = schema_info.get("tables", {})
        
        # 基于表名和字段名推断隐式关系
        table_names = list(tables.keys())
        
        for i, table1 in enumerate(table_names):
            for table2 in table_names[i+1:]:
                implicit_relation = self._check_implicit_relation(table1, table2, tables)
                if implicit_relation:
                    implicit_relations.append(implicit_relation)
        
        return implicit_relations
    
    def _check_implicit_relation(self, table1: str, table2: str, 
                               tables: Dict[str, Any]) -> LogicalRelation:
        """检查两个表之间的隐式关系"""
        # 简化实现：基于表名相似性推断
        if self._are_tables_semantically_related(table1, table2):
            return LogicalRelation(
                source_entity=table1,
                target_entity=table2,
                relation_type=RelationType.DEPENDENCY,
                cardinality=CardinalityType.MANY_TO_MANY,
                relation_name=f"{table1}_related_to_{table2}",
                description=f"{table1}与{table2}在业务上可能存在关联",
                confidence=0.3
            )
        return None
    
    def _are_tables_semantically_related(self, table1: str, table2: str) -> bool:
        """判断两个表是否在语义上相关"""
        # 简化实现：基于关键词匹配
        related_pairs = [
            (["user", "customer", "member"], ["order", "transaction", "purchase"]),
            (["product", "item", "goods"], ["order", "cart", "inventory"]),
            (["category", "type"], ["product", "item"]),
            (["address", "location"], ["user", "customer", "store"])
        ]
        
        table1_lower = table1.lower()
        table2_lower = table2.lower()
        
        for group1, group2 in related_pairs:
            if (any(kw in table1_lower for kw in group1) and 
                any(kw in table2_lower for kw in group2)) or \
               (any(kw in table1_lower for kw in group2) and 
                any(kw in table2_lower for kw in group1)):
                return True
        
        return False

    def _analyze_semantic_relations(self, analysis_context: Dict[str, Any], 
                                  logical_relations: List[LogicalRelation]) -> List[SemanticRelation]:
        """分析语义关系（概念关联）"""
        semantic_relations = []
        domain_info = analysis_context.get("domain_info", {})
        domain_type = domain_info.get("primary_domain", "unknown") if domain_info else "unknown"
        
        # 基于逻辑关系生成语义关系
        for logical in logical_relations:
            semantic = self._create_semantic_from_logical(logical, domain_type)
            if semantic:
                semantic_relations.append(semantic)
        
        # 添加基于领域的语义关系
        domain_semantics = self._generate_domain_semantic_relations(analysis_context)
        semantic_relations.extend(domain_semantics)
        
        return semantic_relations
    
    def _create_semantic_from_logical(self, logical: LogicalRelation, domain_type: str) -> SemanticRelation:
        """从逻辑关系创建语义关系"""
        # 推断语义关系类型
        semantic_type = self._infer_semantic_type(logical)
        
        # 生成业务描述
        business_description = self._generate_semantic_description(logical, semantic_type, domain_type)
        
        # 推断概念名称
        source_concept = self._infer_concept_name(logical.source_entity)
        target_concept = self._infer_concept_name(logical.target_entity)
        
        return SemanticRelation(
            source_concept=source_concept,
            target_concept=target_concept,
            semantic_type=semantic_type,
            business_description=business_description,
            domain_context=domain_type,
            strength=logical.confidence * 0.8
        )
    
    def _infer_semantic_type(self, logical: LogicalRelation) -> str:
        """推断语义关系类型"""
        source_lower = logical.source_entity.lower()
        target_lower = logical.target_entity.lower()
        
        # 包含/组成关系
        if "detail" in source_lower or "item" in source_lower:
            return "has-a"
        
        # 归属关系
        if any(kw in target_lower for kw in ["user", "customer", "owner"]):
            return "belongs-to"
        
        # 使用关系
        if any(kw in source_lower for kw in ["log", "history", "audit"]):
            return "uses"
        
        # 依赖关系
        if logical.relation_type == RelationType.DEPENDENCY:
            return "depends-on"
        
        # 默认关联关系
        return "relates-to"
    
    def _generate_semantic_description(self, logical: LogicalRelation, 
                                     semantic_type: str, domain_type: str) -> str:
        """生成语义关系描述"""
        descriptions = {
            "has-a": f"在{domain_type}领域中，{logical.source_entity}包含或拥有{logical.target_entity}的信息",
            "belongs-to": f"在{domain_type}领域中，{logical.source_entity}属于或归{logical.target_entity}所有",
            "uses": f"在{domain_type}领域中，{logical.source_entity}使用或记录{logical.target_entity}的活动",
            "depends-on": f"在{domain_type}领域中，{logical.source_entity}的存在依赖于{logical.target_entity}",
            "relates-to": f"在{domain_type}领域中，{logical.source_entity}与{logical.target_entity}存在业务关联"
        }
        return descriptions.get(semantic_type, descriptions["relates-to"])
    
    def _infer_concept_name(self, entity_name: str) -> str:
        """推断概念名称"""
        concept_mappings = {
            "user": "用户概念",
            "customer": "客户概念", 
            "order": "订单概念",
            "product": "商品概念",
            "payment": "支付概念",
            "category": "分类概念"
        }
        
        entity_lower = entity_name.lower()
        for keyword, concept in concept_mappings.items():
            if keyword in entity_lower:
                return concept
        
        return f"{entity_name}概念"
    
    def _generate_domain_semantic_relations(self, analysis_context: Dict[str, Any]) -> List[SemanticRelation]:
        """生成领域特定的语义关系"""
        domain_relations = []
        domain_info = analysis_context.get("domain_info", {})
        
        if not domain_info:
            return domain_relations
        
        primary_domain = domain_info.get("primary_domain", "")
        schema_info = analysis_context["schema_info"]
        tables = list(schema_info.get("tables", {}).keys())
        
        # 针对特定领域生成语义关系
        if primary_domain == "电商":
            domain_relations.extend(self._generate_ecommerce_semantic_relations(tables))
        elif primary_domain == "财务":
            domain_relations.extend(self._generate_finance_semantic_relations(tables))
        
        return domain_relations
    
    def _generate_ecommerce_semantic_relations(self, tables: List[str]) -> List[SemanticRelation]:
        """生成电商领域的语义关系"""
        relations = []
        
        # 查找电商相关表
        user_tables = [t for t in tables if any(kw in t.lower() for kw in ["user", "customer"])]
        product_tables = [t for t in tables if any(kw in t.lower() for kw in ["product", "item"])]
        order_tables = [t for t in tables if any(kw in t.lower() for kw in ["order", "purchase"])]
        
        # 生成领域特定关系
        if user_tables and order_tables:
            for user_table in user_tables:
                for order_table in order_tables:
                    relations.append(SemanticRelation(
                        source_concept="用户概念",
                        target_concept="订单概念",
                        semantic_type="creates",
                        business_description=f"电商领域中，用户创建和管理订单",
                        domain_context="电商",
                        strength=0.9
                    ))
        
        return relations
    
    def _generate_finance_semantic_relations(self, tables: List[str]) -> List[SemanticRelation]:
        """生成财务领域的语义关系"""
        relations = []
        
        # 查找财务相关表
        account_tables = [t for t in tables if "account" in t.lower()]
        transaction_tables = [t for t in tables if any(kw in t.lower() for kw in ["transaction", "payment"])]
        
        if account_tables and transaction_tables:
            relations.append(SemanticRelation(
                source_concept="账户概念",
                target_concept="交易概念",
                semantic_type="executes",
                business_description="财务领域中，账户执行各种交易操作",
                domain_context="财务",
                strength=0.9
            ))
        
        return relations

    def _build_relationship_matrix(self, physical_relations: List[PhysicalRelation], 
                                 logical_relations: List[LogicalRelation]) -> Dict[str, Dict[str, str]]:
        """构建关系矩阵"""
        matrix = {}
        
        # 添加物理关系
        for physical in physical_relations:
            if physical.source_table not in matrix:
                matrix[physical.source_table] = {}
            matrix[physical.source_table][physical.target_table] = "FK"
        
        # 添加逻辑关系
        for logical in logical_relations:
            if logical.source_entity not in matrix:
                matrix[logical.source_entity] = {}
            
            current = matrix[logical.source_entity].get(logical.target_entity, "")
            if current:
                matrix[logical.source_entity][logical.target_entity] = f"{current}+{logical.cardinality.value}"
            else:
                matrix[logical.source_entity][logical.target_entity] = logical.cardinality.value
        
        return matrix

    # ========== 结果构建和统计 ==========
    def _build_analysis_result(self, physical_relations: List[PhysicalRelation],
                             logical_relations: List[LogicalRelation],
                             semantic_relations: List[SemanticRelation],
                             relationship_matrix: Dict[str, Dict[str, str]],
                             analysis_context: Dict[str, Any]) -> Dict[str, Any]:
        """构建分析结果"""
        # 转换为字典格式以支持JSON序列化
        physical_dicts = self._convert_physical_to_dicts(physical_relations)
        logical_dicts = [logical.dict() for logical in logical_relations]
        semantic_dicts = [semantic.dict() for semantic in semantic_relations]
        
        # 生成统计信息
        statistics = self._calculate_relationship_statistics(
            physical_relations, logical_relations, semantic_relations
        )
        
        # 识别关键实体
        key_entities = self._identify_key_entities(physical_relations, logical_relations)
        
        domain_info = analysis_context.get("domain_info", {})
        
        return {
            "relationships": {
                "physical": physical_dicts,
                "logical": logical_dicts,
                "semantic": semantic_dicts
            },
            "entities": self._extract_entities_info(analysis_context),
            "relationship_matrix": relationship_matrix,
            "key_entities": key_entities,
            "statistics": statistics,
            "domain_context": domain_info.get("primary_domain", "unknown") if domain_info else "unknown",
            "analysis_summary": self._generate_analysis_summary(statistics, analysis_context)
        }
    
    def _convert_physical_to_dicts(self, physical_relations: List[PhysicalRelation]) -> List[Dict[str, Any]]:
        """转换物理关系为字典"""
        return [{
            "source_table": rel.source_table,
            "target_table": rel.target_table,
            "source_columns": rel.source_columns,
            "target_columns": rel.target_columns,
            "constraint_name": rel.constraint_name,
            "relation_type": rel.relation_type.value
        } for rel in physical_relations]
    
    def _calculate_relationship_statistics(self, physical_relations: List[PhysicalRelation],
                                         logical_relations: List[LogicalRelation],
                                         semantic_relations: List[SemanticRelation]) -> Dict[str, Any]:
        """计算关系统计信息"""
        return {
            "total_physical_relations": len(physical_relations),
            "total_logical_relations": len(logical_relations),
            "total_semantic_relations": len(semantic_relations),
            "has_foreign_keys": len(physical_relations) > 0,
            "relationship_density": self._calculate_relationship_density(physical_relations, logical_relations),
            "complexity_level": self._assess_relationship_complexity(physical_relations, logical_relations, semantic_relations),
            "cardinality_distribution": self._calculate_cardinality_distribution(logical_relations),
            "high_confidence_relations": len([r for r in logical_relations if r.confidence > 0.8])
        }
    
    def _calculate_relationship_density(self, physical_relations: List[PhysicalRelation],
                                      logical_relations: List[LogicalRelation]) -> float:
        """计算关系密度"""
        total_relations = len(physical_relations) + len(logical_relations)
        
        # 获取所有涉及的表数量
        all_tables = set()
        for rel in physical_relations:
            all_tables.add(rel.source_table)
            all_tables.add(rel.target_table)
        for rel in logical_relations:
            all_tables.add(rel.source_entity)
            all_tables.add(rel.target_entity)
        
        table_count = len(all_tables)
        if table_count <= 1:
            return 0.0
        
        # 可能的最大关系数（全连通图）
        max_possible_relations = table_count * (table_count - 1)
        return total_relations / max_possible_relations if max_possible_relations > 0 else 0.0
    
    def _assess_relationship_complexity(self, physical_relations: List[PhysicalRelation],
                                      logical_relations: List[LogicalRelation],
                                      semantic_relations: List[SemanticRelation]) -> str:
        """评估关系复杂度"""
        total_relations = len(physical_relations) + len(logical_relations) + len(semantic_relations)
        
        if total_relations == 0:
            return "无关系"
        elif total_relations <= 3:
            return "简单"
        elif total_relations <= 10:
            return "中等"
        elif total_relations <= 20:
            return "复杂"
        else:
            return "高度复杂"
    
    def _calculate_cardinality_distribution(self, logical_relations: List[LogicalRelation]) -> Dict[str, int]:
        """计算基数约束分布"""
        distribution = {}
        
        for relation in logical_relations:
            cardinality = relation.cardinality.value
            distribution[cardinality] = distribution.get(cardinality, 0) + 1
        
        return distribution
    
    def _identify_key_entities(self, physical_relations: List[PhysicalRelation],
                             logical_relations: List[LogicalRelation]) -> List[str]:
        """识别关键实体（关系数量最多的表）"""
        entity_counts = {}
        
        # 统计每个表的关系数量
        for rel in physical_relations:
            entity_counts[rel.source_table] = entity_counts.get(rel.source_table, 0) + 1
            entity_counts[rel.target_table] = entity_counts.get(rel.target_table, 0) + 1
        
        for rel in logical_relations:
            entity_counts[rel.source_entity] = entity_counts.get(rel.source_entity, 0) + 1
            entity_counts[rel.target_entity] = entity_counts.get(rel.target_entity, 0) + 1
        
        # 返回关系数量最多的前3个实体
        sorted_entities = sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)
        return [entity for entity, count in sorted_entities[:3] if count > 1]
    
    def _extract_entities_info(self, analysis_context: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """提取实体信息"""
        entities = {}
        schema_info = analysis_context["schema_info"]
        table_meanings = analysis_context.get("table_meanings", {})
        
        for table_name, table_info in schema_info.get("tables", {}).items():
            entity_info = {
                "name": table_name,
                "column_count": len(table_info.get("columns", [])),
                "has_primary_key": len(table_info.get("primary_keys", [])) > 0,
                "foreign_key_count": len(table_info.get("foreign_keys", [])),
                "business_purpose": table_meanings.get(table_name, {}).get("business_purpose", "")
            }
            entities[table_name] = entity_info
        
        return entities
    
    def _generate_analysis_summary(self, statistics: Dict[str, Any], 
                                 analysis_context: Dict[str, Any]) -> str:
        """生成分析摘要"""
        total_relations = (statistics["total_physical_relations"] + 
                         statistics["total_logical_relations"] + 
                         statistics["total_semantic_relations"])
        
        table_count = len(analysis_context["schema_info"].get("tables", {}))
        
        return (f"共分析{table_count}个表，发现{total_relations}个关系："
                f"{statistics['total_physical_relations']}个物理关系、"
                f"{statistics['total_logical_relations']}个逻辑关系、"
                f"{statistics['total_semantic_relations']}个语义关系，"
                f"复杂度为{statistics['complexity_level']}")
    
    async def _arun(self, include_physical: bool = True, include_logical: bool = True, 
                   include_semantic: bool = True, **kwargs) -> str:
        """异步执行（当前实现为同步）"""
        return self._run(include_physical, include_logical, include_semantic, **kwargs)