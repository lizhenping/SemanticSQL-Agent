"""数据库结构提取工具

参考 nl2sql_pipeline 的 schema_extraction_pipeline 实现，
但使用智能体工具模式而非管道模式。
"""

from tools.base import BaseSemanticSQLTool, ToolExecResult, ToolParameter
from typing import List, Dict, Any, Optional, Union
from models.analysis_models import (
    SchemaExtractionInput,
    SchemaExtractionOutput,
    TableDetail,
    ColumnDetail,
    ForeignKeyInfo,
    IndexInfo
)
import logging

logger = logging.getLogger(__name__)


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
    args_schema = SchemaExtractionInput
    
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
    ) -> Union[SchemaExtractionOutput, ToolExecResult]:
        """执行 schema 提取"""
        logger.info("开始提取数据库结构信息")
        
        # 获取数据库名称
        database_name = self._get_database_name()
        
        # 获取表列表
        if not tables:
            tables = self._get_all_tables()
            logger.info(f"未指定表，获取所有表: {len(tables)} 个")
        else:
            # 验证表是否存在
            available_tables = set(self._get_all_tables())
            invalid_tables = set(tables) - available_tables
            if invalid_tables:
                logger.warning(f"以下表不存在: {invalid_tables}")
                tables = [t for t in tables if t in available_tables]
        
        # 提取每个表的详细信息
        table_infos = []
        for table_name in tables:
            try:
                table_info = self._extract_table_info(
                    table_name,
                    include_row_count,
                    include_foreign_keys,
                    include_indexes
                )
                table_infos.append(table_info)
            except Exception as e:
                logger.error(f"提取表 {table_name} 信息失败: {e}")
                continue
        
        # 构建结果
        result = SchemaExtractionOutput(
            database_name=database_name,
            tables_count=len(table_infos),
            tables=table_infos,
            extraction_config={
                "include_row_count": include_row_count,
                "include_foreign_keys": include_foreign_keys,
                "include_indexes": include_indexes
            },
            summary=self._generate_summary(table_infos)
        )
        
        logger.info(f"结构提取完成: {len(table_infos)} 个表")
        return result
    
    def _get_database_name(self) -> str:
        """获取数据库名称"""
        try:
            result = self.db.run("SELECT DATABASE()")
            if result:
                # 解析结果
                import re
                match = re.search(r"'([^']+)'", result)
                if match:
                    return match.group(1)
            return "unknown"
        except Exception:
            return "unknown"
    
    def _get_all_tables(self) -> List[str]:
        """获取所有表名"""
        return self.db.get_usable_table_names()
    
    def _extract_table_info(
        self,
        table_name: str,
        include_row_count: bool,
        include_foreign_keys: bool,
        include_indexes: bool
    ) -> TableDetail:
        """提取单个表的详细信息"""
        logger.debug(f"提取表 {table_name} 的信息")
        
        # 获取列信息
        columns = self._get_columns_info(table_name)
        
        # 提取主键
        primary_keys = [col.name for col in columns if col.is_primary_key]
        
        # 创建表详情
        table_detail = TableDetail(
            name=table_name,
            comment=self._get_table_comment(table_name),
            columns=columns,
            primary_keys=primary_keys,
            foreign_keys=[],
            indexes=[]
        )
        
        # 获取行数
        if include_row_count:
            table_detail.row_count = self._get_row_count(table_name)
        
        # 获取外键
        if include_foreign_keys:
            table_detail.foreign_keys = self._get_foreign_keys(table_name)
        
        # 获取索引
        if include_indexes:
            table_detail.indexes = self._get_indexes(table_name)
        
        return table_detail
    
    def _get_table_comment(self, table_name: str) -> Optional[str]:
        """获取表注释"""
        try:
            sql = f"""
            SELECT TABLE_COMMENT 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '{table_name}'
            """
            result = self.db.run(sql)
            if result and "TABLE_COMMENT" in result:
                # 解析结果
                import re
                match = re.search(r"'([^']*)'", result)
                if match:
                    comment = match.group(1)
                    return comment if comment else None
        except Exception as e:
            logger.debug(f"获取表 {table_name} 注释失败: {e}")
        return None
    
    def _get_columns_info(self, table_name: str) -> List[ColumnDetail]:
        """获取列信息"""
        try:
            # 使用 INFORMATION_SCHEMA 获取详细的列信息
            sql = f"""
            SELECT 
                COLUMN_NAME,
                DATA_TYPE,
                IS_NULLABLE,
                COLUMN_DEFAULT,
                COLUMN_KEY,
                COLUMN_COMMENT,
                CHARACTER_MAXIMUM_LENGTH,
                NUMERIC_PRECISION,
                NUMERIC_SCALE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '{table_name}'
            ORDER BY ORDINAL_POSITION
            """
            
            result = self.db.run(sql)
            
            # 解析结果
            columns = []
            if result:
                # 简单的文本解析（实际应该使用更可靠的方法）
                lines = result.strip().split('\n')
                if len(lines) > 1:
                    # 跳过标题行
                    for line in lines[1:]:
                        if line.strip() and not line.startswith('-'):
                            parts = [p.strip() for p in line.split('|')]
                            if len(parts) >= 6:
                                col_detail = ColumnDetail(
                                    name=parts[0],
                                    data_type=self._format_data_type(parts[1], parts[6], parts[7], parts[8]),
                                    is_nullable=parts[2] == 'YES',
                                    default_value=parts[3] if parts[3] != 'NULL' else None,
                                    is_primary_key='PRI' in parts[4],
                                    is_unique='UNI' in parts[4],
                                    is_foreign_key='MUL' in parts[4],
                                    comment=parts[5] if parts[5] and parts[5] != 'NULL' else None
                                )
                                columns.append(col_detail)
            
            # 如果解析失败，使用备用方法
            if not columns:
                # 使用 LangChain 的方法获取基本信息
                table_info = self.db.get_table_info_no_throw([table_name])
                columns = self._parse_columns_from_ddl(table_info)
            
            return columns
            
        except Exception as e:
            logger.error(f"获取表 {table_name} 列信息失败: {e}")
            # 降级到基本方法
            table_info = self.db.get_table_info_no_throw([table_name])
            return self._parse_columns_from_ddl(table_info)
    
    def _format_data_type(self, base_type: str, max_length: str, precision: str, scale: str) -> str:
        """格式化数据类型"""
        base_type = base_type.upper()
        
        if base_type in ['VARCHAR', 'CHAR'] and max_length and max_length != 'NULL':
            return f"{base_type}({max_length})"
        elif base_type == 'DECIMAL' and precision != 'NULL' and scale != 'NULL':
            return f"{base_type}({precision},{scale})"
        elif base_type in ['INT', 'BIGINT', 'SMALLINT', 'TINYINT'] and precision != 'NULL':
            return f"{base_type}({precision})"
        else:
            return base_type
    
    def _parse_columns_from_ddl(self, ddl: str) -> List[ColumnDetail]:
        """从 DDL 中解析列信息（备用方法）"""
        columns = []
        if not ddl:
            return columns
        
        lines = ddl.split('\n')
        for line in lines:
            line = line.strip()
            if not line or line.startswith('CREATE') or line.startswith(')') or line.startswith('PRIMARY'):
                continue
            
            # 简单的列解析
            parts = line.split()
            if len(parts) >= 2:
                col_name = parts[0].strip('`,"')
                col_type = parts[1].strip(',')
                
                col_detail = ColumnDetail(
                    name=col_name,
                    data_type=col_type,
                    is_nullable='NOT NULL' not in line.upper(),
                    is_primary_key=False,  # 需要单独查询
                    default_value=None,
                    comment=None
                )
                columns.append(col_detail)
        
        return columns
    
    def _get_row_count(self, table_name: str) -> Optional[int]:
        """获取表的行数"""
        try:
            result = self.db.run(f"SELECT COUNT(*) AS cnt FROM `{table_name}`")
            if result:
                # 解析结果
                import re
                match = re.search(r'\d+', result)
                if match:
                    return int(match.group())
        except Exception as e:
            logger.debug(f"获取表 {table_name} 行数失败: {e}")
        return None
    
    def _get_foreign_keys(self, table_name: str) -> List[ForeignKeyInfo]:
        """获取外键信息"""
        foreign_keys = []
        try:
            sql = f"""
            SELECT 
                CONSTRAINT_NAME,
                COLUMN_NAME,
                REFERENCED_TABLE_NAME,
                REFERENCED_COLUMN_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = '{table_name}'
                AND REFERENCED_TABLE_NAME IS NOT NULL
            """
            
            result = self.db.run(sql)
            if result:
                # 简单解析
                lines = result.strip().split('\n')
                if len(lines) > 1:
                    for line in lines[1:]:
                        if line.strip() and not line.startswith('-'):
                            parts = [p.strip() for p in line.split('|')]
                            if len(parts) >= 4:
                                fk_info = ForeignKeyInfo(
                                    constraint_name=parts[0],
                                    column=parts[1],
                                    referenced_table=parts[2],
                                    referenced_column=parts[3]
                                )
                                foreign_keys.append(fk_info)
        except Exception as e:
            logger.debug(f"获取表 {table_name} 外键失败: {e}")
        
        return foreign_keys
    
    def _get_indexes(self, table_name: str) -> List[IndexInfo]:
        """获取索引信息"""
        indexes = []
        try:
            result = self.db.run(f"SHOW INDEX FROM `{table_name}`")
            if result:
                # 简单解析索引信息
                lines = result.strip().split('\n')
                if len(lines) > 1:
                    index_map = {}
                    for line in lines[1:]:
                        if line.strip() and not line.startswith('-'):
                            parts = [p.strip() for p in line.split('|')]
                            if len(parts) >= 5:
                                key_name = parts[2]
                                if key_name not in index_map:
                                    index_map[key_name] = IndexInfo(
                                        name=key_name,
                                        unique=parts[1] == '0',
                                        columns=[]
                                    )
                                index_map[key_name].columns.append(parts[4])
                    
                    indexes = list(index_map.values())
        except Exception as e:
            logger.debug(f"获取表 {table_name} 索引失败: {e}")
        
        return indexes
    
    def _generate_summary(self, table_infos: List[TableDetail]) -> Dict[str, Any]:
        """生成结构摘要"""
        total_columns = sum(len(t.columns) for t in table_infos)
        total_rows = sum(t.row_count for t in table_infos if t.row_count)
        
        # 统计数据类型
        type_stats = {}
        for table in table_infos:
            for col in table.columns:
                data_type = col.data_type.split('(')[0].upper()
                type_stats[data_type] = type_stats.get(data_type, 0) + 1
        
        # 找出有外键关系的表
        tables_with_fk = [
            t.name for t in table_infos 
            if t.foreign_keys
        ]
        
        return {
            "total_tables": len(table_infos),
            "total_columns": total_columns,
            "total_rows": total_rows,
            "data_type_distribution": type_stats,
            "tables_with_foreign_keys": tables_with_fk,
            "average_columns_per_table": round(total_columns / len(table_infos), 1) if table_infos else 0
        }