"""
数据库结构提取工具 - 优化版本
简化设计，移除过度异常处理，按就近原则组织代码
"""

from typing import Dict, Any, Type, List, Optional
import json
from pydantic import BaseModel, Field

from models.exceptions import ToolExecutionError
from utils.database import DatabaseManager
from ..base_tool import BaseSemanticSQLTool


# ========== 工具内部数据模型（就近原则）==========
class SchemaExtractionInput(BaseModel):
    """Schema提取输入参数"""
    database_name: str = Field(description="数据库名称")
    include_views: bool = Field(default=False, description="是否包含视图")
    sample_data: bool = Field(default=True, description="是否包含样本数据")
    tables: Optional[List[str]] = Field(default=None, description="指定要提取的表")


class SchemaInfo(BaseModel):
    """数据库结构信息"""
    database_name: str
    tables: Dict[str, Dict[str, Any]]
    table_count: int
    total_columns: int


class SchemaExtractionTool(BaseSemanticSQLTool):
    """数据库结构提取工具 - 优化版本
    
    职责：
    - 提取数据库完整结构信息
    - 获取表、列、主键、外键等元数据
    - 支持样本数据提取
    
    设计原则：
    - 单一职责：专注结构提取
    - 简化异常：让异常自然传播
    - 类型安全：使用Pydantic模型
    """

    name: str = "schema_extraction"
    description: str = "提取数据库的完整结构信息，包括表、列、索引、外键等"
    args_schema: Type[BaseModel] = SchemaExtractionInput

    def __init__(self, db_manager: DatabaseManager = None, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, 'db_manager', db_manager)

    def _run(
        self,
        database_name: str,
        include_views: bool = False,
        sample_data: bool = True,
        tables: Optional[List[str]] = None,
        **kwargs
    ) -> str:
        """执行数据库结构提取 - 简化版本"""
        # 获取数据库管理器
        db_manager = self._get_database_manager()
        
        # 获取表列表并提取信息
        target_tables = tables if tables else db_manager.get_tables()
        table_infos = self._extract_all_tables_info(
            target_tables, database_name, sample_data, db_manager
        )
        
        # 构建结果
        result = self._build_schema_result(database_name, table_infos)
        
        # 保存并返回
        self.save_to_memory("schema_extraction", result)
        return json.dumps(result, ensure_ascii=False)

    # ========== 核心提取逻辑 ==========
    def _get_database_manager(self) -> DatabaseManager:
        """获取数据库管理器"""
        if self.db_manager:
            return self.db_manager
        
        # 从记忆获取（向后兼容）
        db_manager = self.get_from_memory("database_manager")
        if not db_manager:
            raise ToolExecutionError(
                tool_name=self.name,
                reason="数据库管理器未初始化"
            )
        return db_manager

    def _extract_all_tables_info(
        self,
        tables: List[str],
        database_name: str,
        sample_data: bool,
        db_manager: DatabaseManager
    ) -> Dict[str, Dict[str, Any]]:
        """提取所有表的信息"""
        table_infos = {}
        for table_name in tables:
            table_infos[table_name] = self._extract_single_table_info(
                table_name, database_name, sample_data, db_manager
            )
        return table_infos

    def _extract_single_table_info(
        self,
        table_name: str,
        database_name: str,
        sample_data: bool,
        db_manager: DatabaseManager
    ) -> Dict[str, Any]:
        """提取单个表的详细信息"""
        # 获取基础表信息
        columns = db_manager.get_table_columns(table_name)
        primary_keys = db_manager.get_primary_keys(table_name)
        foreign_keys = db_manager.get_foreign_keys(table_name)
        
        table_info = {
            "name": table_name,
            "columns": self._format_columns_info(columns),
            "primary_keys": primary_keys,
            "foreign_keys": self._format_foreign_keys_info(foreign_keys),
            "row_count": self._get_table_row_count(table_name, db_manager)
        }
        
        # 添加样本数据
        if sample_data:
            table_info["sample_data"] = self._get_sample_data(table_name, db_manager)
        
        return table_info

    def _format_columns_info(self, columns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """格式化列信息"""
        return [{
            "name": col.get("name", ""),
            "type": col.get("type", ""),
            "nullable": col.get("nullable", True),
            "default": col.get("default"),
            "comment": col.get("comment", "")
        } for col in columns]

    def _format_foreign_keys_info(self, foreign_keys: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """格式化外键信息"""
        return [{
            "constrained_columns": fk.get("constrained_columns", []),
            "referred_table": fk.get("referred_table", ""),
            "referred_columns": fk.get("referred_columns", [])
        } for fk in foreign_keys]

    def _get_table_row_count(self, table_name: str, db_manager: DatabaseManager) -> int:
        """获取表行数"""
        return db_manager.get_table_row_count(table_name)

    def _get_sample_data(self, table_name: str, db_manager: DatabaseManager, limit: int = 3) -> List[Dict[str, Any]]:
        """获取样本数据"""
        return db_manager.get_sample_data(table_name, limit)

    def _build_schema_result(self, database_name: str, table_infos: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """构建最终结果"""
        total_columns = sum(
            len(info.get("columns", [])) for info in table_infos.values()
        )
        
        return {
            "database_name": database_name,
            "tables": table_infos,
            "table_count": len(table_infos),
            "total_columns": total_columns,
            "extraction_summary": f"提取了{len(table_infos)}个表，共{total_columns}个字段"
        }

    async def _arun(
        self,
        database_name: str,
        include_views: bool = False,
        sample_data: bool = True,
        tables: Optional[List[str]] = None,
        **kwargs
    ) -> str:
        """异步执行（当前实现为同步）"""
        return self._run(database_name, include_views, sample_data, tables, **kwargs)