"""
SQL执行工具 - 执行SQL并返回结果
基于 LangChain BaseTool
"""

from typing import Dict, Any, Type, List
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from models.exceptions import ToolExecutionError, SQLExecutionError
from utils.database import DatabaseManager


class SQLExecutionInput(BaseModel):
    """SQL执行输入"""
    sql: str = Field(description="要执行的SQL语句")
    limit: int = Field(default=100, description="结果限制")


class SQLExecutionTool(BaseTool):
    """SQL执行工具"""
    
    name: str = "sql_execution"
    description: str = "执行SQL查询并返回结果"
    args_schema: Type[BaseModel] = SQLExecutionInput
    
    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        object.__setattr__(self, 'db_manager', db_manager)
    
    def _run(self, sql: str, limit: int = 100) -> Dict[str, Any]:
        """执行SQL"""
        try:
            # 添加LIMIT如果没有
            sql_lower = sql.lower()
            if 'limit' not in sql_lower and sql_lower.startswith('select'):
                sql = sql.rstrip(';') + f' LIMIT {limit};'
            
            # 执行查询
            result = self.db_manager.execute_query(sql)
            
            # 返回结果
            return {
                "success": True,
                "data": result,
                "row_count": len(result) if result else 0,
                "truncated": len(result) == limit if result else False
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "data": [],
                "row_count": 0
            }
    
    async def _arun(self, sql: str, limit: int = 100) -> Dict[str, Any]:
        """异步执行（当前实现为同步）"""
        return self._run(sql, limit)