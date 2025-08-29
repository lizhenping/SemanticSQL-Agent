"""
同步版本的领域分析工具实现
"""

import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime

from tools.trae_base_tool import TraeBaseTool, ToolParameter
from config.database_models import DatabaseConfig
from database.connection_manager import DatabaseManager


class SyncDomainAnalysisTool(TraeBaseTool):
    """同步版本的领域分析工具"""
    
    def __init__(self, database_config: DatabaseConfig):
        super().__init__(
            name="analyze_domain",
            description="分析数据库的业务领域和表之间的关系"
        )
        self.database_config = database_config
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="scope",
                type="string",
                description="分析范围：'all' 全部，'core' 核心表，'specific' 特定表",
                required=False,
                default="all"
            ),
            ToolParameter(
                name="tables",
                type="array",
                description="特定表名列表（当scope='specific'时使用）",
                required=False
            )
        ]
    
    def execute(self, scope: str = "all", tables: List[str] = None) -> Dict[str, Any]:
        """执行领域分析"""
        try:
            db_manager = DatabaseManager(self.database_config)
            if not db_manager.initialize():
                return self.format_error("数据库连接失败")
            
            try:
                all_tables = db_manager.get_tables()
                
                if scope == "specific" and tables:
                    target_tables = [t for t in tables if t in all_tables]
                elif scope == "core":
                    # 识别核心表（包含用户、订单等关键业务实体的表）
                    target_tables = self._identify_core_tables(all_tables)
                else:
                    target_tables = all_tables
                
                # 分析每个表的业务含义
                domain_analysis = {
                    "scope": scope,
                    "analyzed_tables": len(target_tables),
                    "analysis": {}
                }
                
                for table_name in target_tables:
                    table_info = db_manager.get_table_info(table_name)
                    analysis = self._analyze_table_domain(table_name, table_info)
                    domain_analysis["analysis"][table_name] = analysis
                
                # 分析表之间的关系
                relationships = self._analyze_table_relationships(target_tables, db_manager)
                domain_analysis["relationships"] = relationships
                
                return self.format_result(domain_analysis)
                
            finally:
                db_manager.close()
                
        except Exception as e:
            return self.format_error(str(e))
    
    def _identify_core_tables(self, all_tables: List[str]) -> List[str]:
        """识别核心业务表"""
        core_patterns = [
            "user", "customer", "client", "member",
            "order", "purchase", "transaction", "payment",
            "product", "item", "goods", "sku",
            "category", "catalog", "brand",
            "address", "location", "region"
        ]
        
        core_tables = []
        for table in all_tables:
            table_lower = table.lower()
            for pattern in core_patterns:
                if pattern in table_lower:
                    core_tables.append(table)
                    break
        
        return core_tables[:10]  # 限制核心表数量
    
    def _analyze_table_domain(self, table_name: str, table_info: Dict[str, Any]) -> Dict[str, Any]:
        """分析单个表的业务领域"""
        table_lower = table_name.lower()
        
        # 基于表名推断业务领域
        domain_mapping = {
            "user": "用户管理",
            "customer": "客户关系",
            "order": "订单管理",
            "product": "商品管理",
            "payment": "支付系统",
            "address": "地址管理",
            "category": "分类管理",
            "inventory": "库存管理",
            "review": "评价系统",
            "cart": "购物车"
        }
        
        domain = "其他"
        for key, value in domain_mapping.items():
            if key in table_lower:
                domain = value
                break
        
        # 分析字段类型分布
        columns = table_info.get("columns", [])
        field_types = {}
        for col in columns:
            field_type = str(col.get("type", "")).split("(")[0].upper()
            field_types[field_type] = field_types.get(field_type, 0) + 1
        
        # 识别关键字段
        key_fields = []
        for col in columns:
            name = col.get("name", "").lower()
            if any(keyword in name for keyword in ["id", "name", "email", "phone", "status", "created", "updated"]):
                key_fields.append(col.get("name"))
        
        return {
            "table_name": table_name,
            "domain": domain,
            "column_count": len(columns),
            "field_types": field_types,
            "key_fields": key_fields,
            "description": f"{domain}相关的数据表"
        }
    
    def _analyze_table_relationships(self, tables: List[str], db_manager: DatabaseManager) -> Dict[str, Any]:
        """分析表之间的关系"""
        relationships = {
            "foreign_keys": [],
            "join_patterns": [],
            "hierarchy": {}
        }
        
        # 简单的关系推断
        for table1 in tables:
            for table2 in tables:
                if table1 != table2:
                    # 检查可能的关联字段
                    table1_lower = table1.lower()
                    table2_lower = table2.lower()
                    
                    # 检查外键模式
                    if table1_lower.endswith("_detail") and table2_lower.endswith("_order"):
                        relationships["join_patterns"].append({
                            "type": "detail_to_master",
                            "from": table1,
                            "to": table2,
                            "join_condition": f"{table1}.order_id = {table2}.id"
                        })
                    
                    # 检查用户关联
                    if "user" in table1_lower and "user_id" in str(db_manager.get_table_info(table2)):
                        relationships["join_patterns"].append({
                            "type": "user_related",
                            "from": table2,
                            "to": table1,
                            "join_condition": f"{table2}.user_id = {table1}.id"
                        })
        
        return relationships


