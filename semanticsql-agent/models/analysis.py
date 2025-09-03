"""
数据库分析相关模型
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class DomainAnalysis(BaseModel):
    """领域分析结果"""
    domain_type: str = Field(description="业务领域类型")
    domain_description: str = Field(description="领域描述")
    confidence: float = Field(default=0.0, description="置信度")
    key_entities: List[str] = Field(default_factory=list, description="关键实体")
    business_characteristics: List[str] = Field(default_factory=list, description="业务特征")
    business_rules: List[str] = Field(default_factory=list, description="业务规则")


class FieldClassification(BaseModel):
    """字段分类结果"""
    field_name: str = Field(description="字段名称")
    category: str = Field(description="字段类别")
    field_type: str = Field(description="具体类型")
    importance: str = Field(description="重要性")
    confidence: float = Field(default=0.0, description="置信度")
    reasoning: Optional[str] = Field(default=None, description="分类理由")


class ColumnMeaning(BaseModel):
    """列业务含义"""
    column_name: str = Field(description="列名")
    table_name: str = Field(description="表名")
    business_meaning: str = Field(description="业务含义")
    data_type: str = Field(description="数据类型")
    examples: List[str] = Field(default_factory=list, description="示例值")


class TableMeaning(BaseModel):
    """表业务含义"""
    table_name: str = Field(description="表名")
    business_purpose: str = Field(description="业务用途")
    entity_type: str = Field(description="实体类型")
    relationships: List[str] = Field(default_factory=list, description="关联关系")


class ERRelation(BaseModel):
    """实体关系"""
    from_table: str = Field(description="源表")
    to_table: str = Field(description="目标表")
    from_column: str = Field(description="源列")
    to_column: str = Field(description="目标列")
    relation_type: str = Field(description="关系类型")
    description: str = Field(description="关系描述")