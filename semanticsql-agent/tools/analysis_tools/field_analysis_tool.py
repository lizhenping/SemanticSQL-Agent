"""
字段分析工具 - 优化版本
简化设计，移除过度异常处理，按就近原则组织代码
"""

from typing import Dict, Any, Type, List, Tuple
from enum import Enum
import json
from pydantic import BaseModel, Field

from models.exceptions import ToolExecutionError
from prompts.manager import PromptManager
from ..base_tool import BaseSemanticSQLTool


# ========== 工具内部数据模型（就近原则）==========
class FieldClassificationInput(BaseModel):
    """字段分析输入参数"""
    include_statistics: bool = Field(default=True, description="是否包含统计信息")


class FieldCategory(str, Enum):
    """字段类别枚举"""
    IDENTIFIER = "identifier"    # 标识符（主键、外键）
    DATETIME = "datetime"        # 时间类型
    MEASURE = "measure"          # 度量值（数量、金额）
    DIMENSION = "dimension"      # 维度（状态、类型）
    TEXT = "text"                # 文本信息
    BOOLEAN = "boolean"          # 布尔值
    JSON = "json"                # JSON数据
    BINARY = "binary"            # 二进制数据
    OTHER = "other"              # 其他


class FieldImportance(str, Enum):
    """字段重要性级别"""
    CRITICAL = "critical"        # 关键字段（主键、核心业务字段）
    HIGH = "high"                # 高重要性（常用于查询/分析）
    MEDIUM = "medium"            # 中等重要性
    LOW = "low"                  # 低重要性


class FieldClassificationRule(BaseModel):
    """字段分类规则"""
    name_patterns: List[str] = Field(default_factory=list)
    type_patterns: List[str] = Field(default_factory=list)
    category: FieldCategory
    field_type: str
    importance: FieldImportance
    confidence_base: float = 0.8


class FieldInfo(BaseModel):
    """字段信息"""
    table_name: str
    column_name: str
    data_type: str
    is_primary_key: bool
    is_nullable: bool
    has_default: bool
    comment: str = ""


class ClassifiedField(BaseModel):
    """已分类字段信息"""
    table_name: str
    column_name: str
    category: FieldCategory
    field_type: str
    importance: FieldImportance
    confidence: float
    business_meaning: str = ""
    classification_reason: str = ""


