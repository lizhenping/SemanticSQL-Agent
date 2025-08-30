"""
统一数据模型定义 - 符合架构规范
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Any, Dict
from enum import Enum
import uuid


class AgentStepType(Enum):
    """智能体执行步骤类型"""
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"
    REFLECTION = "reflection"


class DifficultyLevel(Enum):
    """查询难度级别"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class SQLOperation(Enum):
    """SQL操作类型"""
    SELECT = "SELECT"
    JOIN = "JOIN"
    GROUP = "GROUP"
    SUBQUERY = "SUBQUERY"
    WINDOW = "WINDOW"
    CTE = "CTE"
    UNION = "UNION"


@dataclass
class AgentStep:
    """单个执行步骤"""
    step_type: AgentStepType
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "step_type": self.step_type.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "tool_output": self.tool_output,
            "error": self.error,
            "duration_ms": self.duration_ms
        }


@dataclass
class AgentExecution:
    """完整执行记录"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task: str = ""
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    steps: List[AgentStep] = field(default_factory=list)
    final_result: Optional[Any] = None
    status: str = "running"  # running/completed/failed
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_step(self, step: AgentStep):
        """添加执行步骤"""
        self.steps.append(step)
    
    def complete(self, result: Any = None, error: str = None):
        """标记执行完成"""
        self.completed_at = datetime.now()
        if error:
            self.status = "failed"
            self.error = error
        else:
            self.status = "completed"
            self.final_result = result
    
    def get_duration(self) -> Optional[float]:
        """获取执行时长（秒）"""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    def get_summary(self) -> Dict[str, Any]:
        """获取执行摘要"""
        return {
            "task_id": self.task_id,
            "task": self.task,
            "status": self.status,
            "total_steps": len(self.steps),
            "duration": self.get_duration(),
            "tools_used": list(set(s.tool_name for s in self.steps if s.tool_name)),
            "error": self.error
        }


@dataclass
class QueryScenario:
    """查询场景"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    category: str = ""  # 场景类别（销售分析、库存管理等）
    business_purpose: str = ""  # 业务目的
    complexity: DifficultyLevel = DifficultyLevel.MEDIUM
    applicable_tables: List[str] = field(default_factory=list)
    required_operations: List[SQLOperation] = field(default_factory=list)
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "category": self.category,
            "business_purpose": self.business_purpose,
            "complexity": self.complexity.value,
            "applicable_tables": self.applicable_tables,
            "required_operations": [op.value for op in self.required_operations],
            "description": self.description
        }


@dataclass
class GeneratedExample:
    """生成的训练样本"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    scenario_id: Optional[str] = None
    question: str = ""  # 自然语言问题
    sql: str = ""  # SQL查询
    difficulty: DifficultyLevel = DifficultyLevel.MEDIUM
    validation_result: Dict[str, Any] = field(default_factory=dict)
    execution_result: Dict[str, Any] = field(default_factory=dict)
    quality_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    def is_valid(self) -> bool:
        """检查样本是否有效"""
        return (
            bool(self.question) and 
            bool(self.sql) and 
            self.validation_result.get("valid", False)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "scenario_id": self.scenario_id,
            "question": self.question,
            "sql": self.sql,
            "difficulty": self.difficulty.value,
            "validation_result": self.validation_result,
            "execution_result": self.execution_result,
            "quality_score": self.quality_score,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class TrainingExample:
    """最终的训练样本格式"""
    question: str
    sql: str
    database_id: str = ""
    difficulty: str = ""
    
    @classmethod
    def from_generated_example(cls, example: GeneratedExample, database_id: str) -> "TrainingExample":
        """从生成的样本创建训练样本"""
        return cls(
            question=example.question,
            sql=example.sql,
            database_id=database_id,
            difficulty=example.difficulty.value
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "question": self.question,
            "sql": self.sql,
            "database_id": self.database_id,
            "difficulty": self.difficulty
        }
    
    def to_openai_format(self) -> Dict[str, Any]:
        """转换为OpenAI微调格式"""
        return {
            "messages": [
                {"role": "system", "content": f"你是一个SQL专家，数据库ID: {self.database_id}"},
                {"role": "user", "content": self.question},
                {"role": "assistant", "content": self.sql}
            ]
        }
    
    def to_huggingface_format(self) -> Dict[str, Any]:
        """转换为HuggingFace格式"""
        return {
            "input": self.question,
            "output": self.sql,
            "instruction": f"将自然语言查询转换为SQL（数据库: {self.database_id}）"
        }


@dataclass
class DatabaseSchema:
    """数据库结构信息"""
    database_name: str
    tables: Dict[str, "TableInfo"] = field(default_factory=dict)
    relationships: List["TableRelationship"] = field(default_factory=list)
    extracted_at: datetime = field(default_factory=datetime.now)
    
    def get_table_names(self) -> List[str]:
        """获取所有表名"""
        return list(self.tables.keys())
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "database_name": self.database_name,
            "tables": {name: table.to_dict() for name, table in self.tables.items()},
            "relationships": [rel.to_dict() for rel in self.relationships],
            "extracted_at": self.extracted_at.isoformat()
        }


@dataclass
class TableInfo:
    """表结构信息"""
    name: str
    columns: List["ColumnInfo"] = field(default_factory=list)
    primary_key: Optional[str] = None
    foreign_keys: List["ForeignKey"] = field(default_factory=list)
    indexes: List[str] = field(default_factory=list)
    row_count: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "name": self.name,
            "columns": [col.to_dict() for col in self.columns],
            "primary_key": self.primary_key,
            "foreign_keys": [fk.to_dict() for fk in self.foreign_keys],
            "indexes": self.indexes,
            "row_count": self.row_count
        }


@dataclass
class ColumnInfo:
    """列信息"""
    name: str
    data_type: str
    nullable: bool = True
    default: Optional[str] = None
    is_primary: bool = False
    is_foreign: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "name": self.name,
            "data_type": self.data_type,
            "nullable": self.nullable,
            "default": self.default,
            "is_primary": self.is_primary,
            "is_foreign": self.is_foreign
        }


@dataclass
class ForeignKey:
    """外键信息"""
    column: str
    referenced_table: str
    referenced_column: str
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "column": self.column,
            "referenced_table": self.referenced_table,
            "referenced_column": self.referenced_column
        }


@dataclass
class TableRelationship:
    """表关系"""
    from_table: str
    to_table: str
    relationship_type: str  # one-to-one, one-to-many, many-to-many
    join_condition: str
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "from_table": self.from_table,
            "to_table": self.to_table,
            "relationship_type": self.relationship_type,
            "join_condition": self.join_condition
        }