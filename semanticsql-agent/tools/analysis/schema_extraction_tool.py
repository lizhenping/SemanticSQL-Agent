"""
数据库结构提取工具 - 提取完整的数据库模式信息
"""

from typing import Dict, Any, List, Optional
from sqlalchemy import create_engine, inspect, MetaData
from sqlalchemy.engine import Engine

from tools.base_tool import BaseTool, ToolParameter
from core.models import DatabaseSchema, TableInfo, ColumnInfo, ForeignKey
from core.exceptions import SchemaExtractionError


class SchemaExtractionTool(BaseTool):
    """数据库结构提取工具"""
    
    def __init__(self, config: Any):
        super().__init__(config)
        self.db_config = config.database if hasattr(config, 'database') else None
        self.engine = None
        if self.db_config:
            self._init_engine()
    
    def _init_engine(self):
        """初始化数据库引擎"""
        try:
            connection_string = self.db_config.to_connection_string()
            self.engine = create_engine(connection_string)
        except Exception as e:
            self.logger.error(f"Failed to create engine: {e}")
    
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
                 sample_data: bool = False, tables: List[str] = None) -> DatabaseSchema:
        """
        执行数据库结构提取
        
        Returns:
            DatabaseSchema对象
        """
        if not self.engine:
            raise SchemaExtractionError("Database engine not initialized")
        
        try:
            inspector = inspect(self.engine)
            
            # 创建数据库结构对象
            db_schema = DatabaseSchema(
                database_name=self.db_config.database if self.db_config else "unknown"
            )
            
            # 获取所有表名
            all_tables = inspector.get_table_names()
            if include_views:
                all_tables.extend(inspector.get_view_names())
            
            # 过滤表
            if tables:
                all_tables = [t for t in all_tables if t in tables]
            
            # 提取每个表的信息
            for table_name in all_tables:
                table_info = self._extract_table_info(
                    inspector, table_name, include_indexes, sample_data
                )
                db_schema.tables[table_name] = table_info
            
            # 提取表关系
            db_schema.relationships = self._extract_relationships(inspector, all_tables)
            
            return db_schema
            
        except Exception as e:
            raise SchemaExtractionError(f"Failed to extract schema: {e}")
    
    def _extract_table_info(self, inspector, table_name: str,
                           include_indexes: bool, sample_data: bool) -> TableInfo:
        """提取单个表的信息"""
        table_info = TableInfo(name=table_name)
        
        # 提取列信息
        columns = inspector.get_columns(table_name)
        for col in columns:
            column_info = ColumnInfo(
                name=col['name'],
                data_type=str(col['type']),
                nullable=col.get('nullable', True),
                default=str(col.get('default', '')) if col.get('default') else None
            )
            table_info.columns.append(column_info)
        
        # 提取主键
        pk_constraint = inspector.get_pk_constraint(table_name)
        if pk_constraint and pk_constraint.get('constrained_columns'):
            table_info.primary_key = pk_constraint['constrained_columns'][0]
            # 标记主键列
            for col in table_info.columns:
                if col.name == table_info.primary_key:
                    col.is_primary = True
        
        # 提取外键
        foreign_keys = inspector.get_foreign_keys(table_name)
        for fk in foreign_keys:
            if fk.get('constrained_columns') and fk.get('referred_table'):
                fk_info = ForeignKey(
                    column=fk['constrained_columns'][0],
                    referenced_table=fk['referred_table'],
                    referenced_column=fk['referred_columns'][0] if fk.get('referred_columns') else 'id'
                )
                table_info.foreign_keys.append(fk_info)
                # 标记外键列
                for col in table_info.columns:
                    if col.name == fk_info.column:
                        col.is_foreign = True
        
        # 提取索引
        if include_indexes:
            indexes = inspector.get_indexes(table_name)
            for idx in indexes:
                if idx.get('column_names'):
                    table_info.indexes.extend(idx['column_names'])
        
        # 获取行数（如果需要）
        if sample_data:
            try:
                with self.engine.connect() as conn:
                    result = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
                    table_info.row_count = result.scalar()
            except:
                table_info.row_count = None
        
        return table_info
    
    def _extract_relationships(self, inspector, tables: List[str]) -> List[Any]:
        """提取表之间的关系"""
        from core.models import TableRelationship
        relationships = []
        
        for table_name in tables:
            foreign_keys = inspector.get_foreign_keys(table_name)
            
            for fk in foreign_keys:
                if fk.get('referred_table') in tables:
                    relationship = TableRelationship(
                        from_table=table_name,
                        to_table=fk['referred_table'],
                        relationship_type=self._determine_relationship_type(
                            inspector, table_name, fk
                        ),
                        join_condition=self._build_join_condition(table_name, fk)
                    )
                    relationships.append(relationship)
        
        return relationships
    
    def _determine_relationship_type(self, inspector, table_name: str, fk: Dict) -> str:
        """判断关系类型"""
        # 简化的关系类型判断
        # 如果外键也是主键，通常是一对一
        pk_constraint = inspector.get_pk_constraint(table_name)
        if pk_constraint and fk.get('constrained_columns'):
            pk_columns = pk_constraint.get('constrained_columns', [])
            fk_columns = fk['constrained_columns']
            
            if set(fk_columns) == set(pk_columns):
                return "one-to-one"
        
        # 默认一对多
        return "one-to-many"
    
    def _build_join_condition(self, from_table: str, fk: Dict) -> str:
        """构建JOIN条件"""
        if fk.get('constrained_columns') and fk.get('referred_columns'):
            from_col = fk['constrained_columns'][0]
            to_table = fk['referred_table']
            to_col = fk['referred_columns'][0]
            return f"{from_table}.{from_col} = {to_table}.{to_col}"
        return ""