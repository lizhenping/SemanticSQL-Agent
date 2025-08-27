"""Pydantic 模型定义"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime


class FieldType(str, Enum):
    """字段类型枚举"""
    DIMENSION = "dimension"
    MEASURE = "measure"
    IDENTIFIER = "identifier"
    TIMESTAMP = "timestamp"
    DESCRIPTION = "description"


class ColumnInfo(BaseModel):
    """列信息模型"""
    name: str = Field(description="列名")
    data_type: str = Field(description="数据类型")
    nullable: bool = Field(default=True, description="是否可空")
    is_primary: bool = Field(default=False, description="是否主键")
    is_foreign: bool = Field(default=False, description="是否外键")
    foreign_key_ref: Optional[str] = Field(default=None, description="外键引用")
    comment: Optional[str] = Field(default=None, description="列注释")
    field_type: Optional[FieldType] = Field(default=None, description="字段类型分类")
    sample_values: Optional[List[Any]] = Field(default=None, description="样本值")


class TableInfo(BaseModel):
    """表信息模型"""
    name: str = Field(description="表名")
    columns: List[ColumnInfo] = Field(description="列信息")
    row_count: Optional[int] = Field(default=None, description="行数")
    comment: Optional[str] = Field(default=None, description="表注释")
    sample_data: Optional[List[Dict[str, Any]]] = Field(default=None, description="样本数据")
    primary_keys: List[str] = Field(default_factory=list, description="主键列表")
    foreign_keys: Dict[str, str] = Field(default_factory=dict, description="外键关系")


class DomainAnalysis(BaseModel):
    """领域分析结果"""
    domain: str = Field(description="业务领域")
    description: str = Field(description="领域描述")
    key_entities: List[str] = Field(description="关键实体")
    business_rules: List[str] = Field(description="业务规则")
    terminology: Dict[str, str] = Field(default_factory=dict, description="专业术语")


class SQLValidationResult(BaseModel):
    """SQL 验证结果"""
    is_valid: bool = Field(description="是否有效")
    syntax_check: bool = Field(description="语法检查结果")
    sql: str = Field(description="验证的 SQL")
    error: Optional[str] = Field(default=None, description="错误信息")
    suggestions: List[str] = Field(default_factory=list, description="改进建议")


class QueryExecutionResult(BaseModel):
    """查询执行结果"""
    success: bool = Field(description="是否成功")
    sql: str = Field(description="执行的 SQL")
    rows: List[Dict[str, Any]] = Field(default_factory=list, description="查询结果")
    row_count: int = Field(default=0, description="结果行数")
    execution_time: Optional[float] = Field(default=None, description="执行时间（秒）")
    error: Optional[str] = Field(default=None, description="错误信息")


class QueryResult(BaseModel):
    """最终查询结果"""
    success: bool = Field(description="是否成功")
    question: str = Field(description="原始问题")
    sql: Optional[str] = Field(default=None, description="生成的 SQL")
    answer: Optional[str] = Field(default=None, description="自然语言回答")
    execution_result: Optional[QueryExecutionResult] = Field(default=None, description="执行结果")
    error: Optional[str] = Field(default=None, description="错误信息")
    steps: int = Field(default=0, description="执行步骤数")
    timestamp: datetime = Field(default_factory=datetime.now, description="查询时间")