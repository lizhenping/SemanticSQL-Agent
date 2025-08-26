"""数据库架构检查器

负责检查和获取数据库的元数据信息。
"""

import logging
from typing import List, Dict, Any, Optional

from ....models.database import TableInfo, ColumnInfo

logger = logging.getLogger(__name__)


class MySQLSchemaInspector:
    """MySQL架构检查器
    
    职责：
    1. 获取数据库架构信息
    2. 检查表和列的元数据
    3. 获取约束和索引信息
    """
    
    def __init__(self, query_executor):
        """初始化架构检查器
        
        参数:
            query_executor: 查询执行器实例
        """
        self.executor = query_executor
    
    def get_databases(self) -> List[str]:
        """获取所有数据库列表
        
        返回:
            数据库名列表
        """
        query = """
        SELECT SCHEMA_NAME 
        FROM INFORMATION_SCHEMA.SCHEMATA
        WHERE SCHEMA_NAME NOT IN ('information_schema', 'mysql', 'performance_schema', 'sys')
        ORDER BY SCHEMA_NAME
        """
        
        results = self.executor.execute_query(query)
        return [row['SCHEMA_NAME'] for row in results]
    
    def get_tables(self, schema: Optional[str] = None) -> List[str]:
        """获取表列表
        
        参数:
            schema: 数据库名（为None时使用当前数据库）
            
        返回:
            表名列表
        """
        if schema:
            query = """
            SELECT TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = %s
            AND TABLE_TYPE = 'BASE TABLE'
            AND TABLE_NAME != 'aid_info'
            ORDER BY TABLE_NAME
            """
            params = (schema,)
        else:
            query = """
            SELECT TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_TYPE = 'BASE TABLE'
            AND TABLE_NAME != 'aid_info'
            ORDER BY TABLE_NAME
            """
            params = None
        
        results = self.executor.execute_query(query, params)
        return [row['TABLE_NAME'] for row in results]
    
    def get_table_info(self, table_name: str, schema: Optional[str] = None) -> Optional[TableInfo]:
        """获取表的详细信息
        
        参数:
            table_name: 表名
            schema: 数据库名
            
        返回:
            表信息对象或None
        """
        # 获取表注释
        comment = self.get_table_comment(table_name, schema)
        
        # 获取列信息
        columns = self.get_columns(table_name, schema)
        if not columns:
            return None
        
        # 获取主键
        primary_key = self.get_primary_key(table_name, schema)
        
        # 获取外键
        foreign_keys = self.get_foreign_keys(table_name, schema)
        
        # 获取索引
        indexes = self.get_indexes(table_name, schema)
        
        # 构建TableInfo对象
        return TableInfo(
            name=table_name,
            columns=columns,
            primary_key=primary_key,
            foreign_keys=foreign_keys,
            indexes=indexes,
            comment=comment,
            schema=schema
        )
    
    def get_columns(self, table_name: str, schema: Optional[str] = None) -> List[ColumnInfo]:
        """获取表的列信息
        
        参数:
            table_name: 表名
            schema: 数据库名
            
        返回:
            列信息列表
        """
        if schema:
            query = """
            SELECT 
                COLUMN_NAME,
                DATA_TYPE,
                CHARACTER_MAXIMUM_LENGTH,
                NUMERIC_PRECISION,
                NUMERIC_SCALE,
                IS_NULLABLE,
                COLUMN_DEFAULT,
                COLUMN_KEY,
                EXTRA,
                COLUMN_COMMENT,
                ORDINAL_POSITION
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s
            AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
            """
            params = (schema, table_name)
        else:
            query = """
            SELECT 
                COLUMN_NAME,
                DATA_TYPE,
                CHARACTER_MAXIMUM_LENGTH,
                NUMERIC_PRECISION,
                NUMERIC_SCALE,
                IS_NULLABLE,
                COLUMN_DEFAULT,
                COLUMN_KEY,
                EXTRA,
                COLUMN_COMMENT,
                ORDINAL_POSITION
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
            """
            params = (table_name,)
        
        results = self.executor.execute_query(query, params)
        
        columns = []
        for row in results:
            # 构建完整的数据类型
            data_type = self._build_data_type(row)
            
            column = ColumnInfo(
                name=row['COLUMN_NAME'],
                data_type=data_type,
                nullable=row['IS_NULLABLE'] == 'YES',
                default_value=row['COLUMN_DEFAULT'],
                comment=row['COLUMN_COMMENT'] or None,
                is_primary_key=row['COLUMN_KEY'] == 'PRI',
                is_unique=row['COLUMN_KEY'] == 'UNI',
                is_foreign_key=row['COLUMN_KEY'] == 'MUL',
                auto_increment='auto_increment' in row['EXTRA'].lower(),
                ordinal_position=row['ORDINAL_POSITION']
            )
            columns.append(column)
        
        return columns
    
    def get_primary_key(self, table_name: str, schema: Optional[str] = None) -> Optional[List[str]]:
        """获取表的主键信息
        
        参数:
            table_name: 表名
            schema: 数据库名
            
        返回:
            主键列名列表或None
        """
        if schema:
            query = """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = %s
            AND TABLE_NAME = %s
            AND CONSTRAINT_NAME = 'PRIMARY'
            ORDER BY ORDINAL_POSITION
            """
            params = (schema, table_name)
        else:
            query = """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = %s
            AND CONSTRAINT_NAME = 'PRIMARY'
            ORDER BY ORDINAL_POSITION
            """
            params = (table_name,)
        
        results = self.executor.execute_query(query, params)
        
        if results:
            return [row['COLUMN_NAME'] for row in results]
        
        return None
    
    def get_foreign_keys(self, table_name: str, schema: Optional[str] = None) -> List[Dict[str, str]]:
        """获取表的外键信息
        
        参数:
            table_name: 表名
            schema: 数据库名
            
        返回:
            外键信息列表
        """
        if schema:
            query = """
            SELECT 
                CONSTRAINT_NAME,
                COLUMN_NAME,
                REFERENCED_TABLE_SCHEMA,
                REFERENCED_TABLE_NAME,
                REFERENCED_COLUMN_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = %s
            AND TABLE_NAME = %s
            AND REFERENCED_TABLE_NAME IS NOT NULL
            ORDER BY CONSTRAINT_NAME, ORDINAL_POSITION
            """
            params = (schema, table_name)
        else:
            query = """
            SELECT 
                CONSTRAINT_NAME,
                COLUMN_NAME,
                REFERENCED_TABLE_SCHEMA,
                REFERENCED_TABLE_NAME,
                REFERENCED_COLUMN_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = %s
            AND REFERENCED_TABLE_NAME IS NOT NULL
            ORDER BY CONSTRAINT_NAME, ORDINAL_POSITION
            """
            params = (table_name,)
        
        results = self.executor.execute_query(query, params)
        
        foreign_keys = []
        for row in results:
            fk = {
                'constraint_name': row['CONSTRAINT_NAME'],
                'column': row['COLUMN_NAME'],
                'referenced_schema': row['REFERENCED_TABLE_SCHEMA'],
                'referenced_table': row['REFERENCED_TABLE_NAME'],
                'referenced_column': row['REFERENCED_COLUMN_NAME']
            }
            foreign_keys.append(fk)
        
        return foreign_keys
    
    def get_indexes(self, table_name: str, schema: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取表的索引信息
        
        参数:
            table_name: 表名
            schema: 数据库名
            
        返回:
            索引信息列表
        """
        if schema:
            query = """
            SELECT 
                INDEX_NAME,
                COLUMN_NAME,
                NON_UNIQUE,
                SEQ_IN_INDEX,
                INDEX_TYPE
            FROM INFORMATION_SCHEMA.STATISTICS
            WHERE TABLE_SCHEMA = %s
            AND TABLE_NAME = %s
            ORDER BY INDEX_NAME, SEQ_IN_INDEX
            """
            params = (schema, table_name)
        else:
            query = """
            SELECT 
                INDEX_NAME,
                COLUMN_NAME,
                NON_UNIQUE,
                SEQ_IN_INDEX,
                INDEX_TYPE
            FROM INFORMATION_SCHEMA.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = %s
            ORDER BY INDEX_NAME, SEQ_IN_INDEX
            """
            params = (table_name,)
        
        results = self.executor.execute_query(query, params)
        
        # 组织索引信息
        indexes_dict = {}
        for row in results:
            index_name = row['INDEX_NAME']
            if index_name not in indexes_dict:
                indexes_dict[index_name] = {
                    'name': index_name,
                    'columns': [],
                    'unique': not row['NON_UNIQUE'],
                    'type': row['INDEX_TYPE']
                }
            indexes_dict[index_name]['columns'].append(row['COLUMN_NAME'])
        
        return list(indexes_dict.values())
    
    def get_table_comment(self, table_name: str, schema: Optional[str] = None) -> Optional[str]:
        """获取表的注释
        
        参数:
            table_name: 表名
            schema: 数据库名
            
        返回:
            表注释或None
        """
        if schema:
            query = """
            SELECT TABLE_COMMENT
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = %s
            AND TABLE_NAME = %s
            """
            params = (schema, table_name)
        else:
            query = """
            SELECT TABLE_COMMENT
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = %s
            """
            params = (table_name,)
        
        result = self.executor.execute_single(query, params)
        
        if result and result['TABLE_COMMENT']:
            return result['TABLE_COMMENT']
        
        return None
    
    def get_table_row_count(self, table_name: str, schema: Optional[str] = None) -> int:
        """获取表的行数
        
        参数:
            table_name: 表名
            schema: 数据库名
            
        返回:
            行数
        """
        return self.executor.count_rows(table_name, schema)
    
    def _build_data_type(self, column_info: Dict[str, Any]) -> str:
        """构建完整的数据类型字符串
        
        参数:
            column_info: 列信息字典
            
        返回:
            数据类型字符串
        """
        data_type = column_info['DATA_TYPE']
        
        # 处理字符串类型
        if data_type in ['varchar', 'char', 'binary', 'varbinary']:
            if column_info['CHARACTER_MAXIMUM_LENGTH']:
                data_type = f"{data_type}({column_info['CHARACTER_MAXIMUM_LENGTH']})"
        
        # 处理数值类型
        elif data_type in ['decimal', 'numeric']:
            if column_info['NUMERIC_PRECISION'] and column_info['NUMERIC_SCALE']:
                data_type = f"{data_type}({column_info['NUMERIC_PRECISION']},{column_info['NUMERIC_SCALE']})"
        
        # 处理整数类型（可能有显示宽度）
        elif data_type in ['int', 'tinyint', 'smallint', 'mediumint', 'bigint']:
            # MySQL 8.0.17后不再支持显示宽度，所以这里不添加
            pass
        
        return data_type