"""
数据库结构提取工具 - 提取完整的数据库模式信息
"""

from typing import Dict, Any, List, Optional
from sqlalchemy import create_engine, inspect, MetaData
from sqlalchemy.engine import Engine

from tools.base_tool import BaseTool, ToolParameter
from models.schemas import DatabaseSchema, TableInfo, ColumnInfo, ForeignKey
from models.exceptions import SchemaExtractionError


class SchemaExtractionTool(BaseTool):
    """数据库结构提取工具"""
    
    def __init__(self, settings):
        super().__init__(settings)
        # This tool will receive database connection from agent
        self.db_manager = None
    
    def set_database_manager(self, db_manager):
        """Set database manager from agent"""
        self.db_manager = db_manager
    
    @property
    def name(self) -> str:
        return "extract_schema"
    
    @property
    def description(self) -> str:
        return "提取数据库的完整结构信息，包括表、列、索引、外键等"
    
    @property
    def category(self) -> str:
        return "analysis"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="include_views",
                type="boolean",
                description="是否包含视图",
                required=False,
                default=False
            ),
            ToolParameter(
                name="include_indexes",
                type="boolean",
                description="是否包含索引信息",
                required=False,
                default=True
            ),
            ToolParameter(
                name="sample_data",
                type="boolean",
                description="是否包含样本数据",
                required=False,
                default=False
            ),
            ToolParameter(
                name="tables",
                type="array",
                description="指定要提取的表（空则提取所有）",
                required=False,
                default=[]
            )
        ]
    
    def _execute(self, include_views: bool = False, include_indexes: bool = True,
                 sample_data: bool = False, tables: List[str] = None, **kwargs) -> DatabaseSchema:
        """
        Execute database schema extraction
        
        Returns:
            DatabaseSchema object
        """
        if not self.db_manager:
            raise SchemaExtractionError("Database manager not initialized")
        
        try:
            # Get basic table information
            all_tables = self.db_manager.get_tables()
            
            # Filter tables if specified
            if tables:
                all_tables = [t for t in all_tables if t in tables]
            
            # Create database schema object
            db_schema = DatabaseSchema(
                database_name=self.db_manager.config.database
            )
            
            # Extract information for each table
            for table_name in all_tables:
                table_info = self._extract_table_info(table_name, include_indexes, sample_data)
                db_schema.tables[table_name] = table_info
            
            return db_schema
            
        except Exception as e:
            raise SchemaExtractionError(f"Failed to extract schema: {e}")
    
    def _extract_table_info(self, table_name: str,
                           include_indexes: bool, sample_data: bool) -> TableInfo:
        """Extract single table information"""
        # Use database manager to get table info
        table_data = self.db_manager.get_table_info(table_name)
        
        table_info = TableInfo(name=table_name)
        
        # Extract column information
        for col in table_data.get('columns', []):
            column_info = ColumnInfo(
                name=col['name'],
                data_type=col['type'],
                nullable=col.get('nullable', True),
                default=col.get('default'),
                is_primary=col.get('key') == 'PRI' if 'key' in col else False
            )
            table_info.columns.append(column_info)
        
        # Get row count if requested
        if sample_data:
            try:
                result = self.db_manager._execute_query(f"SELECT COUNT(*) as count FROM {table_name}")
                if result.get("success") and result.get("data"):
                    table_info.row_count = result["data"][0]["count"]
            except:
                table_info.row_count = None
        
        return table_info
    
