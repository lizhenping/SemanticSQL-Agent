"""
领域分析工具 - 分析数据库的业务领域
"""

from typing import Dict, Any, List, Optional
import re

from tools.base_tool import BaseTool, ToolParameter


class DomainAnalysisTool(BaseTool):
    """业务领域分析工具"""
    
    @property
    def name(self) -> str:
        return "analyze_domain"
    
    @property
    def description(self) -> str:
        return "分析数据库的业务领域，识别主要业务场景"
    
    @property
    def category(self) -> str:
        return "analysis"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="schema_info",
                type="object",
                description="数据库结构信息",
                required=True
            ),
            ToolParameter(
                name="sample_data",
                type="object",
                description="各表的样本数据",
                required=False,
                default={}
            )
        ]
    
    def _execute(self, schema_info: Dict[str, Any], 
                 sample_data: Dict[str, List] = None) -> Dict[str, Any]:
        """
        执行领域分析
        """
        result = {
            "primary_domain": "",
            "sub_domains": [],
            "business_entities": {},
            "business_processes": [],
            "data_characteristics": {},
            "domain_confidence": 0.0,
            "recommendations": []
        }
        
        tables = schema_info.get("tables", {})
        
        # 分析主要领域
        domain_scores = self._analyze_domain_patterns(tables)
        if domain_scores:
            primary = max(domain_scores, key=domain_scores.get)
            result["primary_domain"] = primary
            result["domain_confidence"] = domain_scores[primary]
            result["sub_domains"] = [d for d in domain_scores if d != primary][:3]
        
        # 识别业务实体
        result["business_entities"] = self._identify_business_entities(tables)
        
        # 识别业务流程
        result["business_processes"] = self._identify_business_processes(
            tables, result["business_entities"]
        )
        
        # 分析数据特征
        result["data_characteristics"] = self._analyze_data_characteristics(
            tables, sample_data
        )
        
        # 生成建议
        result["recommendations"] = self._generate_domain_recommendations(result)
        
        return result
    
    def _analyze_domain_patterns(self, tables: Dict[str, Any]) -> Dict[str, float]:
        """分析领域模式"""
        domain_patterns = {
            "电商": ["product", "order", "cart", "payment", "customer", "inventory", "shop"],
            "金融": ["account", "transaction", "balance", "payment", "invoice", "credit", "loan"],
            "社交": ["user", "friend", "post", "comment", "like", "follow", "message"],
            "教育": ["student", "teacher", "course", "class", "exam", "score", "enrollment"],
            "医疗": ["patient", "doctor", "appointment", "prescription", "diagnosis", "treatment"],
            "物流": ["shipment", "delivery", "warehouse", "tracking", "carrier", "route"],
            "人力资源": ["employee", "department", "salary", "attendance", "leave", "recruitment"],
            "CRM": ["customer", "lead", "opportunity", "contact", "campaign", "deal"],
            "库存管理": ["inventory", "stock", "warehouse", "supplier", "purchase", "material"],
            "内容管理": ["article", "page", "category", "tag", "media", "content", "publish"]
        }
        
        scores = {}
        table_names = [name.lower() for name in tables.keys()]
        all_columns = []
        for table_info in tables.values():
            all_columns.extend([col["name"].lower() for col in table_info.get("columns", [])])
        
        for domain, keywords in domain_patterns.items():
            score = 0
            matches = 0
            
            for keyword in keywords:
                # 检查表名
                for table_name in table_names:
                    if keyword in table_name:
                        score += 2
                        matches += 1
                
                # 检查列名
                for column in all_columns:
                    if keyword in column:
                        score += 1
                        matches += 1
            
            if matches > 0:
                # 归一化分数
                scores[domain] = min(score / len(keywords) * 100, 100)
        
        return scores
    
    def _identify_business_entities(self, tables: Dict[str, Any]) -> Dict[str, Dict]:
        """识别业务实体"""
        entities = {}
        
        for table_name, table_info in tables.items():
            entity_type = self._classify_business_entity(table_name, table_info)
            
            if entity_type != "unknown":
                entities[table_name] = {
                    "type": entity_type,
                    "attributes": [col["name"] for col in table_info.get("columns", [])],
                    "key_field": self._find_key_field(table_info),
                    "relationships": len(table_info.get("foreign_keys", [])),
                    "importance": self._calculate_importance(table_info)
                }
        
        return entities
    
    def _classify_business_entity(self, table_name: str, table_info: Dict) -> str:
        """分类业务实体"""
        name_lower = table_name.lower()
        
        # 核心业务实体
        if any(word in name_lower for word in ["user", "customer", "member", "client"]):
            return "actor"
        elif any(word in name_lower for word in ["product", "item", "service", "goods"]):
            return "product"
        elif any(word in name_lower for word in ["order", "transaction", "purchase", "sale"]):
            return "transaction"
        elif any(word in name_lower for word in ["payment", "invoice", "receipt", "bill"]):
            return "financial"
        
        # 辅助实体
        elif any(word in name_lower for word in ["category", "type", "status", "config"]):
            return "reference"
        elif any(word in name_lower for word in ["log", "history", "audit", "track"]):
            return "audit"
        elif "_" in name_lower and any(word in name_lower for word in ["map", "rel", "link"]):
            return "relationship"
        
        return "entity"
    
    def _find_key_field(self, table_info: Dict) -> Optional[str]:
        """查找主键字段"""
        for col in table_info.get("columns", []):
            if col.get("is_primary"):
                return col["name"]
        return None
    
    def _calculate_importance(self, table_info: Dict) -> float:
        """计算实体重要性"""
        score = 0.0
        
        # 有主键更重要
        if any(col.get("is_primary") for col in table_info.get("columns", [])):
            score += 3
        
        # 外键关系
        score += len(table_info.get("foreign_keys", [])) * 2
        
        # 字段数量
        score += min(len(table_info.get("columns", [])) * 0.5, 5)
        
        # 索引
        score += len(table_info.get("indexes", [])) * 0.5
        
        return min(score, 10)
    
    def _identify_business_processes(self, tables: Dict[str, Any],
                                    entities: Dict[str, Dict]) -> List[Dict]:
        """识别业务流程"""
        processes = []
        
        # 查找事务性表
        transaction_tables = [
            name for name, entity in entities.items()
            if entity["type"] in ["transaction", "financial"]
        ]
        
        for trans_table in transaction_tables:
            process = {
                "name": self._infer_process_name(trans_table),
                "main_entity": trans_table,
                "participants": self._find_process_participants(
                    trans_table, tables[trans_table], entities
                ),
                "type": self._classify_process_type(trans_table),
                "complexity": "simple"
            }
            
            # 评估复杂度
            if len(process["participants"]) > 3:
                process["complexity"] = "complex"
            elif len(process["participants"]) > 1:
                process["complexity"] = "moderate"
            
            processes.append(process)
        
        return processes
    
    def _infer_process_name(self, table_name: str) -> str:
        """推断流程名称"""
        name_lower = table_name.lower()
        
        if "order" in name_lower:
            return "订单处理流程"
        elif "payment" in name_lower:
            return "支付流程"
        elif "delivery" in name_lower or "shipment" in name_lower:
            return "配送流程"
        elif "registration" in name_lower or "signup" in name_lower:
            return "注册流程"
        elif "transaction" in name_lower:
            return "交易流程"
        else:
            return f"{table_name}流程"
    
    def _find_process_participants(self, table_name: str, table_info: Dict,
                                  entities: Dict[str, Dict]) -> List[str]:
        """查找流程参与者"""
        participants = []
        
        # 通过外键找相关实体
        for fk in table_info.get("foreign_keys", []):
            ref_table = fk.get("referenced_table")
            if ref_table and ref_table in entities:
                participants.append(ref_table)
        
        return participants
    
    def _classify_process_type(self, table_name: str) -> str:
        """分类流程类型"""
        name_lower = table_name.lower()
        
        if any(word in name_lower for word in ["order", "purchase", "sale"]):
            return "transactional"
        elif any(word in name_lower for word in ["payment", "invoice", "bill"]):
            return "financial"
        elif any(word in name_lower for word in ["delivery", "shipment"]):
            return "logistical"
        elif any(word in name_lower for word in ["registration", "enrollment"]):
            return "onboarding"
        else:
            return "operational"
    
    def _analyze_data_characteristics(self, tables: Dict[str, Any],
                                     sample_data: Dict[str, List] = None) -> Dict:
        """分析数据特征"""
        characteristics = {
            "table_count": len(tables),
            "total_columns": sum(len(t.get("columns", [])) for t in tables.values()),
            "has_timestamps": False,
            "has_soft_delete": False,
            "has_versioning": False,
            "has_multi_tenant": False,
            "common_patterns": []
        }
        
        # 检查时间戳字段
        timestamp_patterns = ["created", "updated", "modified", "_at", "_time"]
        soft_delete_patterns = ["deleted", "is_active", "status"]
        version_patterns = ["version", "revision", "_v"]
        tenant_patterns = ["tenant", "org", "company", "client_id"]
        
        for table_info in tables.values():
            columns = [col["name"].lower() for col in table_info.get("columns", [])]
            
            # 检查模式
            if any(any(pattern in col for pattern in timestamp_patterns) for col in columns):
                characteristics["has_timestamps"] = True
            
            if any(any(pattern in col for pattern in soft_delete_patterns) for col in columns):
                characteristics["has_soft_delete"] = True
            
            if any(any(pattern in col for pattern in version_patterns) for col in columns):
                characteristics["has_versioning"] = True
            
            if any(any(pattern in col for pattern in tenant_patterns) for col in columns):
                characteristics["has_multi_tenant"] = True
        
        # 识别通用模式
        if characteristics["has_timestamps"]:
            characteristics["common_patterns"].append("审计追踪")
        if characteristics["has_soft_delete"]:
            characteristics["common_patterns"].append("软删除")
        if characteristics["has_versioning"]:
            characteristics["common_patterns"].append("版本控制")
        if characteristics["has_multi_tenant"]:
            characteristics["common_patterns"].append("多租户")
        
        return characteristics
    
    def _generate_domain_recommendations(self, analysis_result: Dict) -> List[str]:
        """生成领域相关建议"""
        recommendations = []
        
        # 基于领域的建议
        domain = analysis_result.get("primary_domain", "")
        if domain == "电商":
            recommendations.append("建议添加库存管理、促销活动等电商核心功能表")
        elif domain == "金融":
            recommendations.append("建议加强数据加密和审计日志功能")
        elif domain == "社交":
            recommendations.append("建议优化用户关系表和消息表的索引")
        
        # 基于数据特征的建议
        characteristics = analysis_result.get("data_characteristics", {})
        if not characteristics.get("has_timestamps"):
            recommendations.append("建议为主要表添加created_at和updated_at时间戳字段")
        
        if not characteristics.get("has_soft_delete"):
            recommendations.append("考虑实现软删除机制以保留历史数据")
        
        # 基于业务实体的建议
        entities = analysis_result.get("business_entities", {})
        if len(entities) < 5:
            recommendations.append("数据模型较简单，考虑是否需要扩展业务实体")
        elif len(entities) > 20:
            recommendations.append("数据模型较复杂，建议进行模块化设计")
        
        return recommendations