class SyncFieldClassificationTool(TraeBaseTool):
    """同步版本的字段分类工具"""
    
    def __init__(self, database_config: DatabaseConfig):
        super().__init__(
            name="classify_fields",
            description="对数据库字段进行分类和分析"
        )
        self.database_config = database_config
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="table_name",
                type="string",
                description="要分析的表名，不指定则分析所有表",
                required=False
            ),
            ToolParameter(
                name="classification_type",
                type="string",
                description="分类类型：'business', 'technical', 'all'",
                required=False,
                default="all"
            )
        ]
    
    def execute(self, table_name: str = None, classification_type: str = "all") -> Dict[str, Any]:
        """执行字段分类"""
        try:
            db_manager = DatabaseManager(self.database_config)
            if not db_manager.initialize():
                return self.format_error("数据库连接失败")
            
            try:
                if table_name:
                    tables = [table_name] if table_name in db_manager.get_tables() else []
                else:
                    tables = db_manager.get_tables()
                
                classification_result = {
                    "classification_type": classification_type,
                    "analyzed_tables": len(tables),
                    "fields": {}
                }
                
                for table_name in tables:
                    table_info = db_manager.get_table_info(table_name)
                    fields = self._classify_table_fields(table_name, table_info, classification_type)
                    classification_result["fields"][table_name] = fields
                
                # 确保所有数据都是JSON可序列化的
                import json
                json.dumps(classification_result, default=str)  # 测试序列化
                
                return self.format_result(classification_result)
                
            finally:
                db_manager.close()
                
        except Exception as e:
            return self.format_error(str(e))
    
    def _classify_table_fields(self, table_name: str, table_info: Dict[str, Any], classification_type: str) -> Dict[str, Any]:
        """分类单个表的字段"""
        columns = table_info.get("columns", [])
        
        business_fields = []
        technical_fields = []
        
        for col in columns:
            field_name = col.get("name", "").lower()
            field_type = str(col.get("type", "")).lower()
            
            # 业务字段识别
            is_business = any(keyword in field_name for keyword in [
                "name", "title", "description", "price", "quantity", "status", 
                "email", "phone", "address", "date", "time", "amount"
            ])
            
            # 技术字段识别
            is_technical = any(keyword in field_name for keyword in [
                "id", "created", "updated", "deleted", "is_", "has_", "_by", "_at"
            ])
            
            field_info = {
                "name": col.get("name"),
                "type": field_type,
                "nullable": col.get("nullable", True),
                "classification": "business" if is_business else "technical" if is_technical else "neutral"
            }
            
            if classification_type in ["business", "all"] and is_business:
                business_fields.append(field_info)
            
            if classification_type in ["technical", "all"] and is_technical:
                technical_fields.append(field_info)
        
        return {
            "total_fields": len(columns),
            "business_fields": business_fields,
            "technical_fields": technical_fields,
            "business_ratio": len(business_fields) / len(columns) if columns else 0
        }


