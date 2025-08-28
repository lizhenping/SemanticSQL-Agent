"""SQL 验证工具"""

from tools.base import BaseSemanticSQLTool
from typing import Dict, Any, List
from models.generation_models import (
    SQLValidationInput,
    SQLValidationOutput,
    ValidationIssue
)
from models.schemas import SQLValidationResult
import logging
import re

logger = logging.getLogger(__name__)


class SQLValidationTool(BaseSemanticSQLTool):
    """SQL 验证工具"""
    
    name = "validate_sql"
    description = (
        "验证 SQL 语句的语法正确性和安全性。"
        "会检查语法错误、表和列的存在性、以及潜在的性能问题。"
    )
    args_schema = SQLValidationInput
    
    def execute(
        self,
        sql: str,
        check_performance: bool = False
    ) -> Dict[str, Any]:
        """验证 SQL"""
        # 清理 SQL
        sql = self._clean_sql(sql)
        
        validation_result = SQLValidationResult(
            is_valid=True,
            syntax_check=True,
            sql=sql
        )
        
        # 1. 安全检查
        safety_check = self._check_safety(sql)
        if not safety_check["safe"]:
            validation_result.is_valid = False
            validation_result.error = safety_check["error"]
            return validation_result.dict()
        
        # 2. 语法检查
        syntax_check = self._check_syntax(sql)
        if not syntax_check["valid"]:
            validation_result.is_valid = False
            validation_result.syntax_check = False
            validation_result.error = syntax_check["error"]
            validation_result.suggestions.extend(syntax_check.get("suggestions", []))
            return validation_result.dict()
        
        # 3. 表和列存在性检查
        existence_check = self._check_existence(sql)
        if not existence_check["valid"]:
            validation_result.is_valid = False
            validation_result.error = existence_check["error"]
            validation_result.suggestions.extend(existence_check.get("suggestions", []))
        
        # 4. 性能检查（可选）
        if check_performance and validation_result.is_valid:
            perf_suggestions = self._check_performance(sql)
            validation_result.suggestions.extend(perf_suggestions)
        
        # 格式化结果
        if validation_result.is_valid:
            return {
                **validation_result.dict(),
                "message": "SQL 验证通过，语法正确且安全"
            }
        else:
            return {
                **validation_result.dict(),
                "message": f"SQL 验证失败: {validation_result.error}"
            }
    
    def _clean_sql(self, sql: str) -> str:
        """清理 SQL 语句"""
        # 移除 markdown 代码块标记
        sql = re.sub(r'```sql\s*\n?', '', sql)
        sql = re.sub(r'```\s*\n?', '', sql)
        
        # 清理空白字符
        sql = sql.strip()
        
        # 确保以分号结尾
        if not sql.endswith(';'):
            sql += ';'
        
        return sql
    
    def _check_safety(self, sql: str) -> Dict[str, Any]:
        """安全性检查"""
        # 危险操作关键词
        dangerous_keywords = [
            'DROP', 'DELETE', 'TRUNCATE', 'UPDATE', 'INSERT',
            'ALTER', 'CREATE', 'GRANT', 'REVOKE', 'EXEC', 'EXECUTE'
        ]
        
        sql_upper = sql.upper()
        
        for keyword in dangerous_keywords:
            # 检查是否是完整的关键词（避免误判）
            pattern = rf'\b{keyword}\b'
            if re.search(pattern, sql_upper):
                return {
                    "safe": False,
                    "error": f"检测到危险操作: {keyword}。只允许 SELECT 查询。"
                }
        
        return {"safe": True}
    
    def _check_syntax(self, sql: str) -> Dict[str, Any]:
        """语法检查"""
        try:
            # 使用 EXPLAIN 检查语法
            explain_sql = f"EXPLAIN {sql}"
            self.db.run(explain_sql)
            
            return {"valid": True}
            
        except Exception as e:
            error_str = str(e)
            logger.error(f"SQL 语法检查失败: {error_str}")
            
            # 分析错误并提供建议
            suggestions = self._analyze_syntax_error(error_str, sql)
            
            return {
                "valid": False,
                "error": error_str,
                "suggestions": suggestions
            }
    
    def _analyze_syntax_error(self, error: str, sql: str) -> List[str]:
        """分析语法错误并提供建议"""
        suggestions = []
        error_lower = error.lower()
        
        if "unknown column" in error_lower:
            suggestions.append("列名不存在，请使用 extract_database_schema 工具查看正确的列名")
            
            # 尝试提取错误的列名
            import re
            match = re.search(r"unknown column '(\w+)'", error_lower)
            if match:
                col_name = match.group(1)
                suggestions.append(f"检查列名 '{col_name}' 是否拼写正确")
        
        elif "table" in error_lower and "doesn't exist" in error_lower:
            suggestions.append("表不存在，请使用 sql_db_list_tables 工具查看可用的表")
            
            # 尝试提取错误的表名
            match = re.search(r"table '[\w\.]+\.(\w+)'", error_lower)
            if match:
                table_name = match.group(1)
                suggestions.append(f"检查表名 '{table_name}' 是否正确")
        
        elif "syntax error" in error_lower:
            suggestions.append("SQL 语法错误，请检查：")
            suggestions.append("- 关键字拼写是否正确")
            suggestions.append("- 是否缺少逗号或括号")
            suggestions.append("- 引号是否匹配")
            
            # 检查常见语法问题
            if not re.search(r'\bFROM\b', sql, re.IGNORECASE):
                suggestions.append("- 缺少 FROM 子句")
            
            if re.search(r'\bGROUP\s+BY\b', sql, re.IGNORECASE) and not re.search(r'\b(COUNT|SUM|AVG|MAX|MIN)\b', sql, re.IGNORECASE):
                suggestions.append("- 使用 GROUP BY 时需要聚合函数")
        
        elif "ambiguous" in error_lower:
            suggestions.append("列名歧义，请使用表名限定列名，如: table.column")
        
        elif "subquery returns more than 1 row" in error_lower:
            suggestions.append("子查询返回多行，请使用 IN 或 EXISTS，或添加 LIMIT 1")
        
        return suggestions
    
    def _check_existence(self, sql: str) -> Dict[str, Any]:
        """检查表和列的存在性"""
        # 获取可用的表
        available_tables = set(self.db.get_usable_table_names())
        
        # 从 SQL 中提取表名
        tables_in_sql = self._extract_table_names(sql)
        
        # 检查表是否存在
        missing_tables = tables_in_sql - available_tables
        if missing_tables:
            return {
                "valid": False,
                "error": f"以下表不存在: {', '.join(missing_tables)}",
                "suggestions": [
                    "使用 sql_db_list_tables 查看所有可用的表",
                    f"可用的表包括: {', '.join(list(available_tables)[:5])}"
                ]
            }
        
        return {"valid": True}
    
    def _extract_table_names(self, sql: str) -> set:
        """从 SQL 中提取表名"""
        tables = set()
        
        # 移除字符串内容（避免误匹配）
        sql_no_strings = re.sub(r"'[^']*'", "", sql)
        sql_no_strings = re.sub(r'"[^"]*"', "", sql_no_strings)
        
        # FROM 子句
        from_pattern = r'\bFROM\s+`?(\w+)`?(?:\s+AS\s+\w+)?'
        tables.update(re.findall(from_pattern, sql_no_strings, re.IGNORECASE))
        
        # JOIN 子句
        join_pattern = r'\bJOIN\s+`?(\w+)`?(?:\s+AS\s+\w+)?'
        tables.update(re.findall(join_pattern, sql_no_strings, re.IGNORECASE))
        
        # INTO 子句（INSERT）
        into_pattern = r'\bINTO\s+`?(\w+)`?'
        tables.update(re.findall(into_pattern, sql_no_strings, re.IGNORECASE))
        
        # UPDATE 子句
        update_pattern = r'\bUPDATE\s+`?(\w+)`?'
        tables.update(re.findall(update_pattern, sql_no_strings, re.IGNORECASE))
        
        return tables
    
    def _check_performance(self, sql: str) -> List[str]:
        """检查潜在的性能问题"""
        suggestions = []
        sql_upper = sql.upper()
        
        # 检查 SELECT *
        if re.search(r'\bSELECT\s+\*', sql_upper):
            suggestions.append("避免使用 SELECT *，只选择需要的列可以提高性能")
        
        # 检查缺少 LIMIT
        if 'LIMIT' not in sql_upper and 'SELECT' in sql_upper:
            suggestions.append("考虑添加 LIMIT 子句限制返回行数")
        
        # 检查 LIKE 通配符在开头
        if re.search(r"LIKE\s+'%", sql_upper):
            suggestions.append("LIKE '%...' 无法使用索引，考虑其他查询方式")
        
        # 检查函数在 WHERE 子句中
        if re.search(r'WHERE.*\b(UPPER|LOWER|DATE|YEAR|MONTH)\s*\(', sql_upper):
            suggestions.append("WHERE 子句中使用函数可能导致索引失效")
        
        # 检查 OR 条件
        if re.search(r'WHERE.*\bOR\b', sql_upper):
            suggestions.append("OR 条件可能影响索引使用，考虑改用 IN 或 UNION")
        
        # 检查子查询
        if sql_upper.count('SELECT') > 1:
            suggestions.append("包含子查询，考虑是否可以改用 JOIN")
        
        return suggestions