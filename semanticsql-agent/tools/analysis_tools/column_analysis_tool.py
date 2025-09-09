"""
列语义分析工具 - 极简架构重构版本
基于新的BaseSemanticSQLTool，实现完全自主的列语义分析
"""

from typing import Dict, Any, List, Optional
import json
import re

from tools.base_tool import BaseSemanticSQLTool
from models.schemas import PredicateType, EntityType
from models.exceptions import raise_tool_error, raise_dependency_error


class ColumnAnalysisTool(BaseSemanticSQLTool):
    """列语义分析工具 - 极简重构版本
    
    职责：
    - 基于数据库结构和字段分析进行列语义分析
    - 生成详细的业务含义描述
    - 识别列间的语义关系和模式
    - 为后续工具提供列语义上下文
    
    设计原则：
    - 依赖记忆：基于schema_extraction和field_analysis工具的结果
    - 智能推断：结合字段语义和业务域知识
    - 三元组输出：结构化列语义关系
    """
    
    name: str = "column_analysis"
    description: str = "分析数据库列语义，生成业务含义描述和语义关系"
    
    def __init__(self, **kwargs):
        """初始化列分析工具"""
        super().__init__(**kwargs)
        # 使用object.__setattr__避免Pydantic验证问题
        object.__setattr__(self, 'meaning_patterns', self._init_meaning_patterns())
    
    def _run(self, *args, **kwargs) -> str:
        """执行工具分析"""
        # 提取输入文本
        input_text = args[0] if args else kwargs.get('input', '')
        # 1. 清空上次执行的三元组
        self._clear_generated_triples()
        self._log_execution_start(input_text)
        
        try:
            # 2. 检查依赖：需要schema_extraction和field_analysis工具的结果
            self._check_dependencies(["schema_extraction", "field_analysis"])
            
            # 3. 获取依赖分析结果
            analysis_context = self._gather_analysis_context()
            
            # 4. 分析列语义
            column_analysis = self._analyze_columns_semantics(analysis_context)
            
            # 5. 生成列语义三元组
            self._generate_column_triples(column_analysis, analysis_context)
            
            # 6. 持久化三元组到记忆系统
            self._persist_triples()
            
            # 7. 构建执行结果
            result_message = self._build_result_message(column_analysis)
            
            self._log_execution_end(f"分析了 {column_analysis['total_columns']} 个列")
            return result_message
            
        except Exception as e:
            error_msg = f"列语义分析失败: {str(e)}"
            self.logger.error(f"❌ {self.name}: {error_msg}")
            return f"❌ {error_msg}"
    
    # ========== 核心业务逻辑 ==========
    def _gather_analysis_context(self) -> Dict[str, Any]:
        """收集分析上下文"""
        # 获取基础结构信息
        schema_memory = self.get_memory_by_source_tool("schema_extraction")
        schema_info = self._extract_schema_info(schema_memory)
        
        # 获取字段分析结果
        field_memory = self.get_memory_by_source_tool("field_analysis")
        field_semantics = self._extract_field_semantics(field_memory)
        
        # 尝试获取领域信息（可选）
        domain_memory = self.get_memory_by_source_tool("domain_analysis")
        domain_info = self._extract_domain_info(domain_memory) if domain_memory else {"primary_domain": "通用业务"}
        
        return {
            "schema_info": schema_info,
            "field_semantics": field_semantics,
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
            elif predicate == "has_type":
                column_details[subject] = {"type": obj}
            elif predicate == "is_primary_key" and obj == "true":
                if subject not in column_details:
                    column_details[subject] = {}
                column_details[subject]["is_primary_key"] = True
        
        return {
            "database_name": database_name,
            "tables": list(tables),
            "table_columns": table_columns,
            "column_details": column_details
        }
    
    def _extract_field_semantics(self, field_memory: List[Dict[str, Any]]) -> Dict[str, Any]:
        """从记忆中提取字段语义信息"""
        field_semantics = {}
        field_importance = {}
        field_meanings = {}
        
        for triple in field_memory:
            subject = triple.get("subject", "")
            predicate = triple.get("predicate", "")
            obj = triple.get("object", "")
            
            if predicate == "has_semantic_type":
                field_semantics[subject] = obj
            elif predicate == "has_importance":
                field_importance[subject] = obj
            elif predicate == "has_business_meaning":
                field_meanings[subject] = obj
        
        return {
            "field_semantics": field_semantics,
            "field_importance": field_importance,
            "field_meanings": field_meanings
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
    
    def _init_meaning_patterns(self) -> Dict[str, Dict[str, Any]]:
        """初始化语义描述模式库"""
        return {
            "标识符": {
                "template": "{table_name}表的唯一标识符，用于区分不同的{entity_name}记录",
                "entity_keywords": ["用户", "产品", "订单", "账户", "项目"],
                "confidence_boost": 0.9
            },
            "时间字段": {
                "template": "记录{entity_name}在{domain}业务中的时间戳信息，用于跟踪{action}",
                "action_mapping": {
                    "created": "创建时间",
                    "updated": "更新时间", 
                    "deleted": "删除时间",
                    "modified": "修改时间",
                    "login": "登录时间",
                    "expire": "过期时间"
                },
                "confidence_boost": 0.85
            },
            "金额字段": {
                "template": "{entity_name}相关的金额数据，在{domain}业务中用于财务统计和分析",
                "financial_keywords": ["价格", "费用", "成本", "收入", "支出"],
                "confidence_boost": 0.9
            },
            "数量字段": {
                "template": "{entity_name}的数量统计信息，支持{domain}业务的数据分析和报表",
                "quantity_keywords": ["计数", "总数", "长度", "尺寸", "容量"],
                "confidence_boost": 0.8
            },
            "状态字段": {
                "template": "标识{entity_name}在{domain}业务流程中的当前状态或阶段",
                "status_keywords": ["待处理", "进行中", "已完成", "已取消", "活跃", "禁用"],
                "confidence_boost": 0.85
            },
            "文本字段": {
                "template": "{entity_name}的描述性文本信息，提供详细的业务说明和备注",
                "text_keywords": ["描述", "备注", "说明", "内容", "标题"],
                "confidence_boost": 0.7
            },
            "布尔字段": {
                "template": "{entity_name}的二元状态标记，表示某个特征的是否状态",
                "boolean_keywords": ["启用", "可见", "有效", "删除", "推荐"],
                "confidence_boost": 0.8
            }
        }
    
    def _analyze_columns_semantics(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """分析列语义"""
        schema_info = context["schema_info"]
        field_semantics_info = context["field_semantics"]
        domain_info = context["domain_info"]
        
        table_columns = schema_info["table_columns"]
        column_details = schema_info["column_details"]
        field_semantics = field_semantics_info["field_semantics"]
        field_importance = field_semantics_info["field_importance"]
        field_meanings = field_semantics_info["field_meanings"]
        
        analyzed_columns = []
        semantic_groups = {}
        relationship_patterns = []
        
        # 分析每个列
        for table_name, columns in table_columns.items():
            entity_name = self._infer_entity_name(table_name, domain_info)
            
            for column_name in columns:
                column_key = f"{table_name}.{column_name}"
                column_type = column_details.get(column_name, {}).get("type", "unknown")
                semantic_type = field_semantics.get(column_key, "未分类")
                importance = field_importance.get(column_key, "low")
                basic_meaning = field_meanings.get(column_key, "")
                
                # 生成增强的业务含义
                enhanced_meaning = self._generate_enhanced_meaning(
                    table_name, column_name, semantic_type, entity_name, 
                    domain_info["primary_domain"], basic_meaning
                )
                
                # 分析语义关系
                relationships = self._analyze_semantic_relationships(
                    table_name, column_name, semantic_type, columns
                )
                
                column_analysis = {
                    "table_name": table_name,
                    "column_name": column_name,
                    "semantic_type": semantic_type,
                    "entity_name": entity_name,
                    "enhanced_meaning": enhanced_meaning,
                    "importance": importance,
                    "data_type": column_type,
                    "relationships": relationships,
                    "confidence": self._calculate_meaning_confidence(semantic_type, basic_meaning)
                }
                
                analyzed_columns.append(column_analysis)
                
                # 更新语义分组统计
                if semantic_type not in semantic_groups:
                    semantic_groups[semantic_type] = []
                semantic_groups[semantic_type].append(column_key)
                
                # 收集关系模式
                relationship_patterns.extend(relationships)
        
        return {
            "analyzed_columns": analyzed_columns,
            "semantic_groups": semantic_groups,
            "relationship_patterns": relationship_patterns,
            "total_columns": len(analyzed_columns),
            "domain": domain_info["primary_domain"],
            "analysis_details": {
                "total_tables": len(table_columns),
                "high_confidence_columns": len([c for c in analyzed_columns if c["confidence"] > 0.8]),
                "unique_semantic_types": len(semantic_groups)
            }
        }
    
    def _infer_entity_name(self, table_name: str, domain_info: Dict[str, Any]) -> str:
        """推断实体名称"""
        # 清理表名
        clean_name = table_name.lower()
        clean_name = re.sub(r'^(t_|tbl_|tb_)', '', clean_name)  # 去前缀
        clean_name = re.sub(r'(_log|_history|_backup)$', '', clean_name)  # 去后缀
        
        # 实体映射词典
        entity_mapping = {
            "user": "用户", "customer": "客户", "member": "会员",
            "product": "产品", "goods": "商品", "item": "项目",
            "order": "订单", "payment": "支付", "transaction": "交易",
            "account": "账户", "profile": "档案", "info": "信息",
            "category": "分类", "type": "类型", "status": "状态",
            "log": "日志", "record": "记录", "data": "数据"
        }
        
        # 查找匹配
        for english, chinese in entity_mapping.items():
            if english in clean_name:
                return chinese
        
        # 使用业务概念
        for concept in domain_info.get("business_concepts", []):
            if concept in clean_name:
                return concept
        
        return clean_name.replace("_", "")
    
    def _generate_enhanced_meaning(self, table_name: str, column_name: str, semantic_type: str, 
                                 entity_name: str, domain: str, basic_meaning: str) -> str:
        """生成增强的业务含义描述"""
        if semantic_type == "未分类" or not basic_meaning:
            return f"{entity_name}的{column_name}属性，用于存储相关业务数据"
        
        pattern_info = self.meaning_patterns.get(semantic_type, {})
        template = pattern_info.get("template", basic_meaning)
        
        try:
            # 特殊处理时间字段
            if semantic_type == "时间字段":
                action = "时间记录"
                action_mapping = pattern_info.get("action_mapping", {})
                for key, value in action_mapping.items():
                    if key in column_name.lower():
                        action = value
                        break
                
                return template.format(
                    entity_name=entity_name,
                    domain=domain,
                    action=action
                )
            
            # 标准模板替换
            return template.format(
                table_name=table_name,
                entity_name=entity_name,
                domain=domain
            )
            
        except (KeyError, ValueError):
            # 模板替换失败时返回基础含义
            return basic_meaning or f"{entity_name}的{semantic_type}数据字段"
    
    def _analyze_semantic_relationships(self, table_name: str, column_name: str, 
                                      semantic_type: str, all_columns: List[str]) -> List[Dict[str, str]]:
        """分析语义关系"""
        relationships = []
        
        # 分析命名模式关系
        if semantic_type == "标识符":
            # 寻找可能的外键关系
            for other_column in all_columns:
                if other_column != column_name and "_id" in other_column.lower():
                    relationships.append({
                        "type": "potential_foreign_key",
                        "target": f"{table_name}.{other_column}",
                        "description": f"可能存在外键关系"
                    })
        
        # 分析时间序列关系
        if semantic_type == "时间字段":
            time_columns = [col for col in all_columns 
                          if any(keyword in col.lower() for keyword in ["time", "date", "created", "updated"])]
            if len(time_columns) > 1:
                relationships.append({
                    "type": "temporal_sequence",
                    "target": f"{table_name}.{time_columns}",
                    "description": "时间序列关系"
                })
        
        # 分析状态-时间关联
        if semantic_type == "状态字段":
            time_columns = [col for col in all_columns 
                          if any(keyword in col.lower() for keyword in ["time", "date", "updated"])]
            for time_col in time_columns:
                relationships.append({
                    "type": "status_time_correlation", 
                    "target": f"{table_name}.{time_col}",
                    "description": "状态与时间关联"
                })
        
        return relationships
    
    def _calculate_meaning_confidence(self, semantic_type: str, basic_meaning: str) -> float:
        """计算语义含义置信度"""
        base_confidence = 0.7
        
        # 基于语义类型的置信度调整
        confidence_mapping = {
            "标识符": 0.9,
            "时间字段": 0.85,
            "金额字段": 0.9,
            "状态字段": 0.85,
            "未分类": 0.3
        }
        
        semantic_confidence = confidence_mapping.get(semantic_type, base_confidence)
        
        # 基于基础含义的置信度调整
        if basic_meaning and len(basic_meaning) > 10:
            semantic_confidence += 0.1
        
        return min(semantic_confidence, 0.95)
    
    def _generate_column_triples(self, analysis: Dict[str, Any], context: Dict[str, Any]) -> None:
        """生成列语义三元组"""
        database_name = context["schema_info"]["database_name"]
        analyzed_columns = analysis["analyzed_columns"]
        
        for column_info in analyzed_columns:
            table_name = column_info["table_name"]
            column_name = column_info["column_name"]
            semantic_type = column_info["semantic_type"]
            enhanced_meaning = column_info["enhanced_meaning"]
            entity_name = column_info["entity_name"]
            confidence = column_info["confidence"]
            relationships = column_info["relationships"]
            
            column_key = f"{table_name}.{column_name}"
            
            # 1. 列-增强业务含义关系
            self.add_analysis_triple(
                subject=column_key,
                predicate="has_enhanced_meaning",
                object=enhanced_meaning,
                subject_type=EntityType.COLUMN.value,
                object_type="EnhancedBusinessMeaning",
                confidence=confidence
            )
            
            # 2. 列-实体关系
            self.add_analysis_triple(
                subject=column_key,
                predicate="belongs_to_entity",
                object=entity_name,
                subject_type=EntityType.COLUMN.value,
                object_type="BusinessEntity",
                confidence=0.8
            )
            
            # 3. 列-语义分组关系
            self.add_analysis_triple(
                subject=semantic_type,
                predicate="contains_column",
                object=column_key,
                subject_type="SemanticGroup",
                object_type=EntityType.COLUMN.value,
                confidence=confidence
            )
            
            # 4. 语义关系三元组
            for rel in relationships:
                self.add_analysis_triple(
                    subject=column_key,
                    predicate=f"has_{rel['type']}",
                    object=rel["target"],
                    subject_type=EntityType.COLUMN.value,
                    object_type="SemanticRelation",
                    confidence=0.7
                )
        
        self.logger.info(f"📝 生成了 {len(self._generated_triples)} 个列语义三元组")
    
    def _build_result_message(self, analysis: Dict[str, Any]) -> str:
        """构建执行结果消息"""
        total_columns = analysis["total_columns"]
        semantic_groups = analysis["semantic_groups"]
        relationship_patterns = analysis["relationship_patterns"]
        domain = analysis["domain"]
        triple_count = len(self._generated_triples)
        
        # 构建语义分组统计
        group_stats = []
        for semantic_type, columns in semantic_groups.items():
            group_stats.append(f"  • {semantic_type}: {len(columns)}个列")
        
        # 构建关系模式统计
        relationship_types = {}
        for rel in relationship_patterns:
            rel_type = rel["type"]
            relationship_types[rel_type] = relationship_types.get(rel_type, 0) + 1
        
        rel_stats = []
        for rel_type, count in relationship_types.items():
            rel_stats.append(f"  • {rel_type}: {count}个")
        
        result = f"""✅ 列语义分析完成

🎯 分析结果:
  • 分析列总数: {total_columns}
  • 业务域: {domain}
  • 生成三元组: {triple_count}个

📊 语义分组分布:
{chr(10).join(group_stats)}

🔗 语义关系模式:
{chr(10).join(rel_stats) if rel_stats else "  • 未发现特殊关系模式"}

📈 分析质量:
  • 分析表数: {analysis['analysis_details']['total_tables']}
  • 高置信度列: {analysis['analysis_details']['high_confidence_columns']}个
  • 语义类型数: {analysis['analysis_details']['unique_semantic_types']}种

💾 列语义知识已存储到记忆系统，可供后续工具使用"""
        
        return result


# ========== 便利函数 ==========
def create_column_analysis_tool(memory_manager: Optional['Neo4jMemoryManager'] = None) -> ColumnAnalysisTool:
    """创建列分析工具的便利函数"""
    return ColumnAnalysisTool(memory_manager=memory_manager)