"""SQL 执行工具"""

from tools.base import BaseSemanticSQLTool
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from models.schemas import QueryExecutionResult
import logging
import time
import re

logger = logging.getLogger(__name__)


class SQLExecutionInput(BaseModel):
    """输入模式"""
    sql: str = Field(description="要执行的 SQL 语句")
    limit: int = Field(
        default=10,
        description="返回结果的最大行数"
    )
    format_output: bool = Field(
        default=True,
        description="是否格式化输出结果"
    )


class SQLExecutionTool(BaseSemanticSQLTool):
    """SQL 执行工具"""
    
    name = "execute_sql"
    description = (
        "执行 SQL 查询并返回结果。"
        "会自动限制返回行数，并格式化输出结果。"
    )
    args_schema = SQLExecutionInput
    
    def execute(
        self,
        sql: str,
        limit: int = 10,
        format_output: bool = True
    ) -> Dict[str, Any]:
        """执行 SQL"""
        # 清理 SQL
        sql = self._clean_sql(sql)
        
        # 添加 LIMIT 限制
        sql_with_limit = self._add_limit(sql, limit)
        
        # 记录开始时间
        start_time = time.time()
        
        try:
            # 执行查询
            result_str = self.db.run(sql_with_limit)
            
            # 计算执行时间
            execution_time = time.time() - start_time
            
            # 解析结果
            rows = self._parse_result(result_str)
            
            # 创建执行结果对象
            execution_result = QueryExecutionResult(
                success=True,
                sql=sql_with_limit,
                rows=rows,
                row_count=len(rows),
                execution_time=execution_time
            )
            
            # 格式化输出
            if format_output:
                return self._format_execution_result(execution_result)
            else:
                return execution_result.dict()
            
        except Exception as e:
            logger.error(f"SQL 执行失败: {str(e)}")
            
            execution_result = QueryExecutionResult(
                success=False,
                sql=sql_with_limit,
                error=str(e),
                execution_time=time.time() - start_time
            )
            
            return self._format_execution_error(execution_result)
    
    def _clean_sql(self, sql: str) -> str:
        """清理 SQL 语句"""
        # 移除 markdown 代码块标记
        sql = re.sub(r'```sql\s*\n?', '', sql)
        sql = re.sub(r'```\s*\n?', '', sql)
        
        # 清理空白字符
        sql = sql.strip()
        
        # 移除末尾的分号（如果有）
        sql = sql.rstrip(';')
        
        return sql
    
    def _add_limit(self, sql: str, limit: int) -> str:
        """添加 LIMIT 限制"""
        sql_upper = sql.upper()
        
        # 检查是否已有 LIMIT
        if 'LIMIT' in sql_upper:
            # 检查现有 LIMIT 值
            limit_match = re.search(r'LIMIT\s+(\d+)', sql_upper)
            if limit_match:
                existing_limit = int(limit_match.group(1))
                if existing_limit > limit:
                    # 替换为更小的限制
                    sql = re.sub(r'LIMIT\s+\d+', f'LIMIT {limit}', sql, flags=re.IGNORECASE)
            return sql
        
        # 添加 LIMIT
        # 检查是否有 ORDER BY，如果有，加在其后
        if 'ORDER BY' in sql_upper:
            # 找到 ORDER BY 子句的结束位置
            # 简单处理：假设 ORDER BY 是最后的子句
            sql = f"{sql} LIMIT {limit}"
        else:
            sql = f"{sql} LIMIT {limit}"
        
        return sql
    
    def _parse_result(self, result_str: str) -> List[Dict[str, Any]]:
        """解析查询结果"""
        if not result_str:
            return []
        
        try:
            # 尝试使用 ast.literal_eval 解析
            import ast
            result = ast.literal_eval(result_str)
            
            if isinstance(result, list):
                # 如果是元组列表，需要转换为字典列表
                if result and isinstance(result[0], tuple):
                    # 需要获取列名
                    # 这是一个简化处理，实际应该从查询中提取列名
                    return [
                        {f"col_{i}": value for i, value in enumerate(row)}
                        for row in result
                    ]
                return result
            else:
                return [result]
                
        except (ValueError, SyntaxError):
            # 如果解析失败，尝试其他方法
            logger.warning("无法使用 literal_eval 解析结果，尝试其他方法")
            
            # 尝试简单的文本解析
            lines = result_str.strip().split('\n')
            if lines:
                # 假设第一行是列名
                if len(lines) > 1 and '|' in lines[0]:
                    # 表格格式
                    return self._parse_table_format(lines)
                else:
                    # 简单的行格式
                    return [{"result": line} for line in lines if line]
            
            return []
    
    def _parse_table_format(self, lines: List[str]) -> List[Dict[str, Any]]:
        """解析表格格式的结果"""
        rows = []
        
        # 查找列名行
        header_line = None
        for i, line in enumerate(lines):
            if '|' in line and not line.strip().startswith('-'):
                header_line = i
                break
        
        if header_line is None:
            return []
        
        # 解析列名
        columns = [col.strip() for col in lines[header_line].split('|') if col.strip()]
        
        # 解析数据行
        for line in lines[header_line + 1:]:
            if line.strip() and not line.strip().startswith('-'):
                values = [val.strip() for val in line.split('|') if val.strip()]
                if len(values) == len(columns):
                    row = dict(zip(columns, values))
                    rows.append(row)
        
        return rows
    
    def _format_execution_result(self, result: QueryExecutionResult) -> Dict[str, Any]:
        """格式化执行结果"""
        output = {
            "success": True,
            "sql": result.sql,
            "execution_time": f"{result.execution_time:.3f} 秒",
            "row_count": result.row_count,
            "message": f"查询成功，返回 {result.row_count} 行数据"
        }
        
        # 格式化数据预览
        if result.rows:
            if result.row_count <= 5:
                # 显示所有行
                output["data"] = self._format_rows(result.rows)
            else:
                # 显示前几行
                output["data_preview"] = self._format_rows(result.rows[:3])
                output["message"] += f"（显示前 3 行）"
        else:
            output["data"] = "查询无结果"
        
        return output
    
    def _format_rows(self, rows: List[Dict[str, Any]]) -> str:
        """格式化行数据为表格"""
        if not rows:
            return "无数据"
        
        # 获取列名
        columns = list(rows[0].keys())
        
        # 计算列宽
        col_widths = {}
        for col in columns:
            # 列名长度
            col_widths[col] = len(str(col))
            # 数据最大长度
            for row in rows:
                val_len = len(str(row.get(col, '')))
                col_widths[col] = max(col_widths[col], val_len)
        
        # 限制列宽
        max_width = 30
        for col in col_widths:
            col_widths[col] = min(col_widths[col], max_width)
        
        # 构建表格
        lines = []
        
        # 表头
        header = " | ".join(
            str(col).ljust(col_widths[col])[:col_widths[col]]
            for col in columns
        )
        lines.append(header)
        
        # 分隔线
        separator = "-+-".join("-" * col_widths[col] for col in columns)
        lines.append(separator)
        
        # 数据行
        for row in rows:
            row_str = " | ".join(
                str(row.get(col, '')).ljust(col_widths[col])[:col_widths[col]]
                for col in columns
            )
            lines.append(row_str)
        
        return "\n".join(lines)
    
    def _format_execution_error(self, result: QueryExecutionResult) -> Dict[str, Any]:
        """格式化执行错误"""
        error_msg = result.error or "未知错误"
        
        # 提供错误分析
        suggestions = []
        error_lower = error_msg.lower()
        
        if "syntax" in error_lower:
            suggestions.append("SQL 语法错误，请使用 validate_sql 工具检查")
        elif "table" in error_lower and "exist" in error_lower:
            suggestions.append("表不存在，请使用 sql_db_list_tables 查看可用表")
        elif "column" in error_lower:
            suggestions.append("列名错误，请使用 extract_database_schema 查看表结构")
        elif "permission" in error_lower or "denied" in error_lower:
            suggestions.append("权限不足，请确认数据库用户权限")
        
        output = {
            "success": False,
            "sql": result.sql,
            "error": error_msg,
            "execution_time": f"{result.execution_time:.3f} 秒",
            "message": f"查询执行失败: {error_msg}"
        }
        
        if suggestions:
            output["suggestions"] = suggestions
        
        return output