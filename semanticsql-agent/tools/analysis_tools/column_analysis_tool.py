"""
列语义分析工具 - 优化版本
简化设计，移除过度异常处理，按就近原则组织代码
"""

from typing import Dict, Any, Type, List, Tuple
import json
from dataclasses import dataclass
from pydantic import BaseModel, Field

from models.exceptions import ToolExecutionError
from prompts.manager import PromptManager
from ..base_tool import BaseSemanticSQLTool


# ========== 工具内部数据模型（就近原则）==========
class ColumnAnalysisInput(BaseModel):
    """列语义分析输入参数"""
    generate_examples: bool = Field(default=True, description="是否生成示例值")
    use_sample_data: bool = Field(default=True, description="是否使用样本数据")


@dataclass
class ColumnContext:
    """列上下文信息"""
    table_name: str
    column_name: str
    data_type: str
    is_primary_key: bool
    is_nullable: bool
    comment: str
    sample_values: List[Any]
    domain_type: str = "unknown"
    field_category: str = "other"
    field_type: str = "unknown"


class BusinessMeaningRule(BaseModel):
    """业务含义推断规则"""
    name_patterns: List[str]
    description_template: str
    confidence: float = 0.8
    examples: List[str] = Field(default_factory=list)


class ColumnMeaningResult(BaseModel):
    """列含义分析结果"""
    table_name: str
    column_name: str
    business_meaning: str
    description_confidence: float
    semantic_group: str = "general"
    examples: List[str] = Field(default_factory=list)
    inference_source: str = "rule_based"


