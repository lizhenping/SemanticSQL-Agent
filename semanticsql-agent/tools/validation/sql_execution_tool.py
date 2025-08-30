"""
SQL执行工具 - 执行SQL并验证结果
"""

import time
from typing import Dict, Any, List, Optional
from datetime import datetime
import sqlalchemy
from sqlalchemy import create_engine, text

from tools.base_tool import BaseTool, ToolParameter
from core.exceptions import SQLExecutionError
from core.constants import SQL_EXECUTION_TIMEOUT, MAX_RESULT_ROWS
from config.trae_config import DatabaseConfig


class SQLExecutionTool(BaseTool):
    """SQL执行测试工具"""
    
    def __init__(self, config: Any):
        super().__init__(config)
        self.db_config = config.database if hasattr(config, 'database') else DatabaseConfig()
        self.engine = None
        self._init_engine()
    
    def _init_engine(self):
        """初始化数据库引擎"""
        try:
            connection_string = self.db_config.to_connection_string()
            self.engine = create_engine(
                connection_string,
                pool_size=self.db_config.pool_size,
                max_overflow=self.db_config.max_overflow,
                pool_timeout=self.db_config.pool_timeout,
                pool_pre_ping=self.db_config.pool_pre_ping,
                echo=self.db_config.echo
            )
        except Exception as e:
            self.logger.error(f"Failed to create database engine: {e}")
    
    @property
    def name(self) -> str:
        return "execute_sql"
    
    @property
    def description(self) -> str:
        return "执行SQL查询并返回结果"
    
    @property
    def category(self) -> str:
        return "validation"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="sql",
                type="string",
                description="要执行的SQL查询",
                required=True
            ),
            ToolParameter(
                name="timeout",
                type="integer",
                description="执行超时时间（秒）",
                required=False,
                default=SQL_EXECUTION_TIMEOUT
            ),
            ToolParameter(
                name="max_rows",
                type="integer",
                description="最大返回行数",
                required=False,
                default=MAX_RESULT_ROWS
            ),
            ToolParameter(
                name="dry_run",
                type="boolean",
                description="是否只进行模拟执行",
                required=False,
                default=False
            ),
            ToolParameter(
                name="explain",
                type="boolean",
                description="是否返回执行计划",
                required=False,
                default=False
            )
        ]
    
    def _execute(self, sql: str, timeout: int = SQL_EXECUTION_TIMEOUT,
                 max_rows: int = MAX_RESULT_ROWS, dry_run: bool = False,
                 explain: bool = False) -> Dict[str, Any]:
        """
        执行SQL查询
        
        Returns:
            执行结果
        """
        if not self.engine:
            return {
                "success": False,
                "error": "Database engine not initialized",
                "rows": [],
                "row_count": 0
            }
        
        # 安全检查
        if self._is_dangerous_query(sql) and not dry_run:
            return {
                "success": False,
                "error": "Dangerous query detected. Use dry_run=True to test.",
                "query_type": self._get_query_type(sql)
            }
        
        # 干运行模式
        if dry_run:
            return self._dry_run(sql)
        
        # 执行计划模式
        if explain:
            return self._get_execution_plan(sql)
        
        # 实际执行
        return self._execute_query(sql, timeout, max_rows)
    
    def _execute_query(self, sql: str, timeout: int, max_rows: int) -> Dict[str, Any]:
        """实际执行查询"""
        start_time = time.time()
        result = {
            "success": False,
            "rows": [],
            "row_count": 0,
            "column_names": [],
            "execution_time": 0,
            "error": None
        }
        
        try:
            with self.engine.connect() as connection:
                # 设置超时
                if self.db_config.type == "mysql":
                    connection.execute(text(f"SET SESSION max_execution_time = {timeout * 1000}"))
                elif self.db_config.type == "postgresql":
                    connection.execute(text(f"SET statement_timeout = {timeout * 1000}"))
                
                # 执行查询
                query_result = connection.execute(text(sql))
                
                # 处理结果
                if query_result.returns_rows:
                    # SELECT查询
                    rows = []
                    for i, row in enumerate(query_result):
                        if i >= max_rows:
                            result["truncated"] = True
                            result["truncated_at"] = max_rows
                            break
                        rows.append(dict(row._mapping))
                    
                    result["rows"] = rows
                    result["row_count"] = len(rows)
                    
                    # 获取列名
                    if rows:
                        result["column_names"] = list(rows[0].keys())
                else:
                    # DML查询（INSERT/UPDATE/DELETE）
                    result["affected_rows"] = query_result.rowcount
                    result["row_count"] = 0
                
                result["success"] = True
                
        except sqlalchemy.exc.OperationalError as e:
            result["error"] = f"Operational error: {str(e)}"
            self.logger.error(f"SQL execution operational error: {e}")
            
        except sqlalchemy.exc.ProgrammingError as e:
            result["error"] = f"Programming error: {str(e)}"
            self.logger.error(f"SQL execution programming error: {e}")
            
        except Exception as e:
            result["error"] = f"Execution error: {str(e)}"
            self.logger.error(f"SQL execution error: {e}")
        
        finally:
            execution_time = time.time() - start_time
            result["execution_time"] = round(execution_time, 3)
            
            # 添加执行统计
            result["statistics"] = self._get_execution_statistics(
                sql, result, execution_time
            )
        
        return result
    
    def _dry_run(self, sql: str) -> Dict[str, Any]:
        """模拟执行（不实际运行）"""
        result = {
            "success": True,
            "dry_run": True,
            "query_type": self._get_query_type(sql),
            "estimated_impact": self._estimate_impact(sql),
            "warnings": []
        }
        
        # 分析查询
        query_type = result["query_type"]
        
        if query_type == "SELECT":
            result["message"] = "Query would be executed and return results"
        elif query_type == "INSERT":
            result["message"] = "Query would insert new records"
            result["warnings"].append("This will add new data to the database")
        elif query_type == "UPDATE":
            result["message"] = "Query would update existing records"
            result["warnings"].append("This will modify existing data")
        elif query_type == "DELETE":
            result["message"] = "Query would delete records"
            result["warnings"].append("This will permanently remove data")
        else:
            result["message"] = "Query would be executed"
        
        return result
    
    def _get_execution_plan(self, sql: str) -> Dict[str, Any]:
        """获取执行计划"""
        result = {
            "success": False,
            "execution_plan": None,
            "error": None
        }
        
        try:
            with self.engine.connect() as connection:
                # 根据数据库类型获取执行计划
                if self.db_config.type == "mysql":
                    explain_sql = f"EXPLAIN {sql}"
                elif self.db_config.type == "postgresql":
                    explain_sql = f"EXPLAIN ANALYZE {sql}"
                else:
                    explain_sql = f"EXPLAIN QUERY PLAN {sql}"
                
                plan_result = connection.execute(text(explain_sql))
                
                # 格式化执行计划
                plan_rows = []
                for row in plan_result:
                    plan_rows.append(dict(row._mapping))
                
                result["execution_plan"] = plan_rows
                result["success"] = True
                
                # 分析执行计划
                result["analysis"] = self._analyze_execution_plan(plan_rows)
                
        except Exception as e:
            result["error"] = f"Failed to get execution plan: {str(e)}"
            self.logger.error(f"Execution plan error: {e}")
        
        return result
    
    def _is_dangerous_query(self, sql: str) -> bool:
        """检查是否为危险查询"""
        sql_upper = sql.upper()
        
        # 危险关键字
        dangerous_keywords = [
            'DROP', 'TRUNCATE', 'ALTER', 
            'CREATE', 'RENAME', 'GRANT', 'REVOKE'
        ]
        
        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                return True
        
        # DELETE without WHERE
        if 'DELETE' in sql_upper and 'WHERE' not in sql_upper:
            return True
        
        # UPDATE without WHERE
        if 'UPDATE' in sql_upper and 'WHERE' not in sql_upper:
            return True
        
        return False
    
    def _get_query_type(self, sql: str) -> str:
        """获取查询类型"""
        sql_upper = sql.upper().strip()
        
        if sql_upper.startswith('SELECT'):
            return 'SELECT'
        elif sql_upper.startswith('INSERT'):
            return 'INSERT'
        elif sql_upper.startswith('UPDATE'):
            return 'UPDATE'
        elif sql_upper.startswith('DELETE'):
            return 'DELETE'
        elif sql_upper.startswith('CREATE'):
            return 'CREATE'
        elif sql_upper.startswith('DROP'):
            return 'DROP'
        elif sql_upper.startswith('ALTER'):
            return 'ALTER'
        else:
            return 'OTHER'
    
    def _estimate_impact(self, sql: str) -> Dict[str, Any]:
        """估算查询影响"""
        impact = {
            "level": "low",
            "description": ""
        }
        
        query_type = self._get_query_type(sql)
        
        if query_type == "SELECT":
            impact["level"] = "none"
            impact["description"] = "Read-only query, no data modification"
        elif query_type in ["INSERT", "UPDATE", "DELETE"]:
            # 检查是否有WHERE子句
            if 'WHERE' not in sql.upper():
                impact["level"] = "high"
                impact["description"] = f"{query_type} without WHERE clause affects all rows"
            else:
                impact["level"] = "medium"
                impact["description"] = f"{query_type} with WHERE clause affects specific rows"
        elif query_type in ["CREATE", "DROP", "ALTER"]:
            impact["level"] = "critical"
            impact["description"] = f"Schema modification: {query_type}"
        
        return impact
    
    def _get_execution_statistics(self, sql: str, result: Dict[str, Any],
                                 execution_time: float) -> Dict[str, Any]:
        """获取执行统计信息"""
        stats = {
            "execution_time_ms": round(execution_time * 1000, 2),
            "success": result["success"],
            "query_type": self._get_query_type(sql)
        }
        
        if result["success"]:
            if "rows" in result:
                stats["rows_returned"] = result["row_count"]
                stats["columns_count"] = len(result.get("column_names", []))
                
                # 计算数据大小（估算）
                if result["rows"]:
                    row_size = len(str(result["rows"][0]))
                    stats["estimated_size_bytes"] = row_size * result["row_count"]
            
            if "affected_rows" in result:
                stats["rows_affected"] = result["affected_rows"]
        
        # 性能评级
        if execution_time < 0.1:
            stats["performance_rating"] = "excellent"
        elif execution_time < 0.5:
            stats["performance_rating"] = "good"
        elif execution_time < 2:
            stats["performance_rating"] = "acceptable"
        else:
            stats["performance_rating"] = "slow"
        
        return stats
    
    def _analyze_execution_plan(self, plan_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析执行计划"""
        analysis = {
            "uses_index": False,
            "full_table_scan": False,
            "estimated_rows": 0,
            "warnings": []
        }
        
        for row in plan_rows:
            row_str = str(row).lower()
            
            # 检查索引使用
            if 'index' in row_str:
                analysis["uses_index"] = True
            
            # 检查全表扫描
            if 'full' in row_str or 'scan' in row_str:
                analysis["full_table_scan"] = True
                analysis["warnings"].append("Full table scan detected")
            
            # 提取行数估算
            for key, value in row.items():
                if 'rows' in str(key).lower() and isinstance(value, (int, float)):
                    analysis["estimated_rows"] += value
        
        # 性能建议
        if analysis["full_table_scan"] and not analysis["uses_index"]:
            analysis["warnings"].append("Consider adding indexes to improve performance")
        
        return analysis
    
    def __del__(self):
        """清理资源"""
        if self.engine:
            self.engine.dispose()