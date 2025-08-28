"""SQL 生成和验证相关的数据模型"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime


# ==================== SQL 生成相关模型 ====================

class SQLGenerationInput(BaseModel):
    """SQL 生成工具的输入"""
    query: str = Field(description="用户的自然语言查询")
    schema_info: Optional[Any] = Field(
        default=None,
        description="数据库结构信息（SchemaExtractionOutput）"
    )
    domain_analysis: Optional[Any] = Field(
        default=None,
        description="领域分析结果（DomainAnalysisOutput）"
    )
    field_classification: Optional[Any] = Field(
        default=None,
        description="字段分类结果（FieldClassificationOutput）"
    )
    relationships: Optional[Any] = Field(
        default=None,
        description="实体关系信息（ERAnalysisOutput）"
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="额外的上下文信息"
    )


class SQLGenerationOutput(BaseModel):
    """SQL 生成工具的输出"""
    sql: str = Field(description="生成的 SQL 语句")
    explanation: str = Field(description="SQL 语句的解释")
    confidence: float = Field(default=0.8, description="生成置信度")
    tables_used: List[str] = Field(default_factory=list, description="使用的表")
    query_type: str = Field(default="SELECT", description="查询类型")


# ==================== SQL 验证相关模型 ====================

class SQLValidationType(str, Enum):
    """SQL 验证类型"""
    SYNTAX = "syntax"
    SEMANTIC = "semantic"
    PERFORMANCE = "performance"
    SECURITY = "security"


class SQLValidationInput(BaseModel):
    """SQL 验证工具的输入"""
    sql: str = Field(description="要验证的 SQL 语句")
    schema_info: Optional[Any] = Field(
        default=None,
        description="数据库结构信息"
    )
    validation_types: List[SQLValidationType] = Field(
        default=[SQLValidationType.SYNTAX],
        description="要执行的验证类型"
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="查询上下文"
    )


class ValidationIssue(BaseModel):
    """验证问题"""
    issue_type: str = Field(description="问题类型")
    severity: str = Field(description="严重程度：error/warning/info")
    message: str = Field(description="问题描述")
    suggestion: Optional[str] = Field(default=None, description="改进建议")
    line_number: Optional[int] = Field(default=None, description="问题所在行号")


class SQLValidationOutput(BaseModel):
    """SQL 验证工具的输出"""
    is_valid: bool = Field(description="是否有效")
    sql: str = Field(description="验证的 SQL 语句")
    issues: List[ValidationIssue] = Field(default_factory=list, description="发现的问题")
    suggestions: List[str] = Field(default_factory=list, description="改进建议")
    corrected_sql: Optional[str] = Field(default=None, description="修正后的 SQL")


# ==================== SQL 执行相关模型 ====================

class SQLExecutionInput(BaseModel):
    """SQL 执行工具的输入"""
    sql: str = Field(description="要执行的 SQL 语句")
    limit: Optional[int] = Field(
        default=100,
        description="限制返回的行数"
    )
    timeout: Optional[int] = Field(
        default=30,
        description="执行超时时间（秒）"
    )
    dry_run: bool = Field(
        default=False,
        description="是否仅模拟执行"
    )


class SQLExecutionOutput(BaseModel):
    """SQL 执行工具的输出"""
    success: bool = Field(description="是否执行成功")
    sql: str = Field(description="执行的 SQL 语句")
    rows: List[Dict[str, Any]] = Field(default_factory=list, description="查询结果")
    row_count: int = Field(default=0, description="返回的行数")
    affected_rows: Optional[int] = Field(default=None, description="影响的行数（DML）")
    columns: List[str] = Field(default_factory=list, description="结果列名")
    execution_time: Optional[float] = Field(default=None, description="执行时间（秒）")
    error: Optional[str] = Field(default=None, description="错误信息")


# ==================== 思考工具相关模型 ====================

class ThinkingInput(BaseModel):
    """深度思考工具的输入"""
    question: str = Field(description="需要深入思考的问题")
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="相关上下文信息"
    )
    depth: int = Field(
        default=3,
        description="思考深度（1-5）"
    )


class ThinkingStep(BaseModel):
    """思考步骤"""
    step_number: int = Field(description="步骤编号")
    thought: str = Field(description="思考内容")
    conclusion: str = Field(description="步骤结论")
    confidence: float = Field(description="置信度")


class ThinkingOutput(BaseModel):
    """深度思考工具的输出"""
    question: str = Field(description="原始问题")
    steps: List[ThinkingStep] = Field(description="思考步骤")
    final_answer: str = Field(description="最终答案")
    confidence: float = Field(description="总体置信度")
    key_insights: List[str] = Field(default_factory=list, description="关键洞察")