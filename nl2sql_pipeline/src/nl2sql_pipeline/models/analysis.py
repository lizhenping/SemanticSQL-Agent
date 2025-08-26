"""分析结果相关的数据模型

包含领域分析、字段分类、描述生成等分析结果的模型定义。
"""

from typing import List, Dict, Optional, Any, Set
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class FieldCategory(Enum):
    """字段类别枚举
    
    定义数据库字段的业务类别。
    """
    IDENTIFIER = "identifier"  # 标识符（如ID、编号）
    MEASURE = "measure"       # 度量（可计算的数值）
    DIMENSION = "dimension"   # 维度（分类、分组字段）
    DATETIME = "datetime"     # 日期时间
    TEXT = "text"            # 文本
    BOOLEAN = "boolean"      # 布尔值
    OTHER = "other"          # 其他


class FieldClassification(BaseModel):
    """字段分类结果
    
    记录单个字段的分类信息。
    """
    field_name: str = Field(..., description="字段全名（表名.列名）")
    category: FieldCategory = Field(..., description="字段类别")
    confidence: float = Field(0.5, ge=0.0, le=1.0, description="分类置信度")
    reasoning: str = Field("", description="分类依据说明")
    data_type: str = Field(..., description="数据类型")
    is_nullable: bool = Field(True, description="是否可空")
    
    # Additional fields for compatibility
    table_name: Optional[str] = Field(None, description="表名")
    column_name: Optional[str] = Field(None, description="列名")
    field_type: Optional[str] = Field(None, description="字段类型")
    importance: Optional[float] = Field(0.5, description="重要性")
    entropy_level: Optional[str] = Field("medium", description="熵值级别")
    
    def get_field_key(self) -> str:
        """Get field key in table.column format"""
        if self.table_name and self.column_name:
            return f"{self.table_name}.{self.column_name}"
        return self.field_name


class FieldEntropyInfo(BaseModel):
    """字段熵值信息
    
    记录字段的熵值计算结果，用于衡量数据多样性。
    """
    field_name: str = Field(..., description="字段全名（表名.列名）")
    entropy_value: float = Field(..., ge=0.0, le=1.0, description="归一化的熵值")
    unique_ratio: float = Field(..., ge=0.0, le=1.0, description="唯一值比例")
    null_ratio: float = Field(..., ge=0.0, le=1.0, description="空值比例")
    entropy_level: str = Field(..., description="熵值级别：low/medium/high")


class ColumnDescription(BaseModel):
    """列描述信息
    
    存储生成的列业务描述。
    """
    table_name: str = Field(..., description="表名")
    column_name: str = Field(..., description="列名")
    description: str = Field(..., description="业务描述")
    confidence: float = Field(0.5, ge=0.0, le=1.0, description="描述置信度")
    source: str = Field("generated", description="描述来源：existing/generated/fallback")
    corrected: bool = Field(False, description="是否经过修正")
    correction_reason: Optional[str] = Field(None, description="修正原因")
    
    # Additional fields for enhanced functionality
    data_type: Optional[str] = Field(None, description="数据类型")
    is_nullable: Optional[bool] = Field(True, description="是否可空")
    is_primary_key: Optional[bool] = Field(False, description="是否主键")
    is_foreign_key: Optional[bool] = Field(False, description="是否外键")
    field_category: Optional[str] = Field(None, description="字段类别")
    business_meaning: Optional[str] = Field(None, description="业务含义")


class TableDescription(BaseModel):
    """表描述信息
    
    存储生成的表业务描述。
    """
    table_name: str = Field(..., description="表名")
    description: str = Field(..., description="业务描述")
    business_type: str = Field("", description="业务类型")
    key_columns: List[str] = Field(default_factory=list, description="关键列列表")
    row_count: Optional[int] = Field(None, description="数据行数")
    confidence: float = Field(0.5, ge=0.0, le=1.0, description="描述置信度")
    
    # Additional fields
    business_role: Optional[str] = Field(None, description="业务角色")
    relationships: Optional[List[str]] = Field(default_factory=list, description="关系列表")


