"""
业务领域分析工具 - 极简架构重构版本
基于新的BaseSemanticSQLTool，实现完全自主的领域识别
"""

from typing import Dict, Any, List, Optional
import json
import re

from tools.base_tool import BaseSemanticSQLTool
from models.schemas import PredicateType, EntityType
from models.exceptions import raise_tool_error, raise_dependency_error


class DomainAnalysisTool(BaseSemanticSQLTool):
    """业务领域分析工具 - 极简重构版本
    
    职责：
    - 基于数据库结构识别业务领域
    - 分析表名和字段名的业务语义  
    - 生成领域-实体关系三元组
    - 为后续工具提供业务上下文
    
    设计原则：
    - 依赖记忆：基于schema_extraction工具的结果
    - 智能推断：通过关键词匹配和模式识别
    - 三元组输出：结构化业务知识
    """
    
    name: str = "domain_analysis"
    description: str = "分析数据库的业务领域，识别主要业务概念和实体关系"
    
    def __init__(self, **kwargs):
        """初始化领域分析工具"""
        super().__init__(**kwargs)
        # 使用object.__setattr__避免Pydantic验证问题
        object.__setattr__(self, 'domain_keywords', self._init_domain_keywords())
    
    def _run(self, *args, **kwargs) -> str:
        """执行工具分析"""
        # 提取输入文本
        input_text = args[0] if args else kwargs.get('input', '')
        # 1. 清空上次执行的三元组
        self._clear_generated_triples()
        self._log_execution_start(input_text)
        
        try:
            # 2. 检查依赖：需要schema_extraction工具的结果
            self._check_dependencies(["schema_extraction"])
            
            # 3. 获取数据库结构信息
            schema_memory = self.get_memory_by_source_tool("schema_extraction")
            schema_info = self._extract_schema_info(schema_memory)
            
            # 4. 分析业务领域
            domain_analysis = self._analyze_business_domain(schema_info)
            
            # 5. 生成领域三元组
            self._generate_domain_triples(domain_analysis, schema_info)
            
            # 6. 持久化三元组到记忆系统
            self._persist_triples()
            
            # 7. 构建执行结果
            result_message = self._build_result_message(domain_analysis)
            
            self._log_execution_end(f"识别出主领域: {domain_analysis['primary_domain']}")
            return result_message
            
        except Exception as e:
            error_msg = f"领域分析失败: {str(e)}"
            self.logger.error(f"❌ {self.name}: {error_msg}")
            return f"❌ {error_msg}"
    
    # ========== 核心业务逻辑 ==========
    def _extract_schema_info(self, schema_memory: List[Dict[str, Any]]) -> Dict[str, Any]:
        """从记忆中提取结构信息"""
        if not schema_memory:
            raise_dependency_error(self.name, "schema_extraction", "数据库结构信息")
        
        # 从三元组中重建结构信息
        tables = set()
        table_columns = {}
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
        
        return {
            "database_name": database_name,
            "tables": list(tables),
            "table_columns": table_columns
        }
    
    def _analyze_business_domain(self, schema_info: Dict[str, Any]) -> Dict[str, Any]:
        """分析业务领域"""
        tables = schema_info["tables"]
        table_columns = schema_info["table_columns"]
        
        # 1. 匹配各个业务领域
        domain_matches = []
        for domain_name, keywords in self.domain_keywords.items():
            match_result = self._match_domain(domain_name, keywords, tables, table_columns)
            if match_result["score"] > 0:
                domain_matches.append(match_result)
        
        # 2. 按得分排序
        domain_matches.sort(key=lambda x: x["score"], reverse=True)
        
        # 3. 确定主要和次要领域
        if domain_matches:
            primary_domain = domain_matches[0]["domain"]
            secondary_domains = [m["domain"] for m in domain_matches[1:3] if m["score"] > 0.2]
            confidence = min(0.95, domain_matches[0]["score"] / len(tables))
        else:
            primary_domain = "通用业务"
            secondary_domains = []
            confidence = 0.1
        
        # 4. 识别核心业务实体
        core_entities = self._identify_core_entities(tables, table_columns)
        
        # 5. 提取业务概念
        business_concepts = self._extract_business_concepts(tables)
        
        return {
            "primary_domain": primary_domain,
            "secondary_domains": secondary_domains,
            "confidence": confidence,
            "core_entities": core_entities,
            "business_concepts": business_concepts,
            "domain_matches": domain_matches,
            "analysis_details": {
                "total_tables": len(tables),
                "analyzed_keywords": len(self.domain_keywords)
            }
        }
    
    def _match_domain(self, domain_name: str, keywords: Dict[str, Any], 
                     tables: List[str], table_columns: Dict[str, List[str]]) -> Dict[str, Any]:
        """匹配特定领域"""
        table_keywords = keywords["tables"]
        column_keywords = keywords["columns"]
        
        matched_tables = []
        matched_columns = []
        score = 0
        
        # 匹配表名
        for table in tables:
            table_lower = table.lower()
            for keyword in table_keywords:
                if keyword in table_lower:
                    matched_tables.append(table)
                    score += 2.0  # 表名匹配权重高
                    break
        
        # 匹配字段名
        for table, columns in table_columns.items():
            for column in columns:
                column_lower = column.lower()
                for keyword in column_keywords:
                    if keyword in column_lower:
                        matched_columns.append(f"{table}.{column}")
                        score += 0.5  # 字段名匹配权重低
                        break
        
        return {
            "domain": domain_name,
            "score": score,
            "matched_tables": matched_tables,
            "matched_columns": matched_columns[:10]  # 限制显示数量
        }
    
    def _identify_core_entities(self, tables: List[str], table_columns: Dict[str, List[str]]) -> List[str]:
        """识别核心业务实体"""
        core_entities = []
        
        # 基于表名识别实体
        entity_indicators = ["user", "customer", "product", "order", "account", "item", "content"]
        
        for table in tables:
            table_lower = table.lower()
            # 去掉常见前缀
            clean_table = re.sub(r'^(t_|tbl_|tb_)', '', table_lower)
            
            # 检查是否为核心实体
            if any(indicator in clean_table for indicator in entity_indicators):
                core_entities.append(table)
            elif len(table_columns.get(table, [])) >= 5:  # 字段较多的表通常是核心实体
                core_entities.append(table)
        
        return core_entities[:8]  # 最多返回8个核心实体
    
    def _extract_business_concepts(self, tables: List[str]) -> List[str]:
        """提取业务概念"""
        concepts = set()
        
        for table in tables:
            # 清理表名
            clean_name = table.lower()
            clean_name = re.sub(r'^(t_|tbl_|tb_)', '', clean_name)  # 去前缀
            clean_name = re.sub(r'(_log|_history|_backup)$', '', clean_name)  # 去后缀
            clean_name = clean_name.replace('_', ' ')
            
            # 分割复合词
            words = clean_name.split()
            for word in words:
                if len(word) > 2 and word not in ['id', 'key', 'info', 'data', 'tmp']:
                    concepts.add(word)
        
        return list(concepts)[:15]  # 最多返回15个概念
    
    def _generate_domain_triples(self, analysis: Dict[str, Any], schema_info: Dict[str, Any]) -> None:
        """生成领域分析三元组"""
        database_name = schema_info["database_name"]
        primary_domain = analysis["primary_domain"]
        
        # 1. 数据库-领域关系
        self.add_analysis_triple(
            subject=database_name,
            predicate=PredicateType.BELONGS_TO.value,
            object=primary_domain,
            subject_type=EntityType.DATABASE.value,
            object_type=EntityType.DOMAIN.value,
            confidence=analysis["confidence"]
        )
        
        # 2. 领域-核心实体关系
        for entity in analysis["core_entities"]:
            self.add_analysis_triple(
                subject=primary_domain,
                predicate=PredicateType.CONTAINS.value,
                object=entity,
                subject_type=EntityType.DOMAIN.value,
                object_type=EntityType.ENTITY.value,
                confidence=0.8
            )
        
        # 3. 业务概念关系
        for concept in analysis["business_concepts"][:10]:
            self.add_analysis_triple(
                subject=primary_domain,
                predicate="has_concept",
                object=concept,
                subject_type=EntityType.DOMAIN.value,
                object_type="BusinessConcept",
                confidence=0.7
            )
        
        # 4. 次要领域关系
        for secondary_domain in analysis["secondary_domains"]:
            self.add_analysis_triple(
                subject=database_name,
                predicate="has_secondary_domain",
                object=secondary_domain,
                subject_type=EntityType.DATABASE.value,
                object_type=EntityType.DOMAIN.value,
                confidence=0.6
            )
        
        self.logger.info(f"📝 生成了 {len(self._generated_triples)} 个领域三元组")
    
    def _build_result_message(self, analysis: Dict[str, Any]) -> str:
        """构建执行结果消息"""
        primary_domain = analysis["primary_domain"]
        secondary_domains = analysis["secondary_domains"]
        core_entities = analysis["core_entities"]
        business_concepts = analysis["business_concepts"]
        confidence = analysis["confidence"]
        triple_count = len(self._generated_triples)
        
        # 构建次要领域描述
        secondary_desc = ""
        if secondary_domains:
            secondary_desc = f"\n  • 次要领域: {', '.join(secondary_domains)}"
        
        # 构建核心实体描述
        entities_desc = ', '.join(core_entities[:5])
        if len(core_entities) > 5:
            entities_desc += f" 等{len(core_entities)}个实体"
        
        result = f"""✅ 业务领域分析完成

🎯 领域识别结果:
  • 主要领域: {primary_domain} (置信度: {confidence:.2f}){secondary_desc}
  • 核心实体: {entities_desc}
  • 业务概念: {len(business_concepts)}个概念
  • 生成三元组: {triple_count}个

📊 分析统计:
  • 分析表数: {analysis['analysis_details']['total_tables']}
  • 匹配领域: {len(analysis['domain_matches'])}个
  
🔗 关键业务概念:
  {', '.join(business_concepts[:8])}

💾 领域知识已存储到记忆系统，可供后续工具使用"""
        
        return result
    
    def _init_domain_keywords(self) -> Dict[str, Dict[str, List[str]]]:
        """初始化领域关键词库"""
        return {
            "电商": {
                "tables": ["order", "product", "customer", "cart", "payment", "shop", "goods", "merchant"],
                "columns": ["price", "amount", "quantity", "sku", "order_id", "product_id", "customer_id"]
            },
            "财务": {
                "tables": ["account", "transaction", "payment", "invoice", "billing", "finance", "money"],
                "columns": ["amount", "balance", "cost", "fee", "tax", "revenue", "profit"]
            },
            "人事": {
                "tables": ["employee", "department", "salary", "attendance", "user", "staff", "hr"],
                "columns": ["salary", "position", "department", "hire_date", "employee_id", "role"]
            },
            "库存": {
                "tables": ["inventory", "stock", "warehouse", "supplier", "goods", "storage"],
                "columns": ["stock", "quantity", "supplier_id", "warehouse_id", "inventory"]
            },
            "内容管理": {
                "tables": ["article", "post", "content", "media", "news", "blog", "cms"],
                "columns": ["title", "content", "author", "publish_date", "category"]
            },
            "教育": {
                "tables": ["student", "course", "teacher", "class", "grade", "exam", "school"],
                "columns": ["student_id", "course_id", "grade", "score", "teacher_id"]
            },
            "医疗": {
                "tables": ["patient", "doctor", "hospital", "medical", "treatment", "prescription"],
                "columns": ["patient_id", "doctor_id", "diagnosis", "treatment", "medicine"]
            },
            "物流": {
                "tables": ["shipping", "delivery", "transport", "logistics", "tracking", "express"],
                "columns": ["tracking_number", "shipping_address", "delivery_date", "courier"]
            }
        }


# ========== 便利函数 ==========
def create_domain_analysis_tool(memory_manager: Optional['Neo4jMemoryManager'] = None) -> DomainAnalysisTool:
    """创建领域分析工具的便利函数"""
    return DomainAnalysisTool(memory_manager=memory_manager)