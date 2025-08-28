"""数据库结构提取工具

参考 nl2sql_pipeline 的 schema_extraction_pipeline 实现，
但使用智能体工具模式而非管道模式。
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Union
import logging

from .base import BaseSemanticSQLTool, ToolExecResult, ToolParameter

logger = logging.getLogger(__name__)


# ==================== 工具内联模型定义 ====================

@dataclass
class ColumnDetail:
    """列的详细信息"""
    name: str
    data_type: str
    is_nullable: bool = True
    default_value: Optional[str] = None
    is_primary_key: bool = False
    is_unique: bool = False
    is_foreign_key: bool = False
    comment: Optional[str] = None


@dataclass
class ForeignKeyInfo:
    """外键信息"""
    constraint_name: str
    column: str
    referenced_table: str
    referenced_column: str


@dataclass
class IndexInfo:
    """索引信息"""
    name: str
    unique: bool
    columns: List[str]


@dataclass
class TableDetail:
    """表的详细信息"""
    name: str
    columns: List[ColumnDetail]
    primary_keys: List[str]
    comment: Optional[str] = None
    foreign_keys: List[ForeignKeyInfo] = None
    indexes: List[IndexInfo] = None
    row_count: Optional[int] = None

    def __post_init__(self):
        if self.foreign_keys is None:
            self.foreign_keys = []
        if self.indexes is None:
            self.indexes = []


# ==================== 工具实现 ====================

class SchemaExtractionTool(BaseSemanticSQLTool):
    """数据库结构提取工具
    
    这是分析流程的第一步，负责从数据库中提取完整的架构信息。
    参考 nl2sql_pipeline 的实现，但作为独立的智能体工具。
    """
    
    name = "extract_database_schema"
    description = (
        "提取数据库的完整结构信息，包括表、列、主键、外键等。"
        "这是分析的第一步，为后续的领域分析和字段分类提供基础数据。"
    )
    
    def get_parameters(self) -> List[ToolParameter]:
        """获取工具参数定义"""
        return [
            ToolParameter(
                name="tables",
                type="list",
                description="要提取的表名列表，如果为空则提取所有表",
                required=False
            ),
            ToolParameter(
                name="include_row_count",
                type="boolean",
                description="是否包含行数统计",
                required=False
            ),
            ToolParameter(
                name="include_foreign_keys",
                type="boolean",
                description="是否包含外键信息",
                required=False
            ),
            ToolParameter(
                name="include_indexes",
                type="boolean",
                description="是否包含索引信息",
                required=False
            )
        ]
    
    def execute(
        self, 
        tables: Optional[List[str]] = None,
        include_row_count: bool = True,
        include_foreign_keys: bool = True,
        include_indexes: bool = False
    ) -> Union[Dict[str, Any], ToolExecResult]:
        """执行 schema 提取"""
        logger.info("开始提取数据库结构信息")
        
        # 获取数据库名称
        database_name = self._get_database_name()
        
        # 获取表列表
        if not tables:
            tables = self._get_all_tables()
        
        logger.info(f"需要提取的表数量: {len(tables)}")
        
        # 提取每个表的信息
        table_details = []
        for table_name in tables:
            table_info = self._extract_table_info(
                table_name,
                include_row_count=include_row_count,
                include_foreign_keys=include_foreign_keys,
                include_indexes=include_indexes
            )
            table_details.append(table_info)
        
        # 构建输出
        output = {
            "database_name": database_name,
            "tables_count": len(table_details),
            "tables": table_details,
            "summary": self._generate_summary(table_details)
        }
        
        logger.info(f"Schema 提取完成，共 {len(table_details)} 个表")
        
        return ToolExecResult(
            output=output,
            metadata={
                "database": database_name,
                "tables_extracted": len(table_details),
                "include_options": {
                    "row_count": include_row_count,
                    "foreign_keys": include_foreign_keys,
                    "indexes": include_indexes
                }
            }
        )
    
    def _get_database_name(self) -> str:
        """获取数据库名称"""
        try:
            # MySQL/PostgreSQL
            result = self.db.run("SELECT DATABASE()")
            if result:
                return str(result).strip()
        except:
            pass
        
        try:
            # SQLite
            result = self.db.run("PRAGMA database_list")
            if result:
                # 解析结果获取主数据库名
                return "main"
        except:
            pass
        
        return "unknown"
    
    def _get_all_tables(self) -> List[str]:
        """获取所有表名"""
        return self.db.get_usable_table_names()
    
    def _extract_table_info(
        self,
        table_name: str,
        include_row_count: bool = True,
        include_foreign_keys: bool = True,
        include_indexes: bool = False
    ) -> Dict[str, Any]:
        """提取单个表的信息"""
        logger.debug(f"提取表信息: {table_name}")
        
        # 获取列信息
        columns = self._get_columns_info(table_name)
        
        # 获取主键
        primary_keys = [col["name"] for col in columns if col.get("is_primary_key", False)]
        
        # 构建表信息
        table_detail = {
            "name": table_name,
            "columns": columns,
            "primary_keys": primary_keys
        }
        
        # 获取表注释
        comment = self._get_table_comment(table_name)
        if comment:
            table_detail["comment"] = comment
        
        # 获取行数
        if include_row_count:
            row_count = self._get_row_count(table_name)
            table_detail["row_count"] = row_count
        
        # 获取外键
        if include_foreign_keys:
            foreign_keys = self._get_foreign_keys(table_name)
            table_detail["foreign_keys"] = foreign_keys
        
        # 获取索引
        if include_indexes:
            indexes = self._get_indexes(table_name)
            table_detail["indexes"] = indexes
        
        return table_detail
    
    def _get_columns_info(self, table_name: str) -> List[Dict[str, Any]]:
        """获取列信息"""
        columns = []
        
        # 首先尝试从 DDL 中解析
        try:
            ddl = self._get_table_ddl(table_name)
            if ddl:
                columns = self._parse_columns_from_ddl(ddl)
        except:
            pass
        
        # 如果 DDL 解析失败，使用标准方法
        if not columns:
            # 使用 SQLAlchemy 的反射功能
            inspector = self.db._inspector
            columns_info = inspector.get_columns(table_name)
            
            for col in columns_info:
                column = {
                    "name": col["name"],
                    "data_type": str(col["type"]),
                    "is_nullable": col.get("nullable", True),
                    "default_value": str(col.get("default")) if col.get("default") else None,
                    "is_primary_key": col.get("primary_key", False),
                    "is_unique": col.get("unique", False),
                    "comment": col.get("comment")
                }
                columns.append(column)
        
        return columns
    
    def _get_table_ddl(self, table_name: str) -> Optional[str]:
        """获取表的 DDL"""
        try:
            # MySQL
            result = self.db.run(f"SHOW CREATE TABLE `{table_name}`")
            if result:
                # 结果通常是 (table_name, create_statement)
                if isinstance(result, (list, tuple)) and len(result) > 1:
                    return result[1]
                return str(result)
        except:
            pass
        
        try:
            # SQLite
            result = self.db.run(
                f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'"
            )
            if result:
                return str(result)
        except:
            pass
        
        return None
    
    def _parse_columns_from_ddl(self, ddl: str) -> List[Dict[str, Any]]:
        """从 DDL 中解析列信息"""
        columns = []
        
        # 简单的正则匹配
        import re
        
        # 查找 CREATE TABLE 语句中的列定义
        create_match = re.search(r'CREATE\s+TABLE[^(]+\((.*)\)', ddl, re.IGNORECASE | re.DOTALL)
        if not create_match:
            return columns
        
        content = create_match.group(1)
        
        # 分割列定义（简单处理，实际可能需要更复杂的解析）
        lines = content.split(',')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 跳过约束定义
            if any(keyword in line.upper() for keyword in ['PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE KEY', 'INDEX', 'CONSTRAINT']):
                continue
            
            # 解析列定义
            parts = line.split()
            if len(parts) >= 2:
                col_name = parts[0].strip('`"[]')
                col_type = parts[1]
                
                column = {
                    "name": col_name,
                    "data_type": col_type,
                    "is_nullable": 'NOT NULL' not in line.upper(),
                    "is_primary_key": 'PRIMARY KEY' in line.upper(),
                    "is_unique": 'UNIQUE' in line.upper()
                }
                
                # 提取注释
                comment_match = re.search(r"COMMENT\s+'([^']+)'", line, re.IGNORECASE)
                if comment_match:
                    column["comment"] = comment_match.group(1)
                
                columns.append(column)
        
        return columns
    
    def _get_table_comment(self, table_name: str) -> Optional[str]:
        """获取表注释"""
        try:
            # MySQL
            result = self.db.run(
                f"SELECT table_comment FROM information_schema.tables "
                f"WHERE table_schema = DATABASE() AND table_name = '{table_name}'"
            )
            if result:
                return str(result).strip()
        except:
            pass
        
        return None
    
    def _get_row_count(self, table_name: str) -> int:
        """获取表行数"""
        try:
            result = self.db.run(f"SELECT COUNT(*) FROM `{table_name}`")
            if result:
                # 处理不同格式的返回值
                if isinstance(result, (list, tuple)):
                    return int(result[0])
                elif isinstance(result, str):
                    # 提取数字
                    import re
                    match = re.search(r'\d+', result)
                    if match:
                        return int(match.group())
                else:
                    return int(result)
        except Exception as e:
            logger.warning(f"获取表 {table_name} 行数失败: {e}")
        
        return 0
    
    def _get_foreign_keys(self, table_name: str) -> List[Dict[str, Any]]:
        """获取外键信息"""
        foreign_keys = []
        
        try:
            # 使用 SQLAlchemy Inspector
            inspector = self.db._inspector
            fks = inspector.get_foreign_keys(table_name)
            
            for fk in fks:
                foreign_key = {
                    "constraint_name": fk.get("name", ""),
                    "column": fk["constrained_columns"][0] if fk.get("constrained_columns") else "",
                    "referenced_table": fk.get("referred_table", ""),
                    "referenced_column": fk["referred_columns"][0] if fk.get("referred_columns") else ""
                }
                foreign_keys.append(foreign_key)
        except Exception as e:
            logger.debug(f"获取外键信息失败: {e}")
        
        return foreign_keys
    
    def _get_indexes(self, table_name: str) -> List[Dict[str, Any]]:
        """获取索引信息"""
        indexes = []
        
        try:
            # 使用 SQLAlchemy Inspector
            inspector = self.db._inspector
            idx_list = inspector.get_indexes(table_name)
            
            for idx in idx_list:
                index = {
                    "name": idx.get("name", ""),
                    "unique": idx.get("unique", False),
                    "columns": idx.get("column_names", [])
                }
                indexes.append(index)
        except Exception as e:
            logger.debug(f"获取索引信息失败: {e}")
        
        return indexes
    
    def _generate_summary(self, tables: List[Dict[str, Any]]) -> str:
        """生成摘要信息"""
        total_tables = len(tables)
        total_columns = sum(len(t.get("columns", [])) for t in tables)
        total_rows = sum(t.get("row_count", 0) for t in tables)
        
        # 找出最大的表
        largest_table = max(tables, key=lambda t: t.get("row_count", 0)) if tables else None
        
        summary_parts = [
            f"数据库包含 {total_tables} 个表，共 {total_columns} 个列"
        ]
        
        if total_rows > 0:
            summary_parts.append(f"总数据量约 {total_rows:,} 行")
        
        if largest_table and largest_table.get("row_count", 0) > 0:
            summary_parts.append(
                f"最大的表是 {largest_table['name']}（{largest_table['row_count']:,} 行）"
            )
        
        # 统计外键关系
        total_foreign_keys = sum(len(t.get("foreign_keys", [])) for t in tables)
        if total_foreign_keys > 0:
            summary_parts.append(f"共有 {total_foreign_keys} 个外键关系")
        
        return "。".join(summary_parts) + "。"