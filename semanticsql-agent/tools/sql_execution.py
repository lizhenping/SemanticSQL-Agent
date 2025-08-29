"""SQL 执行工具"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import logging
import time

from .base import BaseSemanticSQLTool, ToolExecResult

logger = logging.getLogger(__name__)


@dataclass
class QueryExecutionResult:
    """查询执行结果"""
    success: bool
    sql: str
    row_count: int = 0
    rows: List[Dict[str, Any]] = None
    execution_time: float = 0.0
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.rows is None:
            self.rows = []


class SQLExecutionTool(BaseSemanticSQLTool):
    """SQL 执行工具"""
    
    name = "execute_sql"
    description = (
        "执行 SQL 查询并返回结果。"
        "只支持 SELECT 查询，会限制返回的行数。"
    )
    
    def execute(
        self,
        sql: str,
        max_rows: int = 100,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """执行 SQL"""
        start_time = time.time()
        
        # 清理 SQL
        sql = self._clean_sql(sql)
        
        # 验证是否是查询语句
        if not self._is_select_query(sql):
            return {
                "success": False,
                "error": "只允许执行 SELECT 查询",
                "sql": sql
            }
        
        try:
            # 添加行数限制
            limited_sql = self._add_limit(sql, max_rows)
            
            # 执行查询
            logger.info(f"执行 SQL: {limited_sql[:100]}...")
            result = self.db.run(limited_sql)
            
            # 处理结果
            rows = self._process_result(result)
            execution_time = time.time() - start_time
            
            # 构建返回结果
            exec_result = {
                "success": True,
                "sql": sql,
                "row_count": len(rows),
                "rows": rows[:max_rows],  # 确保不超过限制
                "execution_time": execution_time
            }
            
            # 如果结果被截断，添加提示
            if len(rows) >= max_rows:
                exec_result["note"] = f"结果已限制为前 {max_rows} 行"
            
            logger.info(f"查询成功，返回 {len(rows)} 行，耗时 {execution_time:.2f}秒")
            
            return exec_result
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)
            logger.error(f"SQL 执行失败: {error_msg}")
            
            return {
                "success": False,
                "sql": sql,
                "error": error_msg,
                "execution_time": execution_time
            }
    
    def _clean_sql(self, sql: str) -> str:
        """清理 SQL 语句"""
        import re
        
        # 移除前后空白
        sql = sql.strip()
        
        # 移除可能的 markdown 代码块标记
        sql = re.sub(r'^```sql\s*', '', sql)
        sql = re.sub(r'\s*```$', '', sql)
        
        # 移除末尾的分号（某些数据库驱动不支持）
        sql = sql.rstrip(';')
        
        return sql
    
    def _is_select_query(self, sql: str) -> bool:
        """检查是否是 SELECT 查询"""
        sql_upper = sql.upper().strip()
        
        # 允许的查询类型
        allowed_starts = ['SELECT', 'WITH', 'SHOW', 'DESCRIBE', 'DESC', 'EXPLAIN']
        
        return any(sql_upper.startswith(start) for start in allowed_starts)
    
    def _add_limit(self, sql: str, max_rows: int) -> str:
        """为 SQL 添加 LIMIT 子句"""
        import re
        
        sql_upper = sql.upper()
        
        # 如果已经有 LIMIT，不再添加
        if 'LIMIT' in sql_upper:
            return sql
        
        # 对于某些特殊查询，不添加 LIMIT
        if any(keyword in sql_upper for keyword in ['SHOW', 'DESCRIBE', 'DESC', 'EXPLAIN']):
            return sql
        
        # 添加 LIMIT
        # 注意：不同数据库的语法可能不同
        # MySQL, PostgreSQL, SQLite: LIMIT n
        # SQL Server: TOP n
        # Oracle: ROWNUM <= n
        
        # 这里假设使用标准的 LIMIT 语法
        return f"{sql} LIMIT {max_rows}"
    
    def _process_result(self, result: Any) -> List[Dict[str, Any]]:
        """处理查询结果，转换为统一格式"""
        rows = []
        
        if result is None:
            return rows
        
        # 处理不同类型的返回值
        if isinstance(result, str):
            # 字符串结果，尝试解析
            try:
                import ast
                parsed = ast.literal_eval(result)
                if isinstance(parsed, list):
                    result = parsed
                else:
                    # 单个值，包装为列表
                    result = [parsed]
            except:
                # 无法解析，作为单行结果
                result = [{"result": result}]
        
        # 确保结果是列表
        if not isinstance(result, list):
            result = [result]
        
        # 转换每一行为字典
        for row in result:
            if isinstance(row, dict):
                rows.append(row)
            elif isinstance(row, (list, tuple)):
                # 如果是列表或元组，需要列名
                # 这里使用通用列名
                row_dict = {f"column_{i}": val for i, val in enumerate(row)}
                rows.append(row_dict)
            else:
                # 其他类型，作为单列
                rows.append({"value": row})
        
        return rows
    
    def format_result_table(self, exec_result: Dict[str, Any]) -> str:
        """格式化结果为表格形式（辅助方法）"""
        if not exec_result.get("success") or not exec_result.get("rows"):
            return ""
        
        rows = exec_result["rows"]
        if not rows:
            return "查询返回空结果"
        
        # 获取列名
        columns = list(rows[0].keys())
        
        # 计算列宽
        col_widths = {}
        for col in columns:
            # 列名的宽度
            col_widths[col] = len(str(col))
            # 数据的最大宽度
            for row in rows[:10]:  # 只检查前10行
                val_len = len(str(row.get(col, "")))
                col_widths[col] = max(col_widths[col], val_len)
            # 限制最大宽度
            col_widths[col] = min(col_widths[col], 50)
        
        # 构建表格
        lines = []
        
        # 表头
        header_parts = []
        for col in columns:
            header_parts.append(str(col).ljust(col_widths[col]))
        lines.append(" | ".join(header_parts))
        
        # 分隔线
        sep_parts = []
        for col in columns:
            sep_parts.append("-" * col_widths[col])
        lines.append("-|-".join(sep_parts))
        
        # 数据行
        for row in rows[:10]:  # 最多显示10行
            row_parts = []
            for col in columns:
                val = str(row.get(col, ""))
                if len(val) > col_widths[col]:
                    val = val[:col_widths[col]-3] + "..."
                row_parts.append(val.ljust(col_widths[col]))
            lines.append(" | ".join(row_parts))
        
        if len(rows) > 10:
            lines.append(f"... 还有 {len(rows) - 10} 行")
        
        return "\n".join(lines)