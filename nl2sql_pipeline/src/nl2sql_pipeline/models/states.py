"""LangGraph状态模型定义

定义工作流中使用的各种状态类型。
"""

from typing import TypedDict, Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from .database import DatabaseSchema
from .analysis import (
    DomainKnowledge, 
    FieldClassification,
    ColumnDescription,
    TableDescription,
    ERRelationship
)
from .generation import Question, Scenario


class AnalysisState(BaseModel):
    """分析工作流状态
    
    用于在分析流程中传递数据的状态对象。
    """
    # 基本信息
    database_name: str = Field(..., description="数据库名称")
    current_step: int = Field(default=1, description="当前执行步骤")
    completed_steps: List[int] = Field(default_factory=list, description="已完成的步骤")
    
    # 各步骤的输出
    database_schema: Optional[DatabaseSchema] = Field(None, description="数据库架构")
    domain_knowledge: Optional[DomainKnowledge] = Field(None, description="领域知识")
    field_classifications: Optional[List[FieldClassification]] = Field(None, description="字段分类结果")
    column_descriptions: Optional[List[ColumnDescription]] = Field(None, description="列描述")
    table_descriptions: Optional[List[TableDescription]] = Field(None, description="表描述")
    er_relationships: Optional[List[ERRelationship]] = Field(None, description="ER关系")
    
    # 错误处理
    error_message: Optional[str] = Field(None, description="错误信息")
    retry_count: int = Field(default=0, description="重试次数")
    
    class Config:
        """Pydantic配置"""
        arbitrary_types_allowed = True


class GenerationState(BaseModel):
    """生成工作流状态
    
    用于在问题生成流程中传递数据的状态对象。
    """
    # 输入
    analysis_result: 'AnalysisResult' = Field(..., description="分析结果")
    target_count: int = Field(..., description="目标问题数量")
    
    # 场景和复杂度循环状态
    current_scenario: Optional[Scenario] = Field(None, description="当前场景")
    current_complexity: Optional[int] = Field(None, description="当前复杂度")
    scenario_index: int = Field(default=0, description="场景索引")
    complexity_index: int = Field(default=0, description="复杂度索引")
    
    # 生成的问题
    generated_questions: List[Question] = Field(default_factory=list, description="已生成的问题")
    
    # 进度跟踪
    total_generated: int = Field(default=0, description="总生成数")
    
    class Config:
        """Pydantic配置"""
        arbitrary_types_allowed = True


class AnalysisResult(BaseModel):
    """分析结果汇总
    
    包含数据库分析的完整结果。
    """
    # 基本信息
    database_name: str = Field(..., description="数据库名称")
    analysis_timestamp: datetime = Field(..., description="分析时间戳")
    
    # 分析结果
    database_schema: DatabaseSchema = Field(..., description="数据库架构")
    domain_knowledge: DomainKnowledge = Field(..., description="领域知识（优化后）")
    table_descriptions: List[TableDescription] = Field(..., description="表描述列表")
    column_descriptions: List[ColumnDescription] = Field(..., description="列描述列表")
    field_classifications: Dict[str, Dict[str, Any]] = Field(..., description="字段分类结果")
    er_relationships: Dict[str, List[ERRelationship]] = Field(..., description="ER关系（三层）")
    
    # 统计信息
    analysis_stats: Dict[str, Any] = Field(default_factory=dict, description="分析统计信息")
    
    class Config:
        """Pydantic配置"""
        arbitrary_types_allowed = True
    
    def get_table_description(self, table_name: str) -> Optional[TableDescription]:
        """获取特定表的描述
        
        参数:
            table_name: 表名
            
        返回:
            表描述或None
        """
        for desc in self.table_descriptions:
            if desc.table_name == table_name:
                return desc
        return None
    
    def get_column_descriptions(self, table_name: str) -> List[ColumnDescription]:
        """获取特定表的所有列描述
        
        参数:
            table_name: 表名
            
        返回:
            列描述列表
        """
        return [
            desc for desc in self.column_descriptions
            if desc.table_name == table_name
        ]
    
    def get_field_classification(self, table_name: str, column_name: str) -> Optional[Dict[str, Any]]:
        """获取特定字段的分类信息
        
        参数:
            table_name: 表名
            column_name: 列名
            
        返回:
            分类信息或None
        """
        field_key = f"{table_name}.{column_name}"
        return self.field_classifications.get(field_key)