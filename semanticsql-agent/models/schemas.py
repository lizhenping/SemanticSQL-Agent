"""
Unified Pydantic data models for SemanticSQL Agent
Based on the design specification - combines all data structures
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional, Any, Dict
from enum import Enum
import uuid


class AgentStepType(Enum):
    """Agent execution step types"""
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"
    REFLECTION = "reflection"


class DifficultyLevel(Enum):
    """Query difficulty levels"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


class SQLOperation(Enum):
    """SQL operation types"""
    SELECT = "SELECT"
    JOIN = "JOIN"
    GROUP = "GROUP"
    SUBQUERY = "SUBQUERY"
    WINDOW = "WINDOW"
    CTE = "CTE"
    UNION = "UNION"


# Agent execution models
class AgentStep(BaseModel):
    """Single execution step"""
    step_type: AgentStepType
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class AgentExecution(BaseModel):
    """Complete execution record"""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task: str = ""
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    steps: List[AgentStep] = Field(default_factory=list)
    final_result: Optional[Any] = None
    status: str = "running"  # running/completed/failed
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def add_step(self, step: AgentStep):
        """Add execution step"""
        self.steps.append(step)
    
    def complete(self, result: Any = None, error: str = None):
        """Mark execution as completed"""
        self.completed_at = datetime.now()
        if error:
            self.status = "failed"
            self.error = error
        else:
            self.status = "completed"
            self.final_result = result
    
    def get_duration(self) -> Optional[float]:
        """Get execution duration in seconds"""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    def get_summary(self) -> Dict[str, Any]:
        """Get execution summary"""
        return {
            "task_id": self.task_id,
            "task": self.task,
            "status": self.status,
            "total_steps": len(self.steps),
            "duration": self.get_duration(),
            "tools_used": list(set(s.tool_name for s in self.steps if s.tool_name)),
            "error": self.error
        }


# Database schema models
class ColumnInfo(BaseModel):
    """Column information"""
    name: str
    data_type: str
    nullable: bool = True
    default: Optional[str] = None
    is_primary: bool = False
    is_foreign: bool = False


class ForeignKey(BaseModel):
    """Foreign key information"""
    column: str
    referenced_table: str
    referenced_column: str


class TableInfo(BaseModel):
    """Table structure information"""
    name: str
    columns: List[ColumnInfo] = Field(default_factory=list)
    primary_key: Optional[str] = None
    foreign_keys: List[ForeignKey] = Field(default_factory=list)
    indexes: List[str] = Field(default_factory=list)
    row_count: Optional[int] = None


class TableRelationship(BaseModel):
    """Table relationship"""
    from_table: str
    to_table: str
    relationship_type: str  # one-to-one, one-to-many, many-to-many
    join_condition: str


class DatabaseSchema(BaseModel):
    """Database structure information"""
    database_name: str
    tables: Dict[str, TableInfo] = Field(default_factory=dict)
    relationships: List[TableRelationship] = Field(default_factory=list)
    extracted_at: datetime = Field(default_factory=datetime.now)
    
    def get_table_names(self) -> List[str]:
        """Get all table names"""
        return list(self.tables.keys())
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# Domain analysis models
class DomainAnalysis(BaseModel):
    """Domain analysis result"""
    domain: str
    confidence: float
    key_entities: List[str]
    business_features: List[str]


class FieldClassification(BaseModel):
    """Field classification result"""
    field_name: str
    classification: str  # id, timestamp, amount, status, description, etc.
    confidence: float
    reasoning: Optional[str] = None


