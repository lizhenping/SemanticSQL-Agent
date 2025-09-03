"""
数据库结构提取工具 - 提取完整的数据库模式信息
基于 LangChain BaseTool，参考pipeline的简洁设计
"""

from typing import Dict, Any, Type, List, Optional
from pydantic import BaseModel, Field

from models.exceptions import (
    ToolExecutionError,
    DatabaseConnectionError,
    SchemaExtractionError,
)
from utils.database import DatabaseManager
from .base_analysis_tool import BaseAnalysisTool


class SchemaExtractionInput(BaseModel):
    """Schema提取输入参数"""
    database_name: str = Field(description="数据库名称")
    include_views: bool = Field(default=False, description="是否包含视图")
    sample_data: bool = Field(default=True, description="是否包含样本数据")
    tables: Optional[List[str]] = Field(default=None, description="指定要提取的表")


class SchemaExtractionTool(BaseAnalysisTool):
    """数据库结构提取工具"""

    name: str = "schema_extraction"
    description: str = "提取数据库的完整结构信息，包括表、列、索引、外键等"
    args_schema: Type[BaseModel] = SchemaExtractionInput

    def __init__(self, db_manager: DatabaseManager, **kwargs):
        super().__init__(**kwargs)
        # 使用object.__setattr__避开Pydantic验证
        object.__setattr__(self, 'db_manager', db_manager)

    def _run(
        self,
        database_name: str,
        include_views: bool = False,
        sample_data: bool = True,
        tables: Optional[List[str]] = None,
    ) -> str:
        """执行数据库结构提取"""
        try:
            if not self.db_manager:
                raise ToolExecutionError(
                    tool_name=self.name, reason="数据库管理器未初始化"
                )

            # 获取表列表
            all_tables = tables if tables else self.db_manager.get_tables()
            
            # 提取每个表的信息
            table_infos = {}
            for table_name in all_tables:
                table_infos[table_name] = self._extract_table_info(
                    table_name, database_name, sample_data
                )

            # 构建返回结果
            result = {
                "database_name": database_name,
                "tables": table_infos,
                "table_count": len(table_infos),
                "total_columns": sum(
                    len(info.get("columns", {})) for info in table_infos.values()
                ),
            }

            # 保存到记忆
            self.save_to_memory("schema_extraction", result)

            # 返回字典格式，让Agent决定如何序列化
            return result

        except DatabaseConnectionError:
            raise
        except Exception as e:
            raise SchemaExtractionError(database=database_name, error=str(e))

    def _extract_table_info(
        self,
        table_name: str,
        database_name: str,
        sample_data: bool,
    ) -> Dict[str, Any]:
        """提取单个表的详细信息"""
        table_info = {
            "name": table_name,
            "columns": {},
            "primary_key": [],
        }

        try:
            # 获取表基本信息
            table_info.update(self._get_table_metadata(table_name, database_name))
            
            # 获取列信息
            table_info["columns"] = self._get_columns_info(table_name, database_name)
            
            # 获取主键信息
            table_info["primary_key"] = self._get_primary_keys(table_name, database_name)
            
            # 获取样本数据
            if sample_data:
                table_info["sample_data"] = self._get_sample_data(table_name, limit=3)

        except Exception as e:
            self.logger.error(f"提取表 {table_name} 信息时出错: {str(e)}")

        return table_info

    def _get_table_metadata(self, table_name: str, database_name: str) -> Dict[str, Any]:
        """获取表的元数据信息"""
        metadata = {"comment": "", "row_count": 0}

        try:
            query = """
            SELECT table_comment, table_rows
            FROM information_schema.tables 
            WHERE table_schema = :database_name AND table_name = :table_name
            """
            result = self.db_manager._execute_query(
                query, {"database_name": database_name, "table_name": table_name}
            )

            if result.get("success") and result.get("data"):
                row = result["data"][0]
                metadata["comment"] = row.get("TABLE_COMMENT", "") or ""
                metadata["row_count"] = int(row.get("TABLE_ROWS", 0) or 0)

        except Exception as e:
            self.logger.warning(f"获取表 {table_name} 元数据失败: {str(e)}")

        return metadata

    def _get_columns_info(
        self, table_name: str, database_name: str
    ) -> Dict[str, Dict[str, Any]]:
        """获取列信息"""
        columns = {}

        try:
            query = """
            SELECT 
                column_name,
                data_type,
                is_nullable,
                column_default,
                column_comment,
                character_maximum_length,
                numeric_precision,
                numeric_scale
            FROM information_schema.columns 
            WHERE table_schema = :database_name AND table_name = :table_name 
            ORDER BY ordinal_position
            """

            result = self.db_manager._execute_query(
                query, {"database_name": database_name, "table_name": table_name}
            )

            if result.get("success") and result.get("data"):
                for col in result["data"]:
                    col_name = col["COLUMN_NAME"]
                    columns[col_name] = {
                        "name": col_name,
                        "type": self._format_column_type(col),
                        "nullable": col["IS_NULLABLE"] == "YES",
                        "default": col["COLUMN_DEFAULT"],
                        "comment": col["COLUMN_COMMENT"] or "",
                    }

        except Exception as e:
            self.logger.error(f"获取表 {table_name} 列信息失败: {str(e)}")

        return columns

    def _get_primary_keys(self, table_name: str, database_name: str) -> List[str]:
        """获取主键列表"""
        primary_keys = []

        try:
            query = """
            SELECT column_name 
            FROM information_schema.key_column_usage 
            WHERE table_schema = :database_name 
              AND table_name = :table_name 
              AND constraint_name = 'PRIMARY'
            ORDER BY ordinal_position
            """

            result = self.db_manager._execute_query(
                query, {"database_name": database_name, "table_name": table_name}
            )

            if result.get("success") and result.get("data"):
                primary_keys = [row["COLUMN_NAME"] for row in result["data"]]

        except Exception as e:
            self.logger.warning(f"获取表 {table_name} 主键失败: {str(e)}")

        return primary_keys

    def _format_column_type(self, col_data: Dict[str, Any]) -> str:
        """格式化列类型信息"""
        data_type = col_data["DATA_TYPE"]
        max_length = col_data.get("CHARACTER_MAXIMUM_LENGTH")
        precision = col_data.get("NUMERIC_PRECISION")
        scale = col_data.get("NUMERIC_SCALE")

        # 处理字符串类型
        if data_type in ("varchar", "char") and max_length:
            return f"{data_type}({max_length})"

        # 处理数字类型
        if data_type in ("decimal", "numeric") and precision:
            if scale:
                return f"{data_type}({precision},{scale})"
            else:
                return f"{data_type}({precision})"

        return data_type

    def _get_sample_data(self, table_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """获取表的样本数据"""
        try:
            query = f"SELECT * FROM {table_name} LIMIT {limit}"
            result = self.db_manager._execute_query(query)
            if result.get("success") and result.get("data"):
                return self._serialize_sample_data(result["data"])
            return []
        except Exception as e:
            self.logger.warning(f"获取表 {table_name} 样本数据失败: {str(e)}")
            return []

    def _serialize_sample_data(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """序列化样本数据，确保JSON兼容"""
        serializable_data = []

        for row in raw_data:
            serializable_row = {}
            for key, value in row.items():
                if value is None:
                    serializable_row[key] = None
                elif hasattr(value, "isoformat"):  # 日期时间类型
                    serializable_row[key] = value.isoformat()
                elif isinstance(value, (bytes, bytearray)):  # 二进制数据
                    serializable_row[key] = f"<binary_data:{len(value)}_bytes>"
                else:
                    serializable_row[key] = value
            serializable_data.append(serializable_row)

        return serializable_data