class FieldAnalysisTool(BaseSemanticSQLTool):
    """字段分析工具 - 优化版本
    
    职责：
    - 对数据库字段进行语义分类
    - 识别字段的业务含义和重要性
    - 生成字段分类统计信息
    
    设计原则：
    - 单一职责：专注字段分析
    - 方法拆分：每个方法<30行
    - 类型安全：使用枚举和Pydantic模型
    - 简化异常：让异常自然传播
    """
    
    name: str = "field_analysis"
    description: str = "对数据库字段进行语义分类，识别字段的业务含义和重要性"
    args_schema: Type[BaseModel] = FieldClassificationInput

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, 'prompt_manager', PromptManager())
        object.__setattr__(self, '_classification_rules', self._initialize_classification_rules())

    def _run(self, include_statistics: bool = True, **kwargs) -> str:
        """执行字段分析 - 主流程"""
        # 获取数据库结构信息
        schema_info = self._get_schema_info()
        
        # 提取字段信息
        field_infos = self._extract_field_infos(schema_info)
        
        # 对字段进行分类
        classified_fields = self._classify_all_fields(field_infos)
        
        # 构建分析结果
        result = self._build_analysis_result(classified_fields, include_statistics)
        
        # 保存并返回
        self.save_to_memory("field_analysis", result)
        return json.dumps(result, ensure_ascii=False)
    
    # ========== 核心分析逻辑 ==========
    def _get_schema_info(self) -> Dict[str, Any]:
        """获取数据库结构信息"""
        schema_info = self.get_from_memory("schema_extraction")
        if not schema_info:
            raise ToolExecutionError(
                tool_name=self.name,
                reason="无法获取数据库结构信息，需要先运行schema_extraction工具"
            )
        return schema_info
    
    def _initialize_classification_rules(self) -> List[FieldClassificationRule]:
        """初始化字段分类规则"""
        return [
            # 标识符类型
            FieldClassificationRule(
                name_patterns=["id", "_id", "uuid", "key", "_key"],
                type_patterns=["int", "bigint", "varchar", "char", "uuid"],
                category=FieldCategory.IDENTIFIER,
                field_type="标识符",
                importance=FieldImportance.CRITICAL
            ),
            # 时间类型
            FieldClassificationRule(
                name_patterns=["time", "date", "created", "updated", "modified"],
                type_patterns=["datetime", "timestamp", "date", "time"],
                category=FieldCategory.DATETIME,
                field_type="时间戳",
                importance=FieldImportance.HIGH
            ),
            # 金额类型
            FieldClassificationRule(
                name_patterns=["amount", "price", "cost", "fee", "money", "pay"],
                type_patterns=["decimal", "numeric", "float", "double"],
                category=FieldCategory.MEASURE,
                field_type="金额",
                importance=FieldImportance.HIGH
            ),
            # 数量类型
            FieldClassificationRule(
                name_patterns=["count", "num", "qty", "quantity", "size", "length"],
                type_patterns=["int", "bigint", "smallint", "tinyint"],
                category=FieldCategory.MEASURE,
                field_type="数量",
                importance=FieldImportance.MEDIUM
            ),
            # 状态维度
            FieldClassificationRule(
                name_patterns=["status", "state", "type", "category", "level"],
                type_patterns=["varchar", "char", "enum", "int"],
                category=FieldCategory.DIMENSION,
                field_type="状态",
                importance=FieldImportance.HIGH
            ),
            # 名称文本
            FieldClassificationRule(
                name_patterns=["name", "title", "label", "desc"],
                type_patterns=["varchar", "char", "text"],
                category=FieldCategory.TEXT,
                field_type="名称",
                importance=FieldImportance.HIGH
            ),
            # 布尔类型
            FieldClassificationRule(
                name_patterns=["is_", "has_", "can_", "enable", "active"],
                type_patterns=["boolean", "bit", "tinyint(1)"],
                category=FieldCategory.BOOLEAN,
                field_type="布尔值",
                importance=FieldImportance.MEDIUM
            )
        ]
    
    def _extract_field_infos(self, schema_info: Dict[str, Any]) -> List[FieldInfo]:
        """提取所有字段信息"""
        field_infos = []
        tables = schema_info.get("tables", {})
        
        for table_name, table_info in tables.items():
            primary_keys = set(table_info.get("primary_keys", []))
            columns = table_info.get("columns", [])
            
            for column in columns:
                field_info = FieldInfo(
                    table_name=table_name,
                    column_name=column.get("name", ""),
                    data_type=column.get("type", "").lower(),
                    is_primary_key=column.get("name") in primary_keys,
                    is_nullable=column.get("nullable", True),
                    has_default=column.get("default") is not None,
                    comment=column.get("comment", "")
                )
                field_infos.append(field_info)
        
        return field_infos
    
    def _classify_all_fields(self, field_infos: List[FieldInfo]) -> List[ClassifiedField]:
        """对所有字段进行分类"""
        classified_fields = []
        
        for field_info in field_infos:
            classified_field = self._classify_single_field(field_info)
            classified_fields.append(classified_field)
        
        return classified_fields
    
    def _classify_single_field(self, field_info: FieldInfo) -> ClassifiedField:
        """对单个字段进行分类"""
        # 主键特殊处理
        if field_info.is_primary_key:
            return ClassifiedField(
                table_name=field_info.table_name,
                column_name=field_info.column_name,
                category=FieldCategory.IDENTIFIER,
                field_type="主键",
                importance=FieldImportance.CRITICAL,
                confidence=1.0,
                business_meaning="表的主键标识符",
                classification_reason="数据库主键定义"
            )
        
        # 匹配分类规则
        best_match = self._find_best_matching_rule(field_info)
        if best_match:
            rule, confidence = best_match
            business_meaning = self._generate_business_meaning(field_info, rule)
            classification_reason = self._generate_classification_reason(field_info, rule)
            
            return ClassifiedField(
                table_name=field_info.table_name,
                column_name=field_info.column_name,
                category=rule.category,
                field_type=rule.field_type,
                importance=rule.importance,
                confidence=confidence,
                business_meaning=business_meaning,
                classification_reason=classification_reason
            )
        
        # 默认分类
        return self._create_default_classification(field_info)
    
    def _find_best_matching_rule(self, field_info: FieldInfo) -> Tuple[FieldClassificationRule, float]:
        """找到最佳匹配的分类规则"""
        best_rule = None
        best_confidence = 0.0
        
        for rule in self._classification_rules:
            confidence = self._calculate_rule_confidence(field_info, rule)
            if confidence > best_confidence and confidence > 0.3:  # 最低置信度阈值
                best_rule = rule
                best_confidence = confidence
        
        return (best_rule, best_confidence) if best_rule else None
    
    def _calculate_rule_confidence(self, field_info: FieldInfo, rule: FieldClassificationRule) -> float:
        """计算规则匹配置信度"""
        name_score = 0.0
        type_score = 0.0
        
        # 字段名匹配得分
        field_name_lower = field_info.column_name.lower()
        for pattern in rule.name_patterns:
            if pattern in field_name_lower:
                name_score = 1.0
                break
            elif any(part in pattern for part in field_name_lower.split("_")):
                name_score = 0.7
        
        # 数据类型匹配得分
        for pattern in rule.type_patterns:
            if pattern in field_info.data_type:
                type_score = 1.0
                break
        
        # 综合置信度计算：字段名权重0.7，数据类型权重0.3
        overall_score = name_score * 0.7 + type_score * 0.3
        return overall_score * rule.confidence_base
    
    def _generate_business_meaning(self, field_info: FieldInfo, rule: FieldClassificationRule) -> str:
        """生成业务含义描述"""
        meanings = {
            FieldCategory.IDENTIFIER: f"{field_info.table_name}表的标识符字段",
            FieldCategory.DATETIME: f"记录{field_info.table_name}的时间信息",
            FieldCategory.MEASURE: f"{field_info.table_name}的{rule.field_type}度量值",
            FieldCategory.DIMENSION: f"{field_info.table_name}的{rule.field_type}维度信息",
            FieldCategory.TEXT: f"{field_info.table_name}的{rule.field_type}文本信息",
            FieldCategory.BOOLEAN: f"标记{field_info.table_name}的{rule.field_type}状态"
        }
        return meanings.get(rule.category, f"{field_info.table_name}的{rule.field_type}字段")
    
    def _generate_classification_reason(self, field_info: FieldInfo, rule: FieldClassificationRule) -> str:
        """生成分类理由"""
        return f"基于字段名'{field_info.column_name}'和数据类型'{field_info.data_type}'的规则匹配"
    
    def _create_default_classification(self, field_info: FieldInfo) -> ClassifiedField:
        """创建默认分类（未匹配到规则时）"""
        return ClassifiedField(
            table_name=field_info.table_name,
            column_name=field_info.column_name,
            category=FieldCategory.OTHER,
            field_type="未分类",
            importance=FieldImportance.LOW,
            confidence=0.1,
            business_meaning=f"{field_info.table_name}的普通字段",
            classification_reason="未能匹配到具体分类规则"
        )
    
    # ========== 结果构建和统计 ==========
    def _build_analysis_result(self, classified_fields: List[ClassifiedField], include_statistics: bool) -> Dict[str, Any]:
        """构建分析结果"""
        # 按表组织字段分类
        field_classifications = self._organize_fields_by_table(classified_fields)
        
        # 分类统计
        classification_stats = self._calculate_classification_statistics(classified_fields)
        
        # 重要字段识别
        important_fields = self._identify_important_fields(classified_fields)
        
        result = {
            "field_classifications": field_classifications,
            "classification_stats": classification_stats,
            "important_fields": important_fields,
            "total_fields": len(classified_fields),
            "analysis_summary": f"共分析{len(classified_fields)}个字段，识别出{len(important_fields)}个重要字段"
        }
        
        if include_statistics:
            result["detailed_statistics"] = self._generate_detailed_statistics(classified_fields)
        
        return result
    
    def _organize_fields_by_table(self, classified_fields: List[ClassifiedField]) -> Dict[str, Dict[str, Any]]:
        """按表组织字段分类结果"""
        field_classifications = {}
        
        for field in classified_fields:
            if field.table_name not in field_classifications:
                field_classifications[field.table_name] = {}
            
            field_classifications[field.table_name][field.column_name] = {
                "category": field.category.value,
                "field_type": field.field_type,
                "importance": field.importance.value,
                "confidence": field.confidence,
                "business_meaning": field.business_meaning,
                "classification_reason": field.classification_reason
            }
        
        return field_classifications
    
    def _calculate_classification_statistics(self, classified_fields: List[ClassifiedField]) -> Dict[str, int]:
        """计算分类统计信息"""
        stats = {}
        
        # 按类别统计
        for field in classified_fields:
            category = field.category.value
            stats[category] = stats.get(category, 0) + 1
        
        # 按重要性统计
        importance_stats = {}
        for field in classified_fields:
            importance = field.importance.value
            importance_stats[f"importance_{importance}"] = importance_stats.get(f"importance_{importance}", 0) + 1
        
        stats.update(importance_stats)
        return stats
    
    def _identify_important_fields(self, classified_fields: List[ClassifiedField]) -> List[str]:
        """识别重要字段"""
        important_fields = []
        
        for field in classified_fields:
            if field.importance in [FieldImportance.CRITICAL, FieldImportance.HIGH]:
                important_fields.append(f"{field.table_name}.{field.column_name}")
        
        return important_fields
    
    def _generate_detailed_statistics(self, classified_fields: List[ClassifiedField]) -> Dict[str, Any]:
        """生成详细统计信息"""
        # 高置信度字段
        high_confidence_fields = [
            f"{field.table_name}.{field.column_name}" 
            for field in classified_fields 
            if field.confidence > 0.8
        ]
        
        # 低置信度字段（可能需要人工复核）
        low_confidence_fields = [
            f"{field.table_name}.{field.column_name}" 
            for field in classified_fields 
            if field.confidence < 0.5
        ]
        
        # 按表统计
        tables_stats = {}
        for field in classified_fields:
            table_name = field.table_name
            if table_name not in tables_stats:
                tables_stats[table_name] = {
                    "total_fields": 0,
                    "important_fields": 0,
                    "categories": set()
                }
            
            tables_stats[table_name]["total_fields"] += 1
            if field.importance in [FieldImportance.CRITICAL, FieldImportance.HIGH]:
                tables_stats[table_name]["important_fields"] += 1
            tables_stats[table_name]["categories"].add(field.category.value)
        
        # 转换set为list
        for table_stat in tables_stats.values():
            table_stat["categories"] = list(table_stat["categories"])
        
        return {
            "high_confidence_count": len(high_confidence_fields),
            "low_confidence_count": len(low_confidence_fields),
            "high_confidence_fields": high_confidence_fields[:20],  # 限制返回数量
            "low_confidence_fields": low_confidence_fields[:10],
            "tables_statistics": tables_stats
        }
    
    async def _arun(self, include_statistics: bool = True, **kwargs) -> str:
        """异步执行（当前实现为同步）"""
        return self._run(include_statistics, **kwargs)