"""
SQL执行工具 - 执行SQL并返回结果
基于 LangChain BaseTool
"""

from typing import Dict, Any, Type, List, Optional
from pydantic import BaseModel, Field
import json

from models.exceptions import ToolExecutionError, SQLExecutionError
from ..base_tool import BaseSemanticSQLTool


class SQLExecutionInput(BaseModel):
    """SQL执行输入"""
    sql: str = Field(description="要执行的SQL语句")
    limit: int = Field(default=100, description="结果限制")


class SQLExecutionTool(BaseSemanticSQLTool):
    """SQL执行工具"""
    
    name: str = "sql_execution"
    description: str = "执行SQL查询并返回结果。自动从记忆中获取数据库连接"
    args_schema: Type[BaseModel] = SQLExecutionInput
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    def _run(self, sql: str, limit: int = 100, **kwargs) -> str:
        """执行SQL"""
        try:
            # 从记忆中获取数据库管理器
            db_manager = self.get_from_memory("database_manager")
            if not db_manager:
                raise ToolExecutionError(
                    tool_name=self.name,
                    message="数据库管理器未初始化",
                    details="需要先在Agent记忆中设置database_manager"
                )
            
            # 添加LIMIT如果没有
            sql_lower = sql.lower()
            if 'limit' not in sql_lower and sql_lower.startswith('select'):
                sql = sql.rstrip(';') + f' LIMIT {limit};'
            
            # 执行查询
            result = db_manager.execute_query(sql)
            
            # 构建结果
            execution_result = {
                "success": True,
                "data": result,
                "row_count": len(result) if result else 0,
                "truncated": len(result) == limit if result else False
            }
            
            # 保存执行结果到记忆
            self.save_to_memory("execution_result", execution_result)
            
            return json.dumps(execution_result, ensure_ascii=False)
            
        except Exception as e:
            self.logger.error(f"SQL执行失败: {e}")
            error_result = {
                "success": False,
                "error": str(e),
                "data": [],
                "row_count": 0
            }
            
            # 保存错误结果到记忆
            self.save_to_memory("execution_result", error_result)
            
            return json.dumps(error_result, ensure_ascii=False)
    