# Query generation models
class QueryScenario(BaseModel):
    """Query scenario"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    category: str = ""  # Sales analysis, inventory management, etc.
    business_purpose: str = ""  # Business purpose
    complexity: DifficultyLevel = DifficultyLevel.MEDIUM
    applicable_tables: List[str] = Field(default_factory=list)
    suggested_operations: List[SQLOperation] = Field(default_factory=list)  # 改为 suggested_operations
    description: str = ""


class GeneratedQuestion(BaseModel):
    """Generated natural language question"""
    scenario_id: str
    question: str
    question_type: str
    complexity: str


class GeneratedSQL(BaseModel):
    """Generated SQL query"""
    question_id: str
    sql: str
    tables_used: List[str]
    sql_type: str  # SELECT/JOIN/AGGREGATE etc.


class GeneratedExample(BaseModel):
    """Generated training sample"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scenario_id: Optional[str] = None
    question: str = ""  # Natural language question
    sql: str = ""  # SQL query
    difficulty: DifficultyLevel = DifficultyLevel.MEDIUM
    validation_result: Dict[str, Any] = Field(default_factory=dict)
    execution_result: Dict[str, Any] = Field(default_factory=dict)
    quality_score: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    
    def is_valid(self) -> bool:
        """Check if sample is valid"""
        return (
            bool(self.question) and 
            bool(self.sql) and 
            self.validation_result.get("valid", False)
        )


class TrainingExample(BaseModel):
    """Final training sample format"""
    question: str
    sql: str
    database_id: str = ""
    difficulty: str = ""
    
    @classmethod
    def from_generated_example(cls, example: GeneratedExample, database_id: str) -> "TrainingExample":
        """Create training sample from generated example"""
        return cls(
            question=example.question,
            sql=example.sql,
            database_id=database_id,
            difficulty=example.difficulty.value
        )
    
    def to_openai_format(self) -> Dict[str, Any]:
        """Convert to OpenAI fine-tuning format"""
        return {
            "messages": [
                {"role": "system", "content": f"You are a SQL expert, database ID: {self.database_id}"},
                {"role": "user", "content": self.question},
                {"role": "assistant", "content": self.sql}
            ]
        }
    
    def to_huggingface_format(self) -> Dict[str, Any]:
        """Convert to HuggingFace format"""
        return {
            "input": self.question,
            "output": self.sql,
            "instruction": f"Convert natural language query to SQL (database: {self.database_id})"
        }


# Validation models
class ValidationResult(BaseModel):
    """Validation result"""
    sql_id: str
    is_valid: bool
    execution_time: Optional[float] = None
    row_count: Optional[int] = None
    error_message: Optional[str] = None


class ExecutionResult(BaseModel):
    """SQL execution result"""
    success: bool
    sql: str
    data: List[Dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    execution_time: float = 0.0
    error_message: Optional[str] = None


# Reflection models
class ReflectionResult(BaseModel):
    """Reflection result"""
    original_sql: str
    issues: List[str]
    suggestions: List[str]
    improved_sql: Optional[str] = None


# SQL Query Result (unified)
class SQLQueryResult(BaseModel):
    """SQL query result - unified from previous implementation"""
    success: bool
    question: str
    sql: Optional[str] = None
    answer: Optional[str] = None
    data: List[Dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    execution_time: float = 0.0
    error: Optional[str] = None
    steps: int = 0


# Tool interfaces
class ToolInput(BaseModel):
    """Base tool input"""
    pass


class ToolOutput(BaseModel):
    """Base tool output"""
    success: bool
    data: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# 新增的模型
class TaskConfig(BaseModel):
    """任务配置"""
    task_type: str = Field(description="任务类型")
    count: int = Field(description="生成数量")
    output_format: str = Field(default="jsonl", description="输出格式")
    config: Dict[str, Any] = Field(default_factory=dict, description="其他配置")


class TrainingDataResult(BaseModel):
    """训练数据生成结果"""
    total: int = Field(description="总数")
    successful: int = Field(description="成功数")
    failed: int = Field(description="失败数")
    output_file: str = Field(description="输出文件")
    examples: List[Dict[str, Any]] = Field(default_factory=list, description="示例数据")


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
    relation_type: str = Field(description="关系类型")
    foreign_key: str = Field(description="外键")
    description: str = Field(description="关系描述")