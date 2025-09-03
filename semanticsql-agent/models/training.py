"""
训练数据相关模型
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Dict, Any, Optional
import uuid

from .base import DifficultyLevel


class GeneratedExample(BaseModel):
    """生成的训练样本"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scenario_id: Optional[str] = None
    question: str = ""  # 自然语言问题
    sql: str = ""  # SQL查询
    difficulty: DifficultyLevel = DifficultyLevel.MEDIUM
    validation_result: Dict[str, Any] = Field(default_factory=dict)
    execution_result: Dict[str, Any] = Field(default_factory=dict)
    quality_score: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    
    def is_valid(self) -> bool:
        """检查样本是否有效"""
        return (
            bool(self.question) and 
            bool(self.sql) and 
            self.validation_result.get("valid", False)
        )


class TrainingExample(BaseModel):
    """最终训练样本格式"""
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
    
    def to_openai_format(self) -> Dict[str, Any]:
        """转换为OpenAI微调格式"""
        return {
            "messages": [
                {"role": "system", "content": f"You are a SQL expert, database ID: {self.database_id}"},
                {"role": "user", "content": self.question},
                {"role": "assistant", "content": self.sql}
            ]
        }
    
    def to_huggingface_format(self) -> Dict[str, Any]:
        """转换为HuggingFace格式"""
        return {
            "input": self.question,
            "output": self.sql,
            "instruction": f"Convert natural language query to SQL (database: {self.database_id})"
        }


class TrainingDataResult(BaseModel):
    """训练数据生成结果"""
    total: int = Field(description="总数")
    successful: int = Field(description="成功数")
    failed: int = Field(description="失败数")
    output_file: str = Field(description="输出文件")
    examples: List[Dict[str, Any]] = Field(default_factory=list, description="示例数据")