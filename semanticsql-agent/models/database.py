"""
数据库相关模型 - 表结构、关系等
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional, Dict


class ColumnInfo(BaseModel):
    """列信息"""
    name: str
    data_type: str
    nullable: bool = True
    default: Optional[str] = None
    is_primary: bool = False
    is_foreign: bool = False
    comment: Optional[str] = None


class ForeignKey(BaseModel):
    """外键信息"""
    column: str
    referenced_table: str
    referenced_column: str


class TableInfo(BaseModel):
    """表结构信息"""
    name: str
    columns: List[ColumnInfo] = Field(default_factory=list)
    primary_key: Optional[List[str]] = None
    foreign_keys: List[ForeignKey] = Field(default_factory=list)
    indexes: List[str] = Field(default_factory=list)
    row_count: Optional[int] = None
    comment: Optional[str] = None


class TableRelationship(BaseModel):
    """表关系"""
    from_table: str
    to_table: str
    relationship_type: str  # one-to-one, one-to-many, many-to-many
    join_condition: str


class DatabaseSchema(BaseModel):
    """数据库结构信息"""
    database_name: str
    tables: Dict[str, TableInfo] = Field(default_factory=dict)
    relationships: List[TableRelationship] = Field(default_factory=list)
    extracted_at: datetime = Field(default_factory=datetime.now)
    
    def get_table_names(self) -> List[str]:
        """获取所有表名"""
        return list(self.tables.keys())
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }