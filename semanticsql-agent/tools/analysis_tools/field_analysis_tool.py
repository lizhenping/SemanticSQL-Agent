"""
字段语义分析工具 - 极简架构重构版本
基于新的BaseSemanticSQLTool，实现完全自主的字段语义分析
"""

from typing import Dict, Any, List, Optional
import json
import re

from tools.base_tool import BaseSemanticSQLTool
from models.schemas import PredicateType, EntityType
from models.exceptions import raise_tool_error, raise_dependency_error


class FieldAnalysisTool(BaseSemanticSQLTool):
    """字段语义分析工具 - 极简重构版本
    
    职责：
    - 基于数据库结构进行字段语义分析
    - 识别字段的业务含义和重要性  
    - 生成字段-语义关系三元组
    - 为后续工具提供字段语义上下文
    
    设计原则：
    - 依赖记忆：基于schema_extraction工具的结果
    - 智能推断：通过字段名和类型模式识别
    - 三元组输出：结构化字段知识
    """
    
    name: str = "field_analysis"
    description: str = "分析数据库字段语义，识别字段业务含义和重要性"
    
    def __init__(self, **kwargs):
        """初始化字段分析工具"""
        super().__init__(**kwargs)
        # 使用object.__setattr__避免Pydantic验证问题
        object.__setattr__(self, 'field_patterns', self._init_field_patterns())
    
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
            
            # 4. 分析字段语义
            field_analysis = self._analyze_fields_semantics(schema_info)
            
            # 5. 生成字段三元组
            self._generate_field_triples(field_analysis, schema_info)
            
            # 6. 持久化三元组到记忆系统
            self._persist_triples()
            
            # 7. 构建执行结果
            result_message = self._build_result_message(field_analysis)
            
            self._log_execution_end(f"分析了 {field_analysis['total_fields']} 个字段")
            return result_message
            
        except Exception as e:
            error_msg = f"字段分析失败: {str(e)}"
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
    
    def _init_field_patterns(self) -> Dict[str, Dict[str, Any]]:
        """初始化字段模式库"""
        return {
            "标识符": {
                "name_patterns": ["id", "_id", "uuid", "key", "_key", "code"],
                "type_patterns": ["int", "bigint", "varchar", "char", "uuid"],
                "importance": "critical",
                "semantic_type": "identifier"
            },
            "时间字段": {
                "name_patterns": ["time", "date", "created", "updated", "modified", "at"],
                "type_patterns": ["datetime", "timestamp", "date", "time"],
                "importance": "high",
                "semantic_type": "temporal"
            },
            "金额字段": {
                "name_patterns": ["amount", "price", "cost", "fee", "money", "pay", "salary"],
                "type_patterns": ["decimal", "numeric", "float", "double"],
                "importance": "high",
                "semantic_type": "monetary"
            },
            "数量字段": {
                "name_patterns": ["count", "num", "qty", "quantity", "size", "length", "total"],
                "type_patterns": ["int", "bigint", "smallint", "tinyint"],
                "importance": "medium",
                "semantic_type": "quantitative"
            },
            "状态字段": {
                "name_patterns": ["status", "state", "type", "category", "level", "priority"],
                "type_patterns": ["varchar", "char", "enum", "int"],
                "importance": "high", 
                "semantic_type": "categorical"
            },
            "文本字段": {
                "name_patterns": ["name", "title", "label", "desc", "content", "text", "comment"],
                "type_patterns": ["varchar", "char", "text", "longtext"],
                "importance": "medium",
                "semantic_type": "textual"
            },
            "布尔字段": {
                "name_patterns": ["is_", "has_", "can_", "enable", "active", "deleted"],
                "type_patterns": ["boolean", "bit", "tinyint(1)"],
                "importance": "medium",
                "semantic_type": "boolean"
            }
        }
    
    def _analyze_fields_semantics(self, schema_info: Dict[str, Any]) -> Dict[str, Any]:
        """分析字段语义"""
        table_columns = schema_info["table_columns"]
        column_details = schema_info["column_details"]
        
        analyzed_fields = []
        semantic_summary = {
            "标识符": 0, "时间字段": 0, "金额字段": 0, "数量字段": 0,
            "状态字段": 0, "文本字段": 0, "布尔字段": 0, "未分类": 0
        }
        critical_fields = []
        
        # 分析每个字段
        for table_name, columns in table_columns.items():
            for column_name in columns:
                field_analysis = self._analyze_single_field(
                    table_name, column_name, column_details.get(column_name, {})
                )
                analyzed_fields.append(field_analysis)
                
                # 更新统计
                semantic_type = field_analysis["semantic_type"]
                semantic_summary[semantic_type] = semantic_summary.get(semantic_type, 0) + 1
                
                # 收集关键字段
                if field_analysis["importance"] == "critical":
                    critical_fields.append(f"{table_name}.{column_name}")
        
        return {
            "analyzed_fields": analyzed_fields,
            "semantic_summary": semantic_summary,
            "critical_fields": critical_fields,
            "total_fields": len(analyzed_fields),
            "analysis_details": {
                "total_tables": len(table_columns),
                "patterns_matched": len([f for f in analyzed_fields if f["confidence"] > 0.7])
            }
        }
    
    def _analyze_single_field(self, table_name: str, column_name: str, 
                              column_details: Dict[str, Any]) -> Dict[str, Any]:
        """分析单个字段"""
        column_type = column_details.get("type", "unknown").lower()
        is_primary_key = column_details.get("is_primary_key", False)
        
        # 主键特殊处理
        if is_primary_key:
            return {
                "table_name": table_name,
                "column_name": column_name,
                "semantic_type": "标识符",
                "business_meaning": f"{table_name}表的主键标识符",
                "importance": "critical",
                "confidence": 1.0,
                "data_type": column_type,
                "pattern_matched": "primary_key_detection"
            }
        
        # 模式匹配分析
        best_match = self._match_field_patterns(column_name, column_type)
        
        if best_match:
            semantic_type, confidence, pattern_info = best_match
            return {
                "table_name": table_name,
                "column_name": column_name,
                "semantic_type": semantic_type,
                "business_meaning": self._generate_business_meaning(table_name, column_name, semantic_type),
                "importance": pattern_info["importance"],
                "confidence": confidence,
                "data_type": column_type,
                "pattern_matched": pattern_info["semantic_type"]
            }
        
        # 默认分类
        return {
            "table_name": table_name,
            "column_name": column_name,
            "semantic_type": "未分类",
            "business_meaning": f"{table_name}的普通字段",
            "importance": "low",
            "confidence": 0.1,
            "data_type": column_type,
            "pattern_matched": "no_match"
        }
    
    def _match_field_patterns(self, column_name: str, column_type: str) -> Optional[tuple]:
        """匹配字段模式"""
        column_lower = column_name.lower()
        best_match = None
        best_confidence = 0.0
        
        for semantic_type, pattern_info in self.field_patterns.items():
            confidence = 0.0
            
            # 字段名匹配
            name_score = 0.0
            for pattern in pattern_info["name_patterns"]:
                if pattern in column_lower:
                    name_score = 1.0
                    break
                elif any(part in pattern for part in column_lower.split("_")):
                    name_score = 0.7
            
            # 类型匹配
            type_score = 0.0
            for pattern in pattern_info["type_patterns"]:
                if pattern in column_type:
                    type_score = 1.0
                    break
            
            # 综合置信度：字段名权重0.7，类型权重0.3
            confidence = name_score * 0.7 + type_score * 0.3
            
            if confidence > best_confidence and confidence > 0.3:
                best_confidence = confidence
                best_match = (semantic_type, confidence, pattern_info)
        
        return best_match
    
    def _generate_business_meaning(self, table_name: str, column_name: str, semantic_type: str) -> str:
        """生成业务含义描述"""
        meanings = {
            "标识符": f"{table_name}表的唯一标识符",
            "时间字段": f"记录{table_name}的时间信息",
            "金额字段": f"{table_name}相关的金额数据",
            "数量字段": f"{table_name}的数量统计信息",
            "状态字段": f"{table_name}的状态或分类信息",
            "文本字段": f"{table_name}的描述性文本信息",
            "布尔字段": f"{table_name}的是否标记信息"
        }
        return meanings.get(semantic_type, f"{table_name}的{column_name}字段")
    
    def _generate_field_triples(self, analysis: Dict[str, Any], schema_info: Dict[str, Any]) -> None:
        """生成字段分析三元组"""
        database_name = schema_info["database_name"]
        analyzed_fields = analysis["analyzed_fields"]
        
        for field_info in analyzed_fields:
            table_name = field_info["table_name"]
            column_name = field_info["column_name"]
            semantic_type = field_info["semantic_type"]
            importance = field_info["importance"]
            confidence = field_info["confidence"]
            
            # 1. 字段-语义类型关系
            self.add_analysis_triple(
                subject=f"{table_name}.{column_name}",
                predicate="has_semantic_type",
                object=semantic_type,
                subject_type=EntityType.COLUMN.value,
                object_type="SemanticType",
                confidence=confidence
            )
            
            # 2. 字段-重要性关系
            self.add_analysis_triple(
                subject=f"{table_name}.{column_name}",
                predicate="has_importance",
                object=importance,
                subject_type=EntityType.COLUMN.value,
                object_type="ImportanceLevel",
                confidence=confidence
            )
            
            # 3. 字段-业务含义关系
            if field_info["business_meaning"]:
                self.add_analysis_triple(
                    subject=f"{table_name}.{column_name}",
                    predicate="has_business_meaning",
                    object=field_info["business_meaning"],
                    subject_type=EntityType.COLUMN.value,
                    object_type="BusinessMeaning",
                    confidence=confidence
                )
            
            # 4. 关键字段特殊标记
            if importance == "critical":
                self.add_analysis_triple(
                    subject=table_name,
                    predicate="has_critical_field",
                    object=column_name,
                    subject_type=EntityType.TABLE.value,
                    object_type=EntityType.COLUMN.value,
                    confidence=confidence
                )
        
        self.logger.info(f"📝 生成了 {len(self._generated_triples)} 个字段语义三元组")
    
    def _build_result_message(self, analysis: Dict[str, Any]) -> str:
        """构建执行结果消息"""
        total_fields = analysis["total_fields"]
        semantic_summary = analysis["semantic_summary"]
        critical_fields = analysis["critical_fields"]
        triple_count = len(self._generated_triples)
        
        # 构建语义类型统计
        semantic_stats = []
        for semantic_type, count in semantic_summary.items():
            if count > 0:
                semantic_stats.append(f"  • {semantic_type}: {count}个")
        
        # 构建关键字段描述
        critical_desc = ""
        if critical_fields:
            critical_fields_display = critical_fields[:5]
            if len(critical_fields) > 5:
                critical_fields_display.append(f"等{len(critical_fields)}个")
            critical_desc = f"\n  • 关键字段: {', '.join(critical_fields_display)}"
        
        result = f"""✅ 字段语义分析完成

🔍 分析结果:
  • 分析字段总数: {total_fields}
  • 生成三元组: {triple_count}个{critical_desc}

📊 语义类型分布:
{chr(10).join(semantic_stats)}

🎯 分析统计:
  • 分析表数: {analysis['analysis_details']['total_tables']}
  • 高置信度匹配: {analysis['analysis_details']['patterns_matched']}个
  
💾 字段语义知识已存储到记忆系统，可供后续工具使用"""
        
        return result


# ========== 便利函数 ==========
def create_field_analysis_tool(memory_manager: Optional['Neo4jMemoryManager'] = None) -> FieldAnalysisTool:
    """创建字段分析工具的便利函数"""
    return FieldAnalysisTool(memory_manager=memory_manager)