class ColumnAnalysisTool(BaseSemanticSQLTool):
    """列语义分析工具 - 优化版本
    
    职责：
    - 为数据库列生成业务含义描述
    - 基于列名、数据类型和样本数据推断语义
    - 按语义类型对列进行分组
    
    设计原则：
    - 单一职责：专注列语义分析
    - 方法拆分：每个方法<30行
    - 类型安全：使用数据类和Pydantic模型
    - 简化异常：让异常自然传播
    """
    
    name: str = "column_analysis"
    description: str = "为数据库列生成业务含义描述和语义分组"
    args_schema: Type[BaseModel] = ColumnAnalysisInput
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, 'prompt_manager', PromptManager())
        object.__setattr__(self, '_meaning_rules', self._initialize_meaning_rules())
    
    def _run(self, generate_examples: bool = True, use_sample_data: bool = True, **kwargs) -> str:
        """执行列语义分析 - 主流程"""
        # 获取所有分析上下文
        analysis_context = self._gather_analysis_context()
        
        # 提取列上下文信息
        column_contexts = self._extract_column_contexts(analysis_context, use_sample_data)
        
        # 生成列语义分析
        column_meanings = self._analyze_column_meanings(column_contexts, generate_examples)
        
        # 构建分析结果
        result = self._build_analysis_result(column_meanings)
        
        # 保存并返回
        self.save_to_memory("column_meanings", result)
        return json.dumps(result, ensure_ascii=False)
    
    # ========== 核心分析逻辑 ==========
    def _gather_analysis_context(self) -> Dict[str, Any]:
        """获取所有分析上下文"""
        context = {
            "schema_info": self.get_from_memory("schema_extraction"),
            "domain_info": self.get_from_memory("domain_analysis"),
            "field_classification": self.get_from_memory("field_analysis")
        }
        
        if not context["schema_info"]:
            raise ToolExecutionError(
                tool_name=self.name,
                reason="无法获取数据库结构信息，需要先运行schema_extraction工具"
            )
        
        return context
    
    def _initialize_meaning_rules(self) -> List[BusinessMeaningRule]:
        """初始化业务含义推断规则"""
        return [
            BusinessMeaningRule(
                name_patterns=["id"],
                description_template="主键标识符，唯一标识{table_name}表中的每一条记录",
                confidence=1.0
            ),
            BusinessMeaningRule(
                name_patterns=["_id", "ref_id", "fk_"],
                description_template="外键标识符，关联其他表的主键值",
                confidence=0.9
            ),
            BusinessMeaningRule(
                name_patterns=["name", "title", "label"],
                description_template="名称字段，存储{table_name}的易读标识信息",
                confidence=0.9
            ),
            BusinessMeaningRule(
                name_patterns=["created_at", "create_time", "created"],
                description_template="创建时间，记录{table_name}数据创建的时间点",
                confidence=0.95
            ),
            BusinessMeaningRule(
                name_patterns=["updated_at", "update_time", "modified"],
                description_template="更新时间，记录{table_name}数据最后修改的时间点",
                confidence=0.95
            ),
            BusinessMeaningRule(
                name_patterns=["status", "state", "flag"],
                description_template="状态字段，表示{table_name}的当前状态或处理阶段",
                confidence=0.85
            ),
            BusinessMeaningRule(
                name_patterns=["type", "category", "kind"],
                description_template="类型字段，表示{table_name}的分类或类型信息",
                confidence=0.85
            ),
            BusinessMeaningRule(
                name_patterns=["amount", "price", "cost", "fee", "money"],
                description_template="金额字段，存储{table_name}相关的货币数值信息",
                confidence=0.9
            ),
            BusinessMeaningRule(
                name_patterns=["count", "num", "qty", "quantity", "total"],
                description_template="数量字段，记录{table_name}相关的计数信息",
                confidence=0.85
            ),
            BusinessMeaningRule(
                name_patterns=["phone", "mobile", "tel", "telephone"],
                description_template="电话号码字段，存储{table_name}的联系电话信息",
                confidence=0.9
            ),
            BusinessMeaningRule(
                name_patterns=["email", "mail", "e_mail"],
                description_template="邮箱字段，存储{table_name}的电子邮件地址",
                confidence=0.95
            ),
            BusinessMeaningRule(
                name_patterns=["address", "addr", "location"],
                description_template="地址字段，存储{table_name}的物理位置信息",
                confidence=0.9
            )
        ]
    
    def _extract_column_contexts(self, analysis_context: Dict[str, Any], use_sample_data: bool) -> List[ColumnContext]:
        """提取所有列的上下文信息"""
        column_contexts = []
        schema_info = analysis_context["schema_info"]
        domain_info = analysis_context.get("domain_info", {})
        field_classification = analysis_context.get("field_classification", {})
        
        tables = schema_info.get("tables", {})
        domain_type = domain_info.get("primary_domain", "unknown") if domain_info else "unknown"
        field_classifications = field_classification.get("field_classifications", {})
        
        for table_name, table_info in tables.items():
            primary_keys = set(table_info.get("primary_keys", []))
            columns = table_info.get("columns", [])
            sample_data = table_info.get("sample_data", []) if use_sample_data else []
            
            for column in columns:
                column_name = column.get("name", "")
                sample_values = self._extract_sample_values(column_name, sample_data)
                
                # 获取字段分类信息
                field_info = field_classifications.get(table_name, {}).get(column_name, {})
                
                context = ColumnContext(
                    table_name=table_name,
                    column_name=column_name,
                    data_type=column.get("type", ""),
                    is_primary_key=column_name in primary_keys,
                    is_nullable=column.get("nullable", True),
                    comment=column.get("comment", ""),
                    sample_values=sample_values,
                    domain_type=domain_type,
                    field_category=field_info.get("category", "other"),
                    field_type=field_info.get("field_type", "unknown")
                )
                column_contexts.append(context)
        
        return column_contexts
    
    def _extract_sample_values(self, column_name: str, sample_data: List[Dict[str, Any]]) -> List[Any]:
        """从样本数据中提取指定列的值"""
        values = []
        for row in sample_data:
            if column_name in row and row[column_name] is not None:
                values.append(row[column_name])
        return values[:5]  # 最多迕5个样本值
    
    def _analyze_column_meanings(self, column_contexts: List[ColumnContext], generate_examples: bool) -> List[ColumnMeaningResult]:
        """分析所有列的业务含义"""
        column_meanings = []
        
        for context in column_contexts:
            meaning_result = self._analyze_single_column_meaning(context, generate_examples)
            column_meanings.append(meaning_result)
        
        return column_meanings
    
    def _analyze_single_column_meaning(self, context: ColumnContext, generate_examples: bool) -> ColumnMeaningResult:
        """分析单个列的业务含义"""
        # 优先使用字段分类信息
        if context.field_category != "other" and context.field_type != "unknown":
            business_meaning = f"{context.field_type}字段，属于{context.field_category}类别，用于{context.domain_type}业务"
            semantic_group = context.field_category
            confidence = 0.85
            source = "field_classification"
        else:
            # 使用规则匹配
            rule_match = self._find_matching_rule(context)
            if rule_match:
                rule, confidence = rule_match
                business_meaning = rule.description_template.format(table_name=context.table_name)
                semantic_group = self._determine_semantic_group(context, rule)
                source = "rule_based"
            else:
                # 默认分析
                business_meaning, semantic_group, confidence, source = self._create_default_meaning(context)
        
        # 生成示例值
        examples = self._generate_column_examples(context) if generate_examples else []
        
        return ColumnMeaningResult(
            table_name=context.table_name,
            column_name=context.column_name,
            business_meaning=business_meaning,
            description_confidence=confidence,
            semantic_group=semantic_group,
            examples=examples,
            inference_source=source
        )
    
    def _find_matching_rule(self, context: ColumnContext) -> Tuple[BusinessMeaningRule, float]:
        """找到匹配的业务含义规则"""
        column_name_lower = context.column_name.lower()
        
        # 主键特殊处理
        if context.is_primary_key and context.column_name.lower() == "id":
            return self._meaning_rules[0], 1.0  # ID主键规则
        
        # 其他规则匹配
        for rule in self._meaning_rules:
            for pattern in rule.name_patterns:
                if pattern in column_name_lower:
                    return rule, rule.confidence
        
        return None
    
    def _determine_semantic_group(self, context: ColumnContext, rule: BusinessMeaningRule) -> str:
        """确定语义分组"""
        # 基于规则的语义分组
        if any(pattern in rule.name_patterns for pattern in ["id", "_id"]):
            return "identifier"
        elif any(pattern in rule.name_patterns for pattern in ["time", "date", "created", "updated"]):
            return "temporal"
        elif any(pattern in rule.name_patterns for pattern in ["amount", "price", "cost", "count", "qty"]):
            return "measure"
        elif any(pattern in rule.name_patterns for pattern in ["status", "state", "type", "category"]):
            return "dimension"
        elif any(pattern in rule.name_patterns for pattern in ["name", "title", "label"]):
            return "label"
        elif any(pattern in rule.name_patterns for pattern in ["phone", "email", "address"]):
            return "contact"
        else:
            return "general"
    
    def _create_default_meaning(self, context: ColumnContext) -> Tuple[str, str, float, str]:
        """创建默认含义（未匹配到规则时）"""
        data_type_lower = context.data_type.lower()
        
        if any(dt in data_type_lower for dt in ["text", "varchar", "char"]):
            meaning = f"文本字段，存储{context.table_name}的字符串信息"
            semantic_group = "text"
        elif any(dt in data_type_lower for dt in ["int", "decimal", "float", "numeric"]):
            meaning = f"数值字段，存储{context.table_name}的数字信息"
            semantic_group = "numeric"
        elif any(dt in data_type_lower for dt in ["bool", "bit", "boolean"]):
            meaning = f"布尔字段，表示{context.table_name}的是/否状态"
            semantic_group = "boolean"
        elif any(dt in data_type_lower for dt in ["datetime", "timestamp", "date", "time"]):
            meaning = f"时间字段，记录{context.table_name}的时间信息"
            semantic_group = "temporal"
        else:
            meaning = f"{context.domain_type}领域中{context.table_name}表的业务数据字段"
            semantic_group = "general"
        
        return meaning, semantic_group, 0.3, "data_type_inference"
    
    def _generate_column_examples(self, context: ColumnContext) -> List[str]:
        """生成列示例值"""
        if not context.sample_values:
            return []
        
        # 转换为字符串并去重
        examples = []
        seen = set()
        for value in context.sample_values:
            str_value = str(value)
            if str_value not in seen and str_value.lower() not in ['none', 'null', '']:
                examples.append(str_value)
                seen.add(str_value)
                if len(examples) >= 3:  # 最多3个示例
                    break
        
        return examples
    
    # ========== 结果构建和统计 ==========
    def _build_analysis_result(self, column_meanings: List[ColumnMeaningResult]) -> Dict[str, Any]:
        """构建分析结果"""
        # 按表组织列含义
        column_meanings_by_table = self._organize_meanings_by_table(column_meanings)
        
        # 语义分组统计
        semantic_groups = self._calculate_semantic_groups(column_meanings)
        
        # 业务含义映射
        business_meanings = self._create_business_meanings_map(column_meanings)
        
        return {
            "column_meanings": column_meanings_by_table,
            "business_meanings": business_meanings,
            "semantic_groups": semantic_groups,
            "total_columns": len(column_meanings),
            "high_confidence_count": len([m for m in column_meanings if m.description_confidence > 0.8]),
            "tables_processed": len(set(m.table_name for m in column_meanings)),
            "analysis_summary": f"共分析{len(column_meanings)}个列，识别出{len(semantic_groups)}个语义分组"
        }
    
    def _organize_meanings_by_table(self, column_meanings: List[ColumnMeaningResult]) -> Dict[str, Dict[str, Any]]:
        """按表组织列含义"""
        result = {}
        
        for meaning in column_meanings:
            if meaning.table_name not in result:
                result[meaning.table_name] = {}
            
            result[meaning.table_name][meaning.column_name] = {
                "business_meaning": meaning.business_meaning,
                "semantic_group": meaning.semantic_group,
                "confidence": meaning.description_confidence,
                "examples": meaning.examples,
                "inference_source": meaning.inference_source
            }
        
        return result
    
    def _calculate_semantic_groups(self, column_meanings: List[ColumnMeaningResult]) -> Dict[str, List[str]]:
        """计算语义分组统计"""
        groups = {}
        
        for meaning in column_meanings:
            group = meaning.semantic_group
            if group not in groups:
                groups[group] = []
            groups[group].append(f"{meaning.table_name}.{meaning.column_name}")
        
        return groups
    
    def _create_business_meanings_map(self, column_meanings: List[ColumnMeaningResult]) -> Dict[str, str]:
        """创建业务含义映射"""
        return {
            f"{meaning.table_name}.{meaning.column_name}": meaning.business_meaning
            for meaning in column_meanings
        }
    
    async def _arun(self, generate_examples: bool = True, use_sample_data: bool = True, **kwargs) -> str:
        """异步执行（当前实现为同步）"""
        return self._run(generate_examples, use_sample_data, **kwargs)
