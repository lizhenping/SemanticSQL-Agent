"""Database schema related models"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime


class ColumnInfo(BaseModel):
    """Database column information"""
    name: str
    data_type: str
    is_nullable: bool = True
    is_primary_key: bool = False
    is_foreign_key: bool = False
    default_value: Optional[str] = None
    comment: Optional[str] = None
    
    
class TableInfo(BaseModel):
    """Database table information"""
    name: str
    columns: List[ColumnInfo]
    primary_key: Optional[List[str]] = None
    foreign_keys: List[Dict[str, str]] = Field(default_factory=list)
    indexes: List[Dict[str, Any]] = Field(default_factory=list)
    comment: Optional[str] = None
    row_count: Optional[int] = None
    

class DatabaseSchema(BaseModel):
    """Complete database schema"""
    database_name: str
    tables: List[TableInfo]
    created_at: datetime = Field(default_factory=datetime.now)
    
    @property
    def table_count(self) -> int:
        return len(self.tables)
    
    @property
    def total_columns(self) -> int:
        return sum(len(table.columns) for table in self.tables)
    
    def get_table(self, name: str) -> Optional[TableInfo]:
        """Get table by name"""
        return next((t for t in self.tables if t.name == name), None)