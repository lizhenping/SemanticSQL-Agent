"""数据库结构提取工具"""

from tools.base import BaseSemanticSQLTool
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class SchemaExtractionInput(BaseModel):
    """输入模式"""
    tables: Optional[List[str]] = Field(
        default=None,
        description="要提取的表名列表，为空则提取所有表"
    )
    include_samples: bool = Field(
        default=True,
        description="是否包含样本数据"
    )
    sample_size: int = Field(
        default=3,
        description="每个表的样本数据行数"
    )


class SchemaExtractionTool(BaseSemanticSQLTool):
    """数据库结构提取工具"""
    
    name = "extract_database_schema"
    description = (
        "提取数据库的表结构信息，包括表、列、数据类型、注释等。"
        "这是分析的第一步，帮助理解数据库结构。"
    )
    args_schema = SchemaExtractionInput
    
    def execute(
        self, 
        tables: Optional[List[str]] = None,
        include_samples: bool = True,
        sample_size: int = 3
    ) -> Dict[str, Any]:
        """执行 schema 提取"""
        # 获取表列表
        if not tables:
            tables = self.db.get_usable_table_names()
            logger.info(f"未指定表，获取所有表: {len(tables)} 个")
        
        # 限制表数量，避免输出过长
        if len(tables) > 10:
            logger.warning(f"表数量过多 ({len(tables)})，只提取前 10 个")
            tables = tables[:10]
        
        result = {
            "database": self.db._engine.url.database,
            "tables_count": len(tables),
            "tables": {}
        }
        
        for table in tables:
            table_info = self._extract_table_info(table, include_samples, sample_size)
            result["tables"][table] = table_info
        
        return result
    
    def _extract_table_info(
        self, 
        table_name: str, 
        include_samples: bool,
        sample_size: int
    ) -> Dict[str, Any]:
        """提取单个表的信息"""
        table_info = {
            "name": table_name,
            "structure": None,
            "columns": [],
            "row_count": None,
            "sample_data": None
        }
        
        try:
            # 获取表结构 DDL
            table_info["structure"] = self.db.get_table_info_no_throw([table_name])
            
            # 解析列信息
            table_info["columns"] = self._parse_columns_from_ddl(table_info["structure"])
            
            # 获取行数
            try:
                count_result = self.db.run(f"SELECT COUNT(*) as cnt FROM `{table_name}`")
                # 解析结果
                if count_result and isinstance(count_result, str):
                    import re
                    match = re.search(r'\d+', count_result)
                    if match:
                        table_info["row_count"] = int(match.group())
            except Exception as e:
                logger.warning(f"获取表 {table_name} 行数失败: {e}")
            
            # 获取样本数据
            if include_samples and sample_size > 0:
                try:
                    sample_query = f"SELECT * FROM `{table_name}` LIMIT {sample_size}"
                    table_info["sample_data"] = self.db.run(sample_query)
                except Exception as e:
                    logger.warning(f"获取表 {table_name} 样本数据失败: {e}")
                    table_info["sample_data"] = f"获取失败: {str(e)}"
            
        except Exception as e:
            logger.error(f"提取表 {table_name} 信息失败: {e}")
            table_info["error"] = str(e)
        
        return table_info
    
    def _parse_columns_from_ddl(self, ddl: str) -> List[Dict[str, str]]:
        """从 DDL 中解析列信息"""
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
                
                # 检查是否有 NOT NULL
                nullable = 'NOT NULL' not in line.upper()
                
                # 检查是否有注释
                comment = None
                if 'COMMENT' in line.upper():
                    import re
                    comment_match = re.search(r"COMMENT\s+'([^']+)'", line, re.IGNORECASE)
                    if comment_match:
                        comment = comment_match.group(1)
                
                columns.append({
                    "name": col_name,
                    "type": col_type,
                    "nullable": nullable,
                    "comment": comment
                })
        
        return columns