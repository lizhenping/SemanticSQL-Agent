"""
三元组数据模型 - SemanticSQL Agent核心数据结构
基于架构设计文档的标准实现
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from enum import Enum
import uuid


class PredicateType(Enum):
    """标准化谓词类型枚举 - 统一三元组关系定义"""
    
    # 数据库结构关系
    HAS_TABLE = "has_table"
    HAS_COLUMN = "has_column"
    HAS_CONSTRAINT = "has_constraint"
    HAS_INDEX = "has_index"
    HAS_RELATIONSHIP = "has_relationship"
    
    # 业务语义关系  
    BELONGS_TO = "belongs_to"
    CONTAINS = "contains"
    REFERENCES = "references"
    DERIVED_FROM = "derived_from"
    SIMILAR_TO = "similar_to"
    
    # 分析结果关系
    FIELD_TYPE = "field_type"
    BUSINESS_MEANING = "business_meaning"
    BUSINESS_ROLE = "business_role"
    CORE_ENTITY = "core_entity"
    
    # 生成内容关系
    GENERATES_QUESTION = "generates_question"
    GENERATES_SQL = "generates_sql"
    CORRESPONDS_TO = "corresponds_to"
    EXECUTES_WITH = "executes_with"
    
    # 质量评估关系
    QUALITY_SCORE = "quality_score"
    VALIDATION_RESULT = "validation_result"
    REFLECTION_RESULT = "reflection_result"


class EntityType(Enum):
    """实体类型枚举"""
    DATABASE = "Database"
    TABLE = "Table"
    COLUMN = "Column"
    DOMAIN = "Domain"
    ENTITY = "Entity"
    QUESTION = "Question"
    SQL = "SQL"
    SCENARIO = "Scenario"
    OPERATION = "Operation"
    RESULT = "Result"


class SemanticTriple(BaseModel):
    """语义三元组 - 系统核心数据结构
    
    设计原则：
    - 统一数据表示：所有工具输入输出都基于三元组
    - 结构化知识：支持图数据库存储和查询
    - 可扩展性：支持任意复杂的关系表达
    """
    
    # 核心三元组字段
    subject: str = Field(description="主体实体")
    predicate: str = Field(description="关系谓词")
    object: str = Field(description="客体实体")
    
    # 扩展元数据字段
    subject_type: str = Field(default="Entity", description="主体类型")
    object_type: str = Field(default="Entity", description="客体类型")
    confidence: Optional[float] = Field(default=None, description="置信度(0-1)")
    source_tool: str = Field(default="", description="来源工具名称")
    
    # 系统字段
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8], description="会话ID")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="创建时间戳")
    
    def to_simple_tuple(self) -> Tuple[str, str, str]:
        """转换为简单三元组元组"""
        return (self.subject, self.predicate, self.object)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return self.model_dump()
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"({self.subject}, {self.predicate}, {self.object})"
    
    def __repr__(self) -> str:
        """调试表示"""
        return f"SemanticTriple({self.subject}, {self.predicate}, {self.object}, source={self.source_tool})"


class TripleCollection(BaseModel):
    """三元组集合 - 工具输出的标准容器
    
    设计原则：
    - 批量操作：支持多个三元组的统一管理
    - 元数据支持：包含生成上下文信息
    - 序列化友好：支持JSON序列化和反序列化
    """
    
    triples: List[SemanticTriple] = Field(default_factory=list, description="三元组列表")
    source_tool: str = Field(description="生成工具名称")
    generation_context: Dict[str, Any] = Field(default_factory=dict, description="生成上下文")
    summary: str = Field(default="", description="集合摘要描述")
    
    def add_triple(self, 
                   subject: str, 
                   predicate: str, 
                   object: str,
                   subject_type: str = "Entity",
                   object_type: str = "Entity", 
                   confidence: Optional[float] = None) -> SemanticTriple:
        """添加新的三元组"""
        triple = SemanticTriple(
            subject=subject,
            predicate=predicate,
            object=object,
            subject_type=subject_type,
            object_type=object_type,
            confidence=confidence,
            source_tool=self.source_tool
        )
        self.triples.append(triple)
        return triple
    
    def filter_by_predicate(self, predicate: str) -> List[SemanticTriple]:
        """按谓词筛选三元组"""
        return [t for t in self.triples if t.predicate == predicate]
    
    def filter_by_subject(self, subject: str) -> List[SemanticTriple]:
        """按主体筛选三元组"""
        return [t for t in self.triples if t.subject == subject]
    
    def count(self) -> int:
        """获取三元组数量"""
        return len(self.triples)
    
    def to_simple_list(self) -> List[Tuple[str, str, str]]:
        """转换为简单三元组列表"""
        return [t.to_simple_tuple() for t in self.triples]
    
    def merge(self, other: 'TripleCollection') -> 'TripleCollection':
        """合并另一个三元组集合"""
        merged = TripleCollection(
            source_tool=f"{self.source_tool}+{other.source_tool}",
            summary=f"Merged: {self.summary} + {other.summary}"
        )
        merged.triples = self.triples + other.triples
        return merged


class AgentState(BaseModel):
    """Agent状态 - 极简设计，只有2个核心字段
    
    设计原则：
    - 极简原则：只保留绝对必要的状态字段
    - 记忆外置：复杂状态通过Neo4j记忆系统管理
    - 自主决策：Agent基于记忆状态自主选择工具
    """
    
    current_input: str = Field(description="用户当前输入")
    database_params: Optional[Dict[str, Any]] = Field(default=None, description="数据库连接参数")


class ToolResult(BaseModel):
    """工具执行结果 - 标准化工具输出格式
    
    设计原则：
    - 统一接口：所有工具返回统一格式
    - 丰富信息：包含执行状态、结果数据、元数据
    - 错误处理：支持错误信息传递
    """
    
    success: bool = Field(description="执行是否成功")
    triples: TripleCollection = Field(description="生成的三元组集合")
    message: str = Field(default="", description="执行消息")
    execution_time: Optional[float] = Field(default=None, description="执行耗时(秒)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")
    error: Optional[str] = Field(default=None, description="错误信息")
    
    @classmethod
    def success_result(cls, 
                      triples: TripleCollection, 
                      message: str = "执行成功",
                      **kwargs) -> 'ToolResult':
        """创建成功结果"""
        return cls(
            success=True,
            triples=triples,
            message=message,
            **kwargs
        )
    
    @classmethod
    def error_result(cls, 
                    error: str, 
                    tool_name: str = "unknown",
                    **kwargs) -> 'ToolResult':
        """创建错误结果"""
        empty_collection = TripleCollection(source_tool=tool_name)
        return cls(
            success=False,
            triples=empty_collection,
            error=error,
            message=f"执行失败: {error}",
            **kwargs
        )





# 便利函数
def create_triple(subject: str, 
                 predicate: str, 
                 object: str,
                 source_tool: str = "",
                 **kwargs) -> SemanticTriple:
    """快速创建三元组的便利函数"""
    return SemanticTriple(
        subject=subject,
        predicate=predicate,
        object=object,
        source_tool=source_tool,
        **kwargs
    )


def create_triple_collection(source_tool: str, 
                           summary: str = "") -> TripleCollection:
    """快速创建三元组集合的便利函数"""
    return TripleCollection(
        source_tool=source_tool,
        summary=summary
    )