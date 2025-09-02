"""
数据库结构提取工具 - 提取完整的数据库模式信息
基于 LangChain BaseTool
"""

from typing import Dict, Any, Type, List, Optional
import json
from pydantic import BaseModel, Field

from models.schemas import DatabaseSchema, TableInfo, ColumnInfo, ForeignKey
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
    include_indexes: bool = Field(default=False, description="是否包含索引信息")
    sample_data: bool = Field(default=True, description="是否包含样本数据")
    tables: Optional[List[str]] = Field(
        default=None, description="指定要提取的表（空则提取所有）"
    )


class SchemaExtractionTool(BaseAnalysisTool):
    """数据库结构提取工具"""

    name: str = "schema_extraction"
    description: str = "提取数据库的完整结构信息，包括表、列、索引、外键等"
    args_schema: Type[BaseModel] = SchemaExtractionInput
    db_manager: DatabaseManager = Field(exclude=True)

    def __init__(self, db_manager: DatabaseManager):
        super().__init__(db_manager=db_manager)

    class Config:
        arbitrary_types_allowed = True

    def _run(
        self,
        database_name: str,
        include_views: bool = False,
        include_indexes: bool = False,
        sample_data: bool = True,
        tables: Optional[List[str]] = None,
    ) -> str:
        """执行数据库结构提取"""
        try:
            # Handle LangChain parameter passing - sometimes database_name is a JSON string
            if isinstance(database_name, str) and database_name.startswith('{'):
                try:
                    params = json.loads(database_name)
                    database_name = params.get("database_name", database_name)
                    include_views = params.get("include_views", include_views)
                    include_indexes = params.get("include_indexes", include_indexes) 
                    sample_data = params.get("sample_data", sample_data)
                    tables = params.get("tables", tables)
                except json.JSONDecodeError:
                    pass  # Use original parameter if JSON parsing fails
            if not self.db_manager:
                raise ToolExecutionError(
                    tool_name=self.name, reason="数据库管理器未初始化"
                )

            # 获取数据库引擎
            engine = self.db_manager.engine
            if not engine:
                raise DatabaseConnectionError(
                    host=self.db_manager.config.host,
                    database=database_name,
                    original_error="数据库连接未建立",
                )

            # 提取表信息
            table_infos = {}

            # 获取表列表
            all_table_names = tables if tables else self.db_manager.get_tables()

            # 根据参数选择要处理的表
            if tables:
                # 如果指定了特定表，只处理这些表
                selected_tables = [t for t in all_table_names if t in tables]
            else:
                # 否则处理所有表
                selected_tables = all_table_names

            # 提取每个表的详细信息
            for table_name in selected_tables:
                table_info = self._extract_table_info(
                    table_name, database_name, include_indexes, sample_data
                )

                table_infos[table_name] = table_info

            # 构建返回结果（参考pipeline格式）
            result = {
                "database_name": database_name,
                "tables": table_infos,
                "table_count": len(table_infos),
                "total_columns": sum(
                    len(info.get("columns", {})) for info in table_infos.values()
                ),
                "extraction_summary": {
                    "processed_tables": len(selected_tables),
                    "include_views": include_views,
                    "include_indexes": include_indexes,
                    "sample_data": sample_data,
                },
            }

            # 将结果保存到内存中供其他工具使用（暂时禁用避免FieldInfo错误）
            # if self._agent_memory:
            #     try:
            #         self._agent_memory.save_context(
            #             inputs={"tool_name": "schema_extraction"}, outputs=result
            #         )
            #     except Exception as e:
            #         print(f"Warning: Failed to save schema info to memory: {e}")

            # 返回JSON字符串格式的结果（LangChain要求）
            return json.dumps(result, ensure_ascii=False, indent=2)

        except DatabaseConnectionError:
            raise
        except Exception as e:
            raise SchemaExtractionError(database=database_name, error=str(e))

    def _extract_table_info(
        self,
        table_name: str,
        database_name: str,
        include_indexes: bool,
        sample_data: bool,
    ) -> Dict[str, Any]:
        """提取单个表的详细信息，采用pipeline的简洁设计

        参数:
            table_name: 表名
            database_name: 数据库名
            include_indexes: 是否包含索引信息
            sample_data: 是否包含样本数据

        返回:
            表信息字典
        """
        table_info = {
            "name": table_name,
            "comment": "",
            "columns": {},  # 改为字典格式，便于后续处理
            "primary_key": [],
            "row_count": 0,
        }

        try:
            # 步骤1：获取表基本信息（注释和行数）
            table_info.update(self._get_table_metadata(table_name, database_name))

            # 步骤2：获取列信息
            columns = self._get_columns_info(table_name, database_name)
            table_info["columns"] = columns

            # 步骤3：获取主键信息
            primary_keys = self._get_primary_keys(table_name, database_name)
            table_info["primary_key"] = primary_keys

            # 步骤4：添加样本数据（如果需要）
            if sample_data:
                table_info["sample_data"] = self._get_sample_data(table_name, limit=3)

        except Exception as e:
            print(f"提取表 {table_name} 信息时出错: {str(e)}")

        return table_info

    def _get_table_metadata(
        self, table_name: str, database_name: str
    ) -> Dict[str, Any]:
        """获取表的元数据信息"""
        metadata = {"comment": "", "row_count": 0}

        try:
            # 获取表注释和行数
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
            print(f"获取表 {table_name} 元数据失败: {str(e)}")

        return metadata

    def _get_columns_info(
        self, table_name: str, database_name: str
    ) -> Dict[str, Dict[str, Any]]:
        """获取列信息，返回字典格式"""
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
                        "default": self._safe_default_value(col["COLUMN_DEFAULT"]),
                        "comment": col["COLUMN_COMMENT"] or "",
                    }

        except Exception as e:
            print(f"获取表 {table_name} 列信息失败: {str(e)}")
            import traceback
            traceback.print_exc()

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
            print(f"获取表 {table_name} 主键失败: {str(e)}")

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

        # 处理enum类型
        if "enum" in data_type.lower():
            return self._safe_type_string(data_type)

        return data_type

    def _safe_default_value(self, default_value) -> Any:
        """安全处理默认值"""
        if default_value is None:
            return None

        # 转换为字符串并清理
        str_value = str(default_value).strip()

        # 处理常见的默认值
        if str_value.upper() in ("NULL", "CURRENT_TIMESTAMP"):
            return str_value.upper()

        return str_value

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
                    for val in enum_values.split(","):
                        clean_val = val.strip().strip("'\"")
                        if clean_val:
                            values_list.append(clean_val)
                    return f"ENUM({','.join(values_list)})"

            # 移除其他可能的问题字符
            return type_str.replace('"', "").replace("'", "")
        except:
            return "UNKNOWN"

    def _get_sample_data(self, table_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """获取表的样本数据，优化JSON序列化"""
        try:
            query = f"SELECT * FROM {table_name} LIMIT {limit}"
            result = self.db_manager._execute_query(query)
            if result.get("success") and result.get("data"):
                return self._serialize_sample_data(result["data"])
            return []
        except Exception as e:
            print(f"获取表 {table_name} 样本数据失败: {str(e)}")
            return []

    def _serialize_sample_data(
        self, raw_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """序列化样本数据，确保JSON兼容"""
        serializable_data = []

        for row in raw_data:
            serializable_row = {}
            for key, value in row.items():
                serializable_row[key] = self._serialize_value(value)
            serializable_data.append(serializable_row)

        return serializable_data

    def _serialize_value(self, value) -> Any:
        """序列化单个值"""
        if value is None:
            return None
        elif hasattr(value, "isoformat"):  # 日期时间类型
            return value.isoformat()
        elif isinstance(value, (bytes, bytearray)):  # 二进制数据
            return f"<binary_data:{len(value)}_bytes>"
        elif isinstance(value, (int, float, str, bool)):
            return value
        else:
            # 其他复杂类型转换为字符串
            return str(value)

    async def _arun(
        self,
        database_name: str,
        include_views: bool = False,
        include_indexes: bool = False,
        sample_data: bool = True,
        tables: Optional[List[str]] = None,
    ) -> str:
        """异步执行数据库结构提取"""
        return self._run(
            database_name=database_name,
            include_views=include_views,
            include_indexes=include_indexes,
            sample_data=sample_data,
            tables=tables,
        )
