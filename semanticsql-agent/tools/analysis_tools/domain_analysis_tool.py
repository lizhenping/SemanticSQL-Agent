"""
领域分析工具 - 分析数据库的业务领域
基于 LangChain BaseTool
"""

from typing import Dict, Any, Type, List
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from models.exceptions import ToolExecutionError


class DomainAnalysisInput(BaseModel):
    """领域分析输入"""
    memory: Dict[str, Any] = Field(description="包含数据库分析结果的记忆")


class DomainAnalysisTool(BaseTool):
    """业务领域分析工具"""
    
    name: str = "domain_analysis"
    description: str = "分析数据库的业务领域，识别主要业务场景和数据特征"
    # args_schema: Type[BaseModel] = DomainAnalysisInput  # Commented due to LangChain complex parameter issues
    
    def _run(self, tool_input: str = "", **kwargs) -> Dict[str, Any]:
        """执行领域分析"""
        try:
            # 解析输入参数
            import json
            memory = {}
            schema_info = {}
            
            if tool_input:
                try:
                    parsed_input = json.loads(tool_input)
                    print(f"[DEBUG] Parsed input keys: {list(parsed_input.keys())}")
                    
                    # 尝试多种输入格式
                    if "schema" in parsed_input:
                        # Agent传递的schema格式
                        schema_info = parsed_input["schema"]
                        print(f"[DEBUG] Found schema key, has tables: {'tables' in schema_info}")
                    elif "database_schema" in parsed_input:
                        # Agent传递的database_schema格式
                        schema_info = parsed_input["database_schema"]
                        print(f"[DEBUG] Found database_schema key, has tables: {'tables' in schema_info}")
                    elif "database_structure" in parsed_input:
                        # 直接的数据库结构格式
                        schema_info = parsed_input
                        print(f"[DEBUG] Found database_structure key")
                    elif "memory" in parsed_input:
                        # 包装在memory中的格式
                        memory = parsed_input["memory"]
                        db_analysis = memory.get("db_analysis", {})
                        schema_info = db_analysis.get("schema_info", {})
                        print(f"[DEBUG] Found memory key")
                    elif "db_analysis" in parsed_input:
                        # db_analysis格式
                        db_analysis = parsed_input["db_analysis"]
                        schema_info = db_analysis.get("schema_info", {})
                        print(f"[DEBUG] Found db_analysis key")
                    elif "tables" in parsed_input and "database_name" in parsed_input:
                        # 直接的schema结果格式（从schema_extraction输出）
                        schema_info = parsed_input
                        print(f"[DEBUG] Found direct schema format")
                    else:
                        # 默认作为记忆处理
                        memory = parsed_input
                        db_analysis = memory.get("db_analysis", {})
                        schema_info = db_analysis.get("schema_info", {})
                        print(f"[DEBUG] Using default parsing")
                except json.JSONDecodeError as e:
                    print(f"[DEBUG] JSON decode error: {e}")
                    schema_info = {}
            
            print(f"[DEBUG] Final schema_info empty: {not schema_info}")
            if schema_info:
                print(f"[DEBUG] Schema contains tables: {'tables' in schema_info}")
            
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