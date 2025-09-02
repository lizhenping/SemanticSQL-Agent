"""
领域分析工具 - 分析数据库的业务领域
基于 LangChain BaseTool
"""

from typing import Dict, Any, Type, List, Union
from pydantic import BaseModel, Field

from models.exceptions import ToolExecutionError
from .base_analysis_tool import BaseAnalysisTool, AnalysisToolInput


class DomainAnalysisInput(AnalysisToolInput):
    """领域分析输入"""
    input: Union[Dict[str, Any], str] = Field(default_factory=dict, description="输入参数（JSON字符串或字典，包含schema_info等）")


class DomainAnalysisTool(BaseAnalysisTool):
    """业务领域分析工具"""
    
    name: str = "domain_analysis"
    description: str = "分析数据库的业务领域，识别主要业务场景和数据特征"
    args_schema: Type[BaseModel] = DomainAnalysisInput
    
    def _run(self, input: Union[Dict[str, Any], str] = None, **kwargs) -> Dict[str, Any]:
        """执行领域分析"""
        try:
            # 添加详细的调试信息
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"=== DOMAIN ANALYSIS DEBUG ===")
            logger.error(f"input type: {type(input)}")
            logger.error(f"input value: {str(input)[:500]}...")
            logger.error(f"kwargs: {kwargs}")
            
            # 多种方式尝试获取schema_info
            schema_info = {}
            
            # 方式1: 直接从input参数提取
            if input:
                schema_info = self.get_data_from_memory_or_param(input, "schema_info")
                logger.error(f"Method 1 result: {bool(schema_info)}")
            
            # 方式2: 检查kwargs中是否有schema_info
            if not schema_info and "schema_info" in kwargs:
                schema_info = kwargs["schema_info"]
                logger.error(f"Method 2 result: {bool(schema_info)}")
            
            # 方式3: 从memory获取
            if not schema_info and self._agent_memory:
                current_memory = self.get_current_memory()
                schema_info = self.get_analysis_from_memory(current_memory, "schema_info")
                logger.error(f"Method 3 result: {bool(schema_info)}")
            
            logger.error(f"Final schema_info: {bool(schema_info)}")
            
            if not schema_info:
                raise ToolExecutionError(
                    tool_name=self.name,
                    reason="未找到数据库结构信息，请先执行schema_extraction"
                )
            
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
            result["data_characteristics"] = self._analyze_data_characteristics(tables)
            
            # 生成建议
            result["recommendations"] = self._generate_domain_recommendations(result)
            
            # 返回工具自己的结果（不包含累积数据）
            return result
            
        except Exception as e:
            raise ToolExecutionError(
                tool_name=self.name,
                reason=f"领域分析失败: {str(e)}"
            )
    
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
        
        domain_scores = {}
        table_names = [name.lower() for name in tables.keys()]
        all_columns = []
        
        # 收集所有列名
        for table_info in tables.values():
            columns = table_info.get("columns", [])
            all_columns.extend([col["name"].lower() for col in columns])
        
        # 计算每个领域的匹配分数
        for domain, keywords in domain_patterns.items():
            score = 0.0
            matched_keywords = 0
            
            for keyword in keywords:
                # 检查表名
                table_matches = sum(1 for t in table_names if keyword in t)
                # 检查列名
                column_matches = sum(1 for c in all_columns if keyword in c)
                
                if table_matches > 0 or column_matches > 0:
                    matched_keywords += 1
                    score += table_matches * 2 + column_matches  # 表名权重更高
            
            if matched_keywords > 0:
                # 归一化分数
                domain_scores[domain] = score / (len(keywords) * len(tables))
        
        return domain_scores
    
    def _identify_business_entities(self, tables: Dict[str, Any]) -> Dict[str, List[str]]:
        """识别业务实体"""
        entities = {
            "核心实体": [],
            "关联实体": [],
            "配置实体": [],
            "日志实体": []
        }
        
        for table_name, table_info in tables.items():
            columns = table_info.get("columns", [])
            column_names = [col["name"].lower() for col in columns]
            
            # 判断实体类型
            has_id = any("id" in col for col in column_names)
            has_timestamps = any(
                any(ts in col for ts in ["created", "updated", "time"])
                for col in column_names
            )
            has_status = any("status" in col or "state" in col for col in column_names)
            
            # 核心实体：有ID、时间戳和状态
            if has_id and has_timestamps and has_status:
                entities["核心实体"].append(table_name)
            # 关联实体：多对多关系表
            elif table_name.count("_") >= 2 or any(
                kw in table_name.lower() for kw in ["_to_", "_map", "_rel"]
            ):
                entities["关联实体"].append(table_name)
            # 配置实体
            elif any(
                cfg in table_name.lower() 
                for cfg in ["config", "setting", "parameter", "option"]
            ):
                entities["配置实体"].append(table_name)
            # 日志实体
            elif any(
                log in table_name.lower() 
                for log in ["log", "history", "audit", "track"]
            ):
                entities["日志实体"].append(table_name)
            # 其他有ID的作为核心实体
            elif has_id:
                entities["核心实体"].append(table_name)
        
        return entities
    
    def _identify_business_processes(
        self, 
        tables: Dict[str, Any], 
        entities: Dict[str, List[str]]
    ) -> List[str]:
        """识别业务流程"""
        processes = []
        table_names = list(tables.keys())
        
        # 基于表名模式识别流程
        process_patterns = {
            "订单流程": ["order", "payment", "delivery", "refund"],
            "用户管理": ["user", "role", "permission", "auth"],
            "库存管理": ["inventory", "stock", "purchase", "supplier"],
            "内容发布": ["content", "article", "publish", "review"],
            "财务流程": ["invoice", "payment", "billing", "accounting"],
            "客户服务": ["ticket", "support", "feedback", "complaint"]
        }
        
        for process_name, keywords in process_patterns.items():
            matching_tables = []
            for keyword in keywords:
                matching_tables.extend([
                    t for t in table_names 
                    if keyword in t.lower()
                ])
            
            if len(matching_tables) >= 2:  # 至少匹配2个相关表
                processes.append(process_name)
        
        return processes
    
    def _analyze_data_characteristics(self, tables: Dict[str, Any]) -> Dict[str, Any]:
        """分析数据特征"""
        characteristics = {
            "total_tables": len(tables),
            "total_columns": 0,
            "avg_columns_per_table": 0,
            "has_timestamps": False,
            "has_soft_delete": False,
            "has_versioning": False,
            "common_patterns": []
        }
        
        total_columns = 0
        timestamp_tables = 0
        soft_delete_tables = 0
        version_tables = 0
        
        for table_info in tables.values():
            columns = table_info.get("columns", [])
            total_columns += len(columns)
            
            column_names = [col["name"].lower() for col in columns]
            
            # 检查时间戳
            if any("created" in col or "updated" in col for col in column_names):
                timestamp_tables += 1
            
            # 检查软删除
            if any(
                col in column_names 
                for col in ["deleted_at", "is_deleted", "deleted"]
            ):
                soft_delete_tables += 1
            
            # 检查版本控制
            if any("version" in col for col in column_names):
                version_tables += 1
        
        characteristics["total_columns"] = total_columns
        characteristics["avg_columns_per_table"] = (
            total_columns / len(tables) if tables else 0
        )
        characteristics["has_timestamps"] = timestamp_tables > len(tables) * 0.5
        characteristics["has_soft_delete"] = soft_delete_tables > 0
        characteristics["has_versioning"] = version_tables > 0
        
        # 识别常见模式
        if characteristics["has_timestamps"]:
            characteristics["common_patterns"].append("时间戳审计")
        if characteristics["has_soft_delete"]:
            characteristics["common_patterns"].append("软删除")
        if characteristics["has_versioning"]:
            characteristics["common_patterns"].append("版本控制")
        
        return characteristics
    
    def _generate_domain_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """生成领域相关建议"""
        recommendations = []
        
        domain = analysis.get("primary_domain", "")
        entities = analysis.get("business_entities", {})
        processes = analysis.get("business_processes", [])
        
        # 基于领域的建议
        if domain == "电商":
            recommendations.append("关注订单、商品、库存相关的查询")
            recommendations.append("考虑销售统计、库存预警等场景")
        elif domain == "金融":
            recommendations.append("重点关注交易、账户余额相关查询")
            recommendations.append("注意数据精度和事务一致性")
        
        # 基于实体的建议
        if len(entities.get("核心实体", [])) > 10:
            recommendations.append("系统较复杂，建议分模块生成查询")
        
        if entities.get("日志实体"):
            recommendations.append("可以生成日志分析和审计相关的查询")
        
        # 基于流程的建议
        if "订单流程" in processes:
            recommendations.append("生成订单全流程跟踪的查询")
        
        return recommendations
    
    async def _arun(self, memory: Dict[str, Any]) -> Dict[str, Any]:
        """异步执行（当前实现为同步）"""
        return self._run(memory)