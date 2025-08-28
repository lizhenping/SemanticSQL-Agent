"""
查询执行器 - 安全的SQL查询执行
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from .connection_manager import DatabaseManager


class QueryExecutor:
    """查询执行器"""
    
    def __init__(self, database_manager: DatabaseManager):
        self.db_manager = database_manager
        self.logger = logging.getLogger("database.executor")
    
    def is_safe_query(self, sql: str) -> bool:
        """检查SQL查询是否安全"""
        sql_upper = sql.strip().upper()
        
        # 只允许SELECT查询
        if not sql_upper.startswith("SELECT"):
            return False
        
        # 检查危险关键词
        dangerous_keywords = [
            "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE", "TRUNCATE",
            "GRANT", "REVOKE", "EXEC", "EXECUTE", "UNION", "UNION ALL"
        ]
        
        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                return False
        
        return True
    
    async def execute_safe_query(
        self,
        sql: str,
        max_rows: int = 1000,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """执行安全的查询"""
        try:
            # 安全检查
            if not self.is_safe_query(sql):
                return {
                    "success": False,
                    "error": "不安全的SQL查询",
                    "sql": sql
                }
            
            # 执行查询
            result = await self.db_manager.execute_query(sql, max_rows)
            return result
            
        except Exception as e:
            self.logger.error(f"执行查询失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "sql": sql
            }
    
    async def validate_and_execute(
        self,
        sql: str,
        max_rows: int = 1000
    ) -> Dict[str, Any]:
        """验证并执行查询"""
        try:
            # 验证SQL语法
            validation_result = await self.db_manager.validate_sql(sql)
            if not validation_result["success"] or not validation_result["valid"]:
                return {
                    "success": False,
                    "error": validation_result.get("error", "SQL语法错误"),
                    "sql": sql
                }
            
            # 执行查询
            execution_result = await self.execute_safe_query(sql, max_rows)
            return execution_result
            
        except Exception as e:
            self.logger.error(f"验证和执行查询失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "sql": sql
            }
    
    async def execute_batch_queries(
        self,
        queries: List[str],
        max_rows_per_query: int = 100
    ) -> List[Dict[str, Any]]:
        """批量执行查询"""
        results = []
        
        for sql in queries:
            result = await self.execute_safe_query(sql, max_rows_per_query)
            results.append(result)
        
        return results
    
    async def get_query_stats(self, sql: str) -> Dict[str, Any]:
        """获取查询统计信息"""
        try:
            # 使用EXPLAIN获取查询计划
            explain_result = await self.db_manager.validate_sql(sql)
            if not explain_result["success"]:
                return explain_result
            
            # 执行查询获取统计信息
            start_time = datetime.now()
            result = await self.execute_safe_query(sql, max_rows=1)
            end_time = datetime.now()
            
            stats = {
                "sql": sql,
                "execution_time": (end_time - start_time).total_seconds(),
                "execution_plan": explain_result.get("execution_plan", []),
                "is_valid": True
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"获取查询统计信息失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "sql": sql
            }
    
    def sanitize_sql(self, sql: str) -> str:
        """清理SQL查询"""
        # 移除多余的空格和换行
        sql = ' '.join(sql.split())
        
        # 确保SQL以SELECT开头
        sql = sql.strip()
        if not sql.upper().startswith("SELECT"):
            sql = f"SELECT {sql}"
        
        return sql
    
    async def get_sample_data(self, table_name: str, limit: int = 10) -> Dict[str, Any]:
        """获取表样本数据"""
        try:
            sql = f"SELECT * FROM {table_name} LIMIT {limit}"
            result = await self.execute_safe_query(sql, limit)
            return result
            
        except Exception as e:
            self.logger.error(f"获取样本数据失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "table": table_name
            }