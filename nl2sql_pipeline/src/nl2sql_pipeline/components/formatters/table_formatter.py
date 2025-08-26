"""表信息格式化器

格式化数据库表信息，生成LLM友好的文本表示。
"""

from typing import List, Dict, Any, Optional
from .base import BaseFormatter
from ...models.database import TableInfo, ColumnInfo
from ...models.analysis import ERRelationship


class TableFormatter(BaseFormatter):
    """表信息格式化器
    
    将表结构信息格式化为适合LLM理解的文本格式。
    """
    
    def format(self, data: Any, context: Optional[Dict[str, Any]] = None) -> str:
        """格式化表信息
        
        Args:
            data: 表名列表或单个表名
            context: 包含 tables, columns, relationships 等信息
            
        Returns:
            格式化后的表信息
        """
        if isinstance(data, str):
            return self.format_single_table(data, context)
        elif isinstance(data, list):
            return self.format_multiple_tables(data, context)
        else:
            return str(data)
    
    def format_single_table(self, table_name: str, context: Optional[Dict[str, Any]] = None) -> str:
        """格式化单个表的详细信息"""
        if not context:
            return f"Table: {table_name}"
        
        # 获取表对象
        tables = context.get('tables', [])
        table = next((t for t in tables if t.name == table_name), None)
        if not table:
            return f"Table: {table_name} (not found)"
        
        # 获取列信息
        columns = context.get('columns', {}).get(table_name, [])
        
        # 构建格式化输出
        lines = []
        lines.append(f"=== Table: {table_name} ===")
        
        # 表描述
        if hasattr(table, 'description') and table.description:
            lines.append(f"Description: {table.description}")
        
        # 表统计
        lines.append(f"Total Columns: {len(columns)}")
        
        # 主键
        pk_columns = [col.name for col in columns if col.is_primary_key]
        if pk_columns:
            lines.append(f"Primary Keys: {', '.join(pk_columns)}")
        
        # 外键
        fk_columns = [col.name for col in columns if col.is_foreign_key]
        if fk_columns:
            lines.append(f"Foreign Keys: {', '.join(fk_columns)}")
        
        # 列详情
        lines.append("\nColumns:")
        for col in columns[:10]:  # 限制显示前10个
            col_line = f"  - {col.name} ({col.data_type})"
            if col.is_primary_key:
                col_line += " [PK]"
            if col.is_foreign_key:
                col_line += " [FK]"
            if not col.is_nullable:
                col_line += " [NOT NULL]"
            lines.append(col_line)
        
        if len(columns) > 10:
            lines.append(f"  ... and {len(columns) - 10} more columns")
        
        return '\n'.join(lines)
    
    def format_multiple_tables(self, table_names: List[str], context: Optional[Dict[str, Any]] = None) -> str:
        """格式化多个表的摘要信息"""
        if not context:
            return "Tables: " + ", ".join(table_names)
        
        lines = []
        lines.append(f"=== Tables Summary ({len(table_names)} tables) ===")
        
        for table_name in table_names:
            # 获取表对象
            tables = context.get('tables', [])
            table = next((t for t in tables if t.name == table_name), None)
            
            # 基本信息
            line = f"\n- {table_name}"
            
            # 添加描述
            if table and hasattr(table, 'description') and table.description:
                line += f" ({self._truncate(table.description, 50)})"
            
            # 添加列数
            columns = context.get('columns', {}).get(table_name, [])
            line += f" [{len(columns)} columns]"
            
            # 标记核心表
            if self._is_core_table(table_name, context):
                line += " ⭐"
            
            lines.append(line)
            
            # 添加关键字段
            key_fields = self._get_key_fields(table_name, columns)
            if key_fields:
                lines.append(f"  Key fields: {', '.join(key_fields[:5])}")
        
        return '\n'.join(lines)
    
    def format_table_ddl(self, table_name: str, context: Optional[Dict[str, Any]] = None) -> str:
        """格式化表的DDL语句"""
        if not context:
            return f"-- Table: {table_name}"
        
        columns = context.get('columns', {}).get(table_name, [])
        if not columns:
            return f"-- Table: {table_name} (no columns)"
        
        lines = []
        lines.append(f"CREATE TABLE {table_name} (")
        
        col_lines = []
        for col in columns:
            col_def = f"  {col.name} {col.data_type}"
            if not col.is_nullable:
                col_def += " NOT NULL"
            if col.is_primary_key:
                col_def += " PRIMARY KEY"
            col_lines.append(col_def)
        
        lines.append(",\n".join(col_lines))
        lines.append(");")
        
        return '\n'.join(lines)
    
    def _is_core_table(self, table_name: str, context: Dict[str, Any]) -> bool:
        """判断是否为核心业务表"""
        # 1. 关系数量
        relationships = context.get('relationships', [])
        rel_count = sum(1 for rel in relationships 
                       if rel.source_table == table_name or rel.target_table == table_name)
        
        # 2. 包含关键业务字段
        columns = context.get('columns', {}).get(table_name, [])
        key_patterns = ['amount', 'total', 'price', 'quantity', 'revenue']
        has_key_fields = any(
            any(pattern in col.name.lower() for pattern in key_patterns)
            for col in columns
        )
        
        # 3. 表名包含核心业务词汇
        core_patterns = ['order', 'customer', 'product', 'transaction', 'payment']
        is_core_name = any(pattern in table_name.lower() for pattern in core_patterns)
        
        return rel_count >= 3 or has_key_fields or is_core_name
    
    def _get_key_fields(self, table_name: str, columns: List[ColumnInfo]) -> List[str]:
        """获取表的关键字段"""
        key_fields = []
        
        # 主键
        for col in columns:
            if col.is_primary_key:
                key_fields.append(col.name)
        
        # 外键
        for col in columns:
            if col.is_foreign_key and col.name not in key_fields:
                key_fields.append(col.name)
        
        # 业务关键字段
        key_patterns = ['name', 'code', 'type', 'status', 'amount', 'date']
        for col in columns:
            if any(pattern in col.name.lower() for pattern in key_patterns):
                if col.name not in key_fields:
                    key_fields.append(col.name)
        
        return key_fields[:8]  # 最多返回8个