class SyncERAnalysisTool(TraeBaseTool):
    """同步版本的ER关系分析工具"""
    
    def __init__(self, database_config: DatabaseConfig):
        super().__init__(
            name="analyze_relationships",
            description="分析数据库实体关系图"
        )
        self.database_config = database_config
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="include_views",
                type="boolean",
                description="是否包含视图",
                required=False,
                default=False
            ),
            ToolParameter(
                name="depth",
                type="integer",
                description="分析深度：1-3",
                required=False,
                default=2
            )
        ]
    
    def execute(self, include_views: bool = False, depth: int = 2) -> Dict[str, Any]:
        """执行ER关系分析"""
        try:
            db_manager = DatabaseManager(self.database_config)
            if not db_manager.initialize():
                return self.format_error("数据库连接失败")
            
            try:
                tables = db_manager.get_tables()
                
                er_analysis = {
                    "entities": [],
                    "relationships": [],
                    "depth": depth,
                    "include_views": include_views
                }
                
                # 分析每个表作为实体
                for table_name in tables:
                    table_info = db_manager.get_table_info(table_name)
                    entity = self._analyze_entity(table_name, table_info)
                    er_analysis["entities"].append(entity)
                
                # 分析实体间关系
                relationships = self._analyze_relationships(er_analysis["entities"])
                er_analysis["relationships"] = relationships
                
                # 构建ER图描述
                er_description = self._build_er_description(er_analysis)
                er_analysis["description"] = er_description
                
                return self.format_result(er_analysis)
                
            finally:
                db_manager.close()
                
        except Exception as e:
            return self.format_error(str(e))
    
    def _analyze_entity(self, table_name: str, table_info: Dict[str, Any]) -> Dict[str, Any]:
        """分析表作为实体"""
        columns = table_info.get("columns", [])
        
        # 识别主键
        primary_keys = [col.get("name") for col in columns if col.get("key") == "PRI"]
        if not primary_keys:
            # 如果没有明确的主键，找id字段
            primary_keys = [col.get("name") for col in columns if "id" in col.get("name", "").lower()]
        
        # 识别外键字段
        foreign_keys = []
        for col in columns:
            col_name = col.get("name", "").lower()
            if col_name.endswith("_id") and col_name != "id":
                referenced_table = col_name.replace("_id", "")
                foreign_keys.append({
                    "field": col.get("name"),
                    "referenced_table": referenced_table,
                    "relationship_type": "many-to-one"
                })
        
        return {
            "name": table_name,
            "type": "table",
            "fields": len(columns),
            "primary_keys": primary_keys,
            "foreign_keys": foreign_keys,
            "attributes": [col.get("name") for col in columns]
        }
    
    def _analyze_relationships(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """分析实体间关系"""
        relationships = []
        
        # 基于外键分析关系
        for entity in entities:
            for fk in entity.get("foreign_keys", []):
                referenced_table = fk["referenced_table"]
                
                # 检查被引用的表是否存在
                referenced_entity = next((e for e in entities if e["name"] == referenced_table), None)
                if referenced_entity:
                    relationships.append({
                        "type": "foreign_key",
                        "from": entity["name"],
                        "to": referenced_table,
                        "from_field": fk["field"],
                        "to_field": referenced_entity["primary_keys"][0] if referenced_entity["primary_keys"] else "id",
                        "relationship_type": fk["relationship_type"],
                        "cardinality": "many-to-one"
                    })
        
        # 检查反向关系
        reverse_relationships = []
        for rel in relationships:
            reverse_relationships.append({
                "type": "reverse_foreign_key",
                "from": rel["to"],
                "to": rel["from"],
                "relationship_type": "one-to-many",
                "cardinality": "one-to-many"
            })
        
        relationships.extend(reverse_relationships)
        
        return relationships
    
    def _build_er_description(self, er_analysis: Dict[str, Any]) -> str:
        """构建ER图描述"""
        entities = er_analysis["entities"]
        relationships = er_analysis["relationships"]
        
        description = f"数据库包含 {len(entities)} 个主要实体：\n"
        
        for entity in entities:
            description += f"- {entity['name']} ({entity['fields']}个字段)\n"
        
        if relationships:
            description += f"\n实体间存在 {len(relationships)} 种关系：\n"
            for rel in relationships[:5]:  # 限制显示数量
                description += f"- {rel['from']} → {rel['to']} ({rel['relationship_type']})\n"
        
        return description


class SyncSequentialThinkingTool(TraeBaseTool):
    """同步版本的顺序思考工具"""
    
    def __init__(self, database_config: DatabaseConfig = None):
        super().__init__(
            name="sequential_thinking",
            description="用于复杂问题解决的顺序思考工具"
        )
        self.database_config = database_config
        self.thought_history = []
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="thought",
                type="string",
                description="当前思考内容",
                required=True
            ),
            ToolParameter(
                name="step_number",
                type="integer",
                description="当前步骤编号",
                required=False,
                default=1
            ),
            ToolParameter(
                name="total_steps",
                type="integer",
                description="总步骤数",
                required=False
            )
        ]
    
    def execute(self, thought: str, step_number: int = 1, total_steps: int = None) -> Dict[str, Any]:
        """执行顺序思考"""
        try:
            # 记录思考过程
            self.thought_history.append({
                "step": step_number,
                "thought": thought,
                "timestamp": datetime.now().isoformat()
            })
            
            # 分析思考内容
            analysis = self._analyze_thought(thought)
            
            result = {
                "step": step_number,
                "thought": thought,
                "analysis": analysis,
                "progress": f"{step_number}/{total_steps}" if total_steps else f"步骤 {step_number}",
                "history_length": len(self.thought_history)
            }
            
            return self.format_result(result)
            
        except Exception as e:
            return self.format_error(str(e))
    
    def _analyze_thought(self, thought: str) -> Dict[str, Any]:
        """分析思考内容"""
        thought_lower = thought.lower()
        
        # 识别思考类型
        thought_types = []
        if any(word in thought_lower for word in ["sql", "query", "select", "join"]):
            thought_types.append("database_operation")
        if any(word in thought_lower for word in ["user", "customer", "product", "order"]):
            thought_types.append("business_logic")
        if any(word in thought_lower for word in ["error", "exception", "failed"]):
            thought_types.append("error_handling")
        if any(word in thought_lower for word in ["plan", "next", "step", "approach"]):
            thought_types.append("planning")
        
        # 计算复杂度
        complexity = min(len(thought.split()) // 5 + 1, 5)
        
        return {
            "types": thought_types,
            "complexity": complexity,
            "word_count": len(thought.split()),
            "key_concepts": self._extract_key_concepts(thought)
        }
    
    def _extract_key_concepts(self, thought: str) -> List[str]:
        """提取关键概念"""
        # 简单的关键词提取
        keywords = ["SQL", "数据库", "表", "字段", "查询", "用户", "订单", "产品"]
        concepts = []
        
        for keyword in keywords:
            if keyword.lower() in thought.lower():
                concepts.append(keyword)
        
        return concepts[:5]  # 限制数量