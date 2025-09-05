"""
表语义分析工具 - 优化版本
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
class TableAnalysisInput(BaseModel):
    """表语义分析输入参数"""
    include_relationships: bool = Field(default=True, description="是否分析表间关系")
    include_entity_types: bool = Field(default=True, description="是否推断实体类型")


class EntityType(str, Enum):
    """实体类型枚举"""
    MASTER = "master"            # 主数据表（用户、商品等）
    TRANSACTION = "transaction"  # 交易表（订单、付款等）
    DETAIL = "detail"            # 明细表（订单明细等）
    LOOKUP = "lookup"            # 字典表（分类、状态等）
    LOG = "log"                  # 日志表
    CONFIG = "config"            # 配置表
    BRIDGE = "bridge"            # 关联表（多对多关系）
    OTHER = "other"              # 其他


class TableClassificationRule(BaseModel):
    """表分类规则"""
    name_patterns: List[str]
    entity_type: EntityType
    purpose_template: str
    confidence: float = 0.8
    keywords: List[str] = Field(default_factory=list)


@dataclass
class TableContext:
    """表上下文信息"""
    table_name: str
    column_count: int
    primary_keys: List[str]
    foreign_keys: List[Dict[str, Any]]
    column_names: List[str]
    sample_data_count: int
    comment: str = ""
    domain_type: str = "unknown"


class TableMeaningResult(BaseModel):
    """表语义分析结果"""
    table_name: str
    entity_type: EntityType
    business_purpose: str
    core_responsibility: str
    relationships: List[str]
    importance_level: str  # critical, high, medium, low
    analysis_confidence: float


class TableAnalysisTool(BaseSemanticSQLTool):
    """表语义分析工具 - 优化版本
    
    职责：
    - 分析每个表的业务职责和实体类型
    - 推断表间关系和业务依赖
    - 评估表的重要性和核心度
    
    设计原则：
    - 单一职责：专注表语义分析
    - 方法拆分：每个方法<30行
    - 类型安全：使用枚举和Pydantic模型
    - 简化异常：让异常自然传播
    """
    
    name: str = "table_analysis"
    description: str = "分析数据库表的业务职责、实体类型和表间关系"
    args_schema: Type[BaseModel] = TableAnalysisInput
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, 'prompt_manager', PromptManager())
        object.__setattr__(self, '_classification_rules', self._initialize_classification_rules())
    
    def _run(self, include_relationships: bool = True, include_entity_types: bool = True, **kwargs) -> str:
        """执行表语义分析 - 主流程"""
        # 获取分析上下文
        analysis_context = self._gather_analysis_context()
        
        # 提取表上下文信息
        table_contexts = self._extract_table_contexts(analysis_context)
        
        # 分析表语义
        table_meanings = self._analyze_table_meanings(table_contexts, include_entity_types)
        
        # 分析表间关系
        if include_relationships:
            table_relationships = self._analyze_table_relationships(table_contexts, table_meanings)
        else:
            table_relationships = []
        
        # 构建分析结果
        result = self._build_analysis_result(table_meanings, table_relationships, analysis_context)
        
        # 保存并返回
        self.save_to_memory("table_meanings", result)
        return json.dumps(result, ensure_ascii=False)
    
    # ========== 核心分析逻辑 ==========
    def _gather_analysis_context(self) -> Dict[str, Any]:
        """获取分析上下文"""
        context = {
            "schema_info": self.get_from_memory("schema_extraction"),
            "domain_info": self.get_from_memory("domain_analysis"),
            "column_meanings": self.get_from_memory("column_meanings")
        }
        
        if not context["schema_info"]:
            raise ToolExecutionError(
                tool_name=self.name,
                reason="无法获取数据库结构信息，需要先运行schema_extraction工具"
            )
        
        return context
    
    def _initialize_classification_rules(self) -> List[TableClassificationRule]:
        """初始化表分类规则"""
        return [
            # 主数据表
            TableClassificationRule(
                name_patterns=["user", "customer", "client", "member", "person"],
                entity_type=EntityType.MASTER,
                purpose_template="主数据表，存储{name}的基础信息和核心属性",
                confidence=0.9
            ),
            TableClassificationRule(
                name_patterns=["product", "item", "goods", "commodity", "article"],
                entity_type=EntityType.MASTER,
                purpose_template="商品主数据表，管理{name}的基本信息和属性",
                confidence=0.9
            ),
            # 交易表
            TableClassificationRule(
                name_patterns=["order", "transaction", "payment", "purchase", "sale"],
                entity_type=EntityType.TRANSACTION,
                purpose_template="交易记录表，记录{name}相关的业务交易和状态信息",
                confidence=0.95
            ),
            # 明细表
            TableClassificationRule(
                name_patterns=["_detail", "_item", "line_item", "detail"],
                entity_type=EntityType.DETAIL,
                purpose_template="明细数据表，存储{name}的具体明细和子项信息",
                confidence=0.9
            ),
            # 字典表
            TableClassificationRule(
                name_patterns=["category", "type", "status", "dict", "lookup", "ref"],
                entity_type=EntityType.LOOKUP,
                purpose_template="字典/参考表，维护{name}的分类和码表信息",
                confidence=0.85
            ),
            # 日志表
            TableClassificationRule(
                name_patterns=["log", "audit", "history", "trace", "event"],
                entity_type=EntityType.LOG,
                purpose_template="日志记录表，记录{name}相关的操作日志和历史信息",
                confidence=0.9
            ),
            # 配置表
            TableClassificationRule(
                name_patterns=["config", "setting", "param", "option"],
                entity_type=EntityType.CONFIG,
                purpose_template="配置参数表，管理{name}相关的系统配置和设置",
                confidence=0.85
            ),
            # 关联表
            TableClassificationRule(
                name_patterns=["_rel", "_map", "_link", "mapping"],
                entity_type=EntityType.BRIDGE,
                purpose_template="关联映射表，维护{name}之间的多对多关系",
                confidence=0.8
            )
        ]
    
    def _extract_table_contexts(self, analysis_context: Dict[str, Any]) -> List[TableContext]:
        """提取表上下文信息"""
        table_contexts = []
        schema_info = analysis_context["schema_info"]
        domain_info = analysis_context.get("domain_info", {})
        
        tables = schema_info.get("tables", {})
        domain_type = domain_info.get("primary_domain", "unknown") if domain_info else "unknown"
        
        for table_name, table_info in tables.items():
            context = TableContext(
                table_name=table_name,
                column_count=len(table_info.get("columns", [])),
                primary_keys=table_info.get("primary_keys", []),
                foreign_keys=table_info.get("foreign_keys", []),
                column_names=[col.get("name", "") for col in table_info.get("columns", [])],
                sample_data_count=len(table_info.get("sample_data", [])),
                comment=table_info.get("comment", ""),
                domain_type=domain_type
            )
            table_contexts.append(context)
        
        return table_contexts
    
    def _analyze_table_meanings(self, table_contexts: List[TableContext], include_entity_types: bool) -> List[TableMeaningResult]:
        """分析表语义"""
        table_meanings = []
        
        for context in table_contexts:
            meaning_result = self._analyze_single_table_meaning(context, include_entity_types)
            table_meanings.append(meaning_result)
        
        return table_meanings
    
    def _analyze_single_table_meaning(self, context: TableContext, include_entity_types: bool) -> TableMeaningResult:
        """分析单个表的语义"""
        # 匹配分类规则
        rule_match = self._find_matching_classification_rule(context)
        
        if rule_match:
            rule, confidence = rule_match
            entity_type = rule.entity_type
            business_purpose = rule.purpose_template.format(name=context.table_name)
            source = "rule_based"
        else:
            # 默认分析
            entity_type, business_purpose, confidence, source = self._create_default_table_meaning(context)
        
        # 生成核心职责
        core_responsibility = self._generate_core_responsibility(context, entity_type)
        
        # 评估重要性
        importance_level = self._assess_table_importance(context, entity_type)
        
        # 初始化关系列表（将在后续步骤中填充）
        relationships = []
        
        return TableMeaningResult(
            table_name=context.table_name,
            entity_type=entity_type,
            business_purpose=business_purpose,
            core_responsibility=core_responsibility,
            relationships=relationships,
            importance_level=importance_level,
            analysis_confidence=confidence
        )
    
    def _find_matching_classification_rule(self, context: TableContext) -> Tuple[TableClassificationRule, float]:
        """找到匹配的分类规则"""
        table_name_lower = context.table_name.lower()
        
        for rule in self._classification_rules:
            for pattern in rule.name_patterns:
                if pattern in table_name_lower:
                    return rule, rule.confidence
        
        return None
    
    def _create_default_table_meaning(self, context: TableContext) -> Tuple[EntityType, str, float, str]:
        """创建默认表语义（未匹配到规则时）"""
        # 基于表结构特征推断实体类型
        if len(context.foreign_keys) > len(context.primary_keys) and len(context.foreign_keys) >= 2:
            # 多个外键，可能是关联表
            entity_type = EntityType.BRIDGE
            purpose = f"关联表，维护{context.table_name}相关实体间的关系"
        elif "_detail" in context.table_name.lower() or "_item" in context.table_name.lower():
            entity_type = EntityType.DETAIL
            purpose = f"明细表，存储{context.table_name}的具体明细信息"
        elif any(col_name.lower().endswith("_time") or col_name.lower().endswith("_date") 
                 for col_name in context.column_names):
            # 包含时间字段，可能是交易表
            entity_type = EntityType.TRANSACTION
            purpose = f"事务记录表，记录{context.table_name}的业务操作和状态变化"
        elif context.column_count <= 5 and any("name" in col_name.lower() 
                                                for col_name in context.column_names):
            # 少量列且包含名称，可能是字典表
            entity_type = EntityType.LOOKUP
            purpose = f"字典表，维护{context.table_name}的分类和码表信息"
        else:
            # 默认为主数据表
            entity_type = EntityType.MASTER
            purpose = f"主数据表，管理{context.table_name}的核心信息和属性"
        
        return entity_type, purpose, 0.4, "structure_inference"
    
    def _generate_core_responsibility(self, context: TableContext, entity_type: EntityType) -> str:
        """生成核心职责描述"""
        responsibilities = {
            EntityType.MASTER: f"维护{context.table_name}的主数据和核心属性，作为其他表的参考数据",
            EntityType.TRANSACTION: f"记录{context.table_name}的业务交易和状态变化，支持业务流程执行",
            EntityType.DETAIL: f"存储{context.table_name}的详细信息和子项数据，支持精细化管理",
            EntityType.LOOKUP: f"提供{context.table_name}的对照和分类数据，支持码表管理",
            EntityType.LOG: f"记录{context.table_name}的操作日志和历史信息，支持审计和追踪",
            EntityType.CONFIG: f"维护{context.table_name}的系统参数和配置，支持系统灵活性",
            EntityType.BRIDGE: f"维护{context.table_name}之间的多对多关系，支持复杂关联查询",
            EntityType.OTHER: f"支持{context.domain_type}领域中{context.table_name}的业务功能"
        }
        return responsibilities.get(entity_type, responsibilities[EntityType.OTHER])
    
    def _assess_table_importance(self, context: TableContext, entity_type: EntityType) -> str:
        """评估表重要性"""
        # 基于实体类型的重要性
        if entity_type in [EntityType.MASTER, EntityType.TRANSACTION]:
            return "critical"
        elif entity_type == EntityType.DETAIL:
            return "high"
        elif entity_type in [EntityType.LOOKUP, EntityType.CONFIG]:
            return "medium"
        else:
            return "low"
    
    def _analyze_table_relationships(self, table_contexts: List[TableContext], table_meanings: List[TableMeaningResult]) -> List[Dict[str, Any]]:
        """分析表间关系"""
        relationships = []
        
        # 按表名组织表上下文
        context_map = {ctx.table_name: ctx for ctx in table_contexts}
        
        for context in table_contexts:
            for fk in context.foreign_keys:
                referred_table = fk.get("referred_table", "")
                if referred_table in context_map:
                    relationship = {
                        "source_table": context.table_name,
                        "target_table": referred_table,
                        "relationship_type": "foreign_key",
                        "description": f"{context.table_name}引用{referred_table}的数据",
                        "columns": {
                            "source": fk.get("constrained_columns", []),
                            "target": fk.get("referred_columns", [])
                        }
                    }
                    relationships.append(relationship)
        
        return relationships
    
    # ========== 结果构建和统计 ==========
    def _build_analysis_result(self, table_meanings: List[TableMeaningResult], 
                             table_relationships: List[Dict[str, Any]], 
                             analysis_context: Dict[str, Any]) -> Dict[str, Any]:
        """构建分析结果"""
        # 更新表语义中的关系信息
        table_meanings_with_relationships = self._update_table_relationships(table_meanings, table_relationships)
        
        # 按表组织语义信息
        table_meanings_dict = self._organize_table_meanings(table_meanings_with_relationships)
        
        # 计算统计信息
        statistics = self._calculate_table_statistics(table_meanings_with_relationships)
        
        # 识别核心表
        core_tables = self._identify_core_tables(table_meanings_with_relationships)
        
        domain_info = analysis_context.get("domain_info", {})
        
        return {
            "table_meanings": table_meanings_dict,
            "table_relationships": table_relationships,
            "core_tables": core_tables,
            "statistics": statistics,
            "domain_context": domain_info.get("primary_domain", "unknown") if domain_info else "unknown",
            "total_tables": len(table_meanings_with_relationships),
            "analysis_summary": f"共分析{len(table_meanings_with_relationships)}个表，识别出{len(core_tables)}个核心表，{len(table_relationships)}个表间关系"
        }
    
    def _update_table_relationships(self, table_meanings: List[TableMeaningResult], 
                                  table_relationships: List[Dict[str, Any]]) -> List[TableMeaningResult]:
        """更新表语义中的关系信息"""
        # 为每个表收集关系信息
        table_relations = {}
        for rel in table_relationships:
            source = rel["source_table"]
            target = rel["target_table"]
            
            if source not in table_relations:
                table_relations[source] = []
            table_relations[source].append(f"引用 {target}")
            
            if target not in table_relations:
                table_relations[target] = []
            table_relations[target].append(f"被 {source} 引用")
        
        # 更新表语义对象
        updated_meanings = []
        for meaning in table_meanings:
            relationships = table_relations.get(meaning.table_name, [])
            # 创建新对象（Pydantic模型不可变）
            updated_meaning = TableMeaningResult(
                table_name=meaning.table_name,
                entity_type=meaning.entity_type,
                business_purpose=meaning.business_purpose,
                core_responsibility=meaning.core_responsibility,
                relationships=relationships,
                importance_level=meaning.importance_level,
                analysis_confidence=meaning.analysis_confidence
            )
            updated_meanings.append(updated_meaning)
        
        return updated_meanings
    
    def _organize_table_meanings(self, table_meanings: List[TableMeaningResult]) -> Dict[str, Any]:
        """按表组织表语义"""
        result = {}
        
        for meaning in table_meanings:
            result[meaning.table_name] = {
                "entity_type": meaning.entity_type.value,
                "business_purpose": meaning.business_purpose,
                "core_responsibility": meaning.core_responsibility,
                "relationships": meaning.relationships,
                "importance_level": meaning.importance_level,
                "analysis_confidence": meaning.analysis_confidence
            }
        
        return result
    
    def _calculate_table_statistics(self, table_meanings: List[TableMeaningResult]) -> Dict[str, Any]:
        """计算表统计信息"""
        entity_type_counts = {}
        importance_counts = {}
        
        for meaning in table_meanings:
            # 实体类型统计
            entity_type = meaning.entity_type.value
            entity_type_counts[entity_type] = entity_type_counts.get(entity_type, 0) + 1
            
            # 重要性统计
            importance = meaning.importance_level
            importance_counts[importance] = importance_counts.get(importance, 0) + 1
        
        return {
            "entity_type_distribution": entity_type_counts,
            "importance_distribution": importance_counts,
            "high_confidence_count": len([m for m in table_meanings if m.analysis_confidence > 0.8])
        }
    
    def _identify_core_tables(self, table_meanings: List[TableMeaningResult]) -> List[str]:
        """识别核心表"""
        core_tables = []
        
        for meaning in table_meanings:
            if meaning.importance_level in ["critical", "high"]:
                core_tables.append(meaning.table_name)
        
        return core_tables
    
    async def _arun(self, include_relationships: bool = True, include_entity_types: bool = True, **kwargs) -> str:
        """异步执行（当前实现为同步）"""
        return self._run(include_relationships, include_entity_types, **kwargs)
