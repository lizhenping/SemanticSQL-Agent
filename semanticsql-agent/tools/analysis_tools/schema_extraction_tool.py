"""
数据库结构提取工具 - 提取完整的数据库模式信息
基于 LangChain BaseTool
"""

from typing import Dict, Any, Type, List, Optional
import json
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from models.schemas import DatabaseSchema, TableInfo, ColumnInfo, ForeignKey
from models.exceptions import (
    ToolExecutionError, 
    DatabaseConnectionError,
    SchemaExtractionError
)
from utils.database import DatabaseManager


class SchemaExtractionInput(BaseModel):
    """Schema提取输入参数"""
    database_name: str = Field(description="数据库名称")
    include_views: bool = Field(default=False, description="是否包含视图")
    include_indexes: bool = Field(default=True, description="是否包含索引信息")
    sample_data: bool = Field(default=False, description="是否包含样本数据")
    tables: List[str] = Field(default_factory=list, description="指定要提取的表（空则提取所有）")


class SchemaExtractionTool(BaseTool):
    """数据库结构提取工具"""
    
    name: str = "schema_extraction"
    description: str = "提取数据库的完整结构信息，包括表、列、索引、外键等"
    args_schema: Type[BaseModel] = SchemaExtractionInput
    
    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager
    
    class Config:
        arbitrary_types_allowed = True
    
    def _run(
        self, 
        database_name: str,
        include_views: bool = False, 
        include_indexes: bool = True,
        sample_data: bool = False, 
        tables: List[str] = None
    ) -> str:
        """执行数据库结构提取"""
        try:
            if not self.db_manager:
                raise ToolExecutionError(
                    tool_name=self.name,
                    reason="数据库管理器未初始化"
                )
            
            # 获取数据库引擎
            engine = self.db_manager.engine
            if not engine:
                raise DatabaseConnectionError(
                    host=self.db_manager.config.host,
                    database=database_name,
                    original_error="数据库连接未建立"
                )
            
            # 提取表信息
            table_infos = {}
            
            # 获取表列表
            table_names = tables if tables else self.db_manager.get_tables()
            
            # 提取每个表的详细信息
            for table_name in table_names:
                table_info = self.db_manager.get_table_info(table_name)
                
                # 获取样本数据
                if sample_data:
                    samples = self._get_sample_data(table_name, limit=5)
                    table_info["sample_data"] = samples
                
                table_infos[table_name] = table_info
            
            # 构建返回结果
            result = {
                "database_name": database_name,
                "tables": table_infos,
                "table_count": len(table_infos),
                "extraction_params": {
                    "include_views": include_views,
                    "include_indexes": include_indexes,
                    "sample_data": sample_data
                }
            }
            
            # 返回JSON字符串格式的结果（LangChain要求）
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except DatabaseConnectionError:
            raise
        except Exception as e:
            raise SchemaExtractionError(
                database=database_name,
                error=str(e)
            )
    
    def _extract_table_info(
        self, 
        inspector, 
        table_name: str, 
        include_indexes: bool
    ) -> Dict[str, Any]:
        """提取单个表的信息"""
        # 获取列信息
        columns = []
        for col in inspector.get_columns(table_name):
            column_info = {
                "name": col["name"],
                "type": self._safe_type_string(col["type"]),
                "nullable": col.get("nullable", True),
                "default": col.get("default"),
                "autoincrement": col.get("autoincrement", False),
                "comment": col.get("comment", "")
            }
            columns.append(column_info)
        
        # 获取主键
        pk_constraint = inspector.get_pk_constraint(table_name)
        primary_keys = pk_constraint.get("constrained_columns", [])
        
        # 获取外键
        foreign_keys = []
        for fk in inspector.get_foreign_keys(table_name):
            foreign_key_info = {
                "name": fk.get("name"),
                "constrained_columns": fk.get("constrained_columns", []),
                "referred_table": fk.get("referred_table"),
                "referred_columns": fk.get("referred_columns", [])
            }
            foreign_keys.append(foreign_key_info)
        
        # 获取索引
        indexes = []
        if include_indexes:
            for idx in inspector.get_indexes(table_name):
                index_info = {
                    "name": idx.get("name"),
                    "columns": idx.get("column_names", []),
                    "unique": idx.get("unique", False)
                }
                indexes.append(index_info)
        
        # 获取表注释
        table_comment = ""
        try:
            # 尝试获取表注释（MySQL特定）
            result = self.db_manager.execute_query(
                f"SELECT table_comment FROM information_schema.tables "
                f"WHERE table_schema = DATABASE() AND table_name = '{table_name}'"
            )
            if result and len(result) > 0:
                table_comment = result[0].get("table_comment", "")
        except:
            pass
        
        return {
            "table_name": table_name,
            "columns": columns,
            "primary_keys": primary_keys,
            "foreign_keys": foreign_keys,
            "indexes": indexes,
            "comment": table_comment,
            "column_count": len(columns)
        }
    
    def _safe_type_string(self, column_type) -> str:
        """安全地转换列类型为字符串，处理特殊字符"""
        try:
            type_str = str(column_type)
            # 清理可能导致JSON解析问题的字符
            if "enum(" in type_str.lower():
                # 提取enum值并简化格式
                import re
                enum_match = re.search(r"enum\((.*?)\)", type_str, re.IGNORECASE)
                if enum_match:
                    enum_values = enum_match.group(1)
                    # 解析enum值列表，移除引号并用逗号分隔
                    values_list = []
                    for val in enum_values.split(','):
                        clean_val = val.strip().strip("'\"")
                        if clean_val:
                            values_list.append(clean_val)
                    return f"ENUM({','.join(values_list)})"
            
            # 移除其他可能的问题字符
            return type_str.replace('"', '').replace("'", "")
        except:
            return "UNKNOWN"
    
    def _get_sample_data(self, table_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """获取表的样本数据"""
        try:
            query = f"SELECT * FROM {table_name} LIMIT {limit}"
            result = self.db_manager.execute_query(query)
            return result if result else []
        except:
            return []
    
    async def _arun(
        self,
        database_name: str,
        include_views: bool = False,
        include_indexes: bool = True,
        sample_data: bool = False,
        tables: List[str] = None
    ) -> str:
        """异步执行（当前实现为同步）"""
        return self._run(
            database_name=database_name,
            include_views=include_views,
            include_indexes=include_indexes,
            sample_data=sample_data,
            tables=tables
        )