class DomainKnowledge(BaseModel):
    """领域知识模型
    
    存储数据库的业务领域分析结果。
    """
    domain_type: str = Field(..., description="领域类型（如：电商、项目管理等）")
    description: str = Field(..., description="领域描述")
    business_concepts: List[str] = Field(default_factory=list, description="业务概念列表")
    naming_patterns: Dict[str, Any] = Field(default_factory=dict, description="命名模式")
    key_entities: List[str] = Field(default_factory=list, description="关键实体")
    main_entities: List[str] = Field(default_factory=list, description="主要实体（兼容字段）")
    business_rules: List[str] = Field(default_factory=list, description="业务规则")
    key_relationships: List[str] = Field(default_factory=list, description="关键关系")
    
    # 新增字段以兼容其它组件的访问
    business_terms: List[str] = Field(default_factory=list, description="业务术语（用于描述生成上下文）")
    common_patterns: List[str] = Field(default_factory=list, description="常见领域模式（用于关系推断）")
    relationships: Optional[List[str]] = Field(None, description="与key_relationships兼容的别名输入")
    
    # Additional fields for compatibility
    database_description: Optional[str] = Field(None, description="数据库描述")
    business_domain: Optional[str] = Field(None, description="业务领域")
    main_business_entities: Optional[List[str]] = Field(None, description="主要业务实体")
    
    def __init__(self, **data):
        super().__init__(**data)
        # Sync compatible fields
        if self.main_business_entities is None:
            self.main_business_entities = self.main_entities
        if self.database_description is None:
            self.database_description = self.description
        if self.business_domain is None:
            self.business_domain = self.domain_type
        # 将 relationships 映射到 key_relationships（如果后者为空且前者存在）
        try:
            if not self.key_relationships and self.relationships:
                self.key_relationships = list(self.relationships)
        except AttributeError:
            # 防御性处理，确保在缺少属性时不中断
            pass


class ERRelationship(BaseModel):
    """ER关系模型
    
    描述表之间的关系。
    """
    source_table: str = Field(..., description="源表")
    target_table: str = Field(..., description="目标表")
    relationship_type: str = Field(..., description="关系类型")
    source_column: Optional[str] = Field(None, description="源列")
    target_column: Optional[str] = Field(None, description="目标列")
    confidence: float = Field(0.5, ge=0.0, le=1.0, description="关系置信度")
    level: str = Field("physical", description="关系层级：physical/logical/conceptual")


# Additional models for three-layer ER analysis

class PhysicalRelation(BaseModel):
    """Physical layer relationship"""
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    constraint_name: Optional[str] = None
    relationship_type: str = "many_to_one"
    business_meaning: Optional[str] = None


class LogicalRelation(BaseModel):
    """Logical layer relationship"""
    source_table: str
    target_table: str
    source_column: Optional[str] = None
    target_column: Optional[str] = None
    relationship_type: str
    confidence: float = 0.5
    reason: str
    cardinality: str = "many_to_many"
    is_mandatory: bool = False


class ConceptualEntity(BaseModel):
    """Conceptual entity in domain model"""
    name: str
    business_meaning: str
    attributes: List[str] = Field(default_factory=list)
    key_attributes: List[str] = Field(default_factory=list)
    related_tables: List[str] = Field(default_factory=list)


class ConceptualRelationship(BaseModel):
    """Conceptual relationship between entities"""
    source_table: str  # 改为与LogicalRelation一致的命名
    target_table: str  # 改为与LogicalRelation一致的命名
    source_column: Optional[str] = None  # 添加源列
    target_column: Optional[str] = None  # 添加目标列
    relationship_type: str
    business_meaning: str
    cardinality: str = "many_to_many"


class ConceptualModel(BaseModel):
    """Conceptual domain model"""
    entities: List[ConceptualEntity] = Field(default_factory=list)
    relationships: List[ConceptualRelationship] = Field(default_factory=list)


class ERRelations(BaseModel):
    """Three-layer ER relationships"""
    physical_relations: List[PhysicalRelation] = Field(default_factory=list)
    logical_relations: List[LogicalRelation] = Field(default_factory=list)
    conceptual_model: ConceptualModel = Field(default_factory=ConceptualModel)


class ERAnalysisResult(BaseModel):
    """ER关系分析结果"""
    database_name: str
    physical_relations: List[PhysicalRelation] = Field(default_factory=list)
    logical_relations: List[LogicalRelation] = Field(default_factory=list)
    conceptual_relations: List[ConceptualRelationship] = Field(default_factory=list)
    entity_types: Dict[str, str] = Field(default_factory=dict)
    relationship_graph: Dict[str, List[str]] = Field(default_factory=dict)
    statistics: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)


class DatabaseAnalysisResult(BaseModel):
    """Complete database analysis result"""
    database_name: str
    database_schema: Any  # DatabaseSchema
    domain_knowledge: DomainKnowledge
    field_classifications: Dict[str, FieldClassification]
    column_descriptions: Dict[str, ColumnDescription]
    table_descriptions: Dict[str, TableDescription]
    er_relations: ERRelations
    metadata: Dict[str, Any] = Field(default_factory=dict)