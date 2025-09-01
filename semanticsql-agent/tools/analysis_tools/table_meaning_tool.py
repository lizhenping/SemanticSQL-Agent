"""
表业务含义分析工具
分析数据库表的业务用途、实体类型和关系
"""

from typing import Dict, Any, Type, List
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from models.exceptions import ToolExecutionError


class TableMeaningInput(BaseModel):
    """表含义分析输入"""
    memory: Dict[str, Any] = Field(description="包含数据库分析结果的记忆")


class TableMeaningTool(BaseTool):
    """分析数据库表的业务含义"""
    
    name: str = "table_meaning_analysis"
    description: str = "分析数据库表的业务含义，识别表的业务用途、实体类型和表间关系"
    args_schema: Type[BaseModel] = TableMeaningInput
    
    def _run(self, memory: Dict[str, Any]) -> Dict[str, Any]:
        """执行表含义分析"""
        try:
            # 从记忆中获取必要信息
            db_analysis = memory.get("db_analysis", {})
            schema_info = db_analysis.get("schema_info", {})
            domain_info = db_analysis.get("domain_info", {})
            er_relations = db_analysis.get("er_relations", {})
            
            if not schema_info:
                raise ToolExecutionError(
                    tool_name=self.name,
                    reason="未找到数据库结构信息，请先执行schema_extraction"
                )
            
            table_purposes = {}
            table_relationships = {}
            business_entities = {}
            
            # 分析每个表
            tables = schema_info.get("tables", {})
            for table_name, table_info in tables.items():
                # 分析表的业务用途
                purpose = self._analyze_table_purpose(
                    table_name, table_info, domain_info
                )
                table_purposes[table_name] = purpose
                
                # 识别业务实体
                entity_type = self._identify_entity_type(
                    table_name, table_info, purpose
                )
                if entity_type:
                    business_entities[table_name] = entity_type
                
                # 分析表间关系
                relationships = self._analyze_table_relationships(
                    table_name, table_info, er_relations
                )
                if relationships:
                    table_relationships[table_name] = relationships
            
            return {
                "table_purposes": table_purposes,
                "table_relationships": table_relationships,
                "business_entities": business_entities,
                "entity_hierarchy": self._build_entity_hierarchy(business_entities, table_relationships),
                "analysis_summary": self._generate_summary(table_purposes, business_entities)
            }
            
        except Exception as e:
            raise ToolExecutionError(
                tool_name=self.name,
                reason=f"表含义分析失败: {str(e)}"
            )
    
    def _analyze_table_purpose(
        self, 
        table_name: str,
        table_info: Dict[str, Any],
        domain_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """分析表的业务用途"""
        purpose = {
            "table_name": table_name,
            "business_purpose": "",
            "entity_type": "",
            "data_category": "",
            "importance_level": "medium",
            "description": ""
        }
        
        table_lower = table_name.lower()
        primary_domain = domain_info.get("primary_domain", "")
        
        # 基于表名模式识别用途
        # 用户相关表
        if any(term in table_lower for term in ["user", "member", "customer", "account"]):
            purpose["business_purpose"] = "用户信息管理"
            purpose["entity_type"] = "主数据"
            purpose["data_category"] = "用户数据"
            purpose["importance_level"] = "high"
            purpose["description"] = "存储系统用户或客户的基本信息"
        
        # 订单相关表
        elif any(term in table_lower for term in ["order", "transaction", "payment"]):
            purpose["business_purpose"] = "交易记录管理"
            purpose["entity_type"] = "交易数据"
            purpose["data_category"] = "业务数据"
            purpose["importance_level"] = "high"
            purpose["description"] = "记录业务交易和支付信息"
        
        # 产品相关表
        elif any(term in table_lower for term in ["product", "item", "goods", "service"]):
            purpose["business_purpose"] = "产品信息管理"
            purpose["entity_type"] = "主数据"
            purpose["data_category"] = "产品数据"
            purpose["importance_level"] = "high"
            purpose["description"] = "存储产品或服务的详细信息"
        
        # 日志相关表
        elif any(term in table_lower for term in ["log", "history", "record", "audit"]):
            purpose["business_purpose"] = "日志记录"
            purpose["entity_type"] = "日志数据"
            purpose["data_category"] = "系统数据"
            purpose["importance_level"] = "low"
            purpose["description"] = "记录系统操作和变更历史"
        
        # 配置相关表
        elif any(term in table_lower for term in ["config", "setting", "parameter"]):
            purpose["business_purpose"] = "系统配置"
            purpose["entity_type"] = "配置数据"
            purpose["data_category"] = "系统数据"
            purpose["importance_level"] = "medium"
            purpose["description"] = "存储系统配置和参数设置"
        
        # 关联表（多对多）
        elif table_lower.count("_") >= 2 and any(term in table_lower for term in ["_to_", "_x_", "_rel_"]):
            purpose["business_purpose"] = "关系映射"
            purpose["entity_type"] = "关联数据"
            purpose["data_category"] = "关系数据"
            purpose["importance_level"] = "medium"
            purpose["description"] = "维护实体间的多对多关系"
        
        # 基于列特征进一步分析
        columns = table_info.get("columns", [])
        column_names = [col["name"].lower() for col in columns]
        
        # 如果有created_at/updated_at，可能是业务实体
        if any("created" in col for col in column_names) and any("updated" in col for col in column_names):
            if not purpose["entity_type"]:
                purpose["entity_type"] = "业务实体"
                purpose["importance_level"] = "medium"
        
        return purpose
    
    def _identify_entity_type(
        self, 
        table_name: str,
        table_info: Dict[str, Any],
        purpose: Dict[str, Any]
    ) -> Dict[str, Any]:
        """识别业务实体类型"""
        entity_type = purpose.get("entity_type", "")
        
        if not entity_type or entity_type == "业务实体":
            # 基于表结构特征判断
            columns = table_info.get("columns", [])
            has_id = any(col["name"].lower() in ["id", f"{table_name}_id"] for col in columns)
            has_timestamps = any("created" in col["name"].lower() for col in columns)
            
            if has_id and has_timestamps:
                entity_type = "核心实体"
            elif has_id:
                entity_type = "参考数据"
            else:
                entity_type = "辅助数据"
        
        return {
            "entity_type": entity_type,
            "entity_category": purpose.get("data_category", ""),
            "is_master_data": entity_type in ["主数据", "核心实体"],
            "is_transactional": entity_type in ["交易数据", "日志数据"]
        }
    
    def _analyze_table_relationships(
        self, 
        table_name: str,
        table_info: Dict[str, Any],
        er_relations: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """分析表间关系"""
        relationships = []
        
        # 从ER关系中查找
        if er_relations:
            table_relations = er_relations.get("relationships", {}).get(table_name, [])
            for rel in table_relations:
                relationships.append({
                    "related_table": rel.get("to_table", ""),
                    "relationship_type": rel.get("type", ""),
                    "foreign_key": rel.get("foreign_key", ""),
                    "description": rel.get("description", "")
                })
        
        # 基于外键列分析
        columns = table_info.get("columns", [])
        for col in columns:
            col_name = col["name"].lower()
            if col_name.endswith("_id") and col_name != "id":
                potential_table = col_name[:-3]
                # 检查是否已经在relationships中
                if not any(rel["related_table"] == potential_table for rel in relationships):
                    relationships.append({
                        "related_table": potential_table,
                        "relationship_type": "many-to-one",
                        "foreign_key": col["name"],
                        "description": f"References {potential_table} table"
                    })
        
        return relationships
    
    def _build_entity_hierarchy(
        self, 
        business_entities: Dict[str, Any],
        table_relationships: Dict[str, Any]
    ) -> Dict[str, Any]:
        """构建实体层次结构"""
        hierarchy = {
            "master_entities": [],
            "transactional_entities": [],
            "reference_entities": [],
            "auxiliary_entities": []
        }
        
        for table_name, entity_info in business_entities.items():
            entity_type = entity_info.get("entity_type", "")
            
            if entity_info.get("is_master_data"):
                hierarchy["master_entities"].append(table_name)
            elif entity_info.get("is_transactional"):
                hierarchy["transactional_entities"].append(table_name)
            elif entity_type == "参考数据":
                hierarchy["reference_entities"].append(table_name)
            else:
                hierarchy["auxiliary_entities"].append(table_name)
        
        return hierarchy
    
    def _generate_summary(
        self, 
        table_purposes: Dict[str, Any],
        business_entities: Dict[str, Any]
    ) -> str:
        """生成分析摘要"""
        total_tables = len(table_purposes)
        master_data_count = sum(
            1 for e in business_entities.values() 
            if e.get("is_master_data")
        )
        transactional_count = sum(
            1 for e in business_entities.values() 
            if e.get("is_transactional")
        )
        
        summary = f"分析完成：共分析了{total_tables}个表，"
        summary += f"其中主数据表{master_data_count}个，"
        summary += f"交易数据表{transactional_count}个。"
        
        return summary
    
    async def _arun(self, memory: Dict[str, Any]) -> Dict[str, Any]:
        """异步执行（当前实现为同步）"""
        return self._run(memory)