"""SQL 验证工具"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import logging
import re

from .base import BaseSemanticSQLTool, ToolExecResult

logger = logging.getLogger(__name__)


@dataclass
class ValidationIssue:
    """验证问题"""
    type: str  # syntax, safety, performance, semantic
    severity: str  # error, warning, info
    message: str
    line: Optional[int] = None
    column: Optional[int] = None


class SQLValidationTool(BaseSemanticSQLTool):
    """SQL 验证工具"""
    
    name = "validate_sql"
    description = (
        "验证 SQL 语句的语法正确性和安全性。"
        "会检查语法错误、表和列的存在性、以及潜在的性能问题。"
    )
    
    def execute(
        self,
        sql: str,
        check_performance: bool = False
    ) -> Dict[str, Any]:
        """验证 SQL"""
        # 清理 SQL
        sql = self._clean_sql(sql)
        
        issues = []
        is_valid = True
        
        # 1. 安全检查
        safety_issues = self._check_safety(sql)
        if safety_issues:
            issues.extend(safety_issues)
            # 如果有严重的安全问题，标记为无效
            if any(issue.severity == "error" for issue in safety_issues):
                is_valid = False
        
        # 2. 语法检查
        syntax_issues = self._check_syntax(sql)
        if syntax_issues:
            issues.extend(syntax_issues)
            if any(issue.severity == "error" for issue in syntax_issues):
                is_valid = False
        
        # 3. 语义检查（表和列存在性）
        semantic_issues = self._check_semantics(sql)
        if semantic_issues:
            issues.extend(semantic_issues)
            if any(issue.severity == "error" for issue in semantic_issues):
                is_valid = False
        
        # 4. 性能检查（可选）
        if check_performance:
            perf_issues = self._check_performance(sql)
            if perf_issues:
                issues.extend(perf_issues)
        
        # 构建结果
        result = {
            "is_valid": is_valid,
            "sql": sql,
            "issues": [
                {
                    "type": issue.type,
                    "severity": issue.severity,
                    "message": issue.message
                }
                for issue in issues
            ]
        }
        
        # 生成建议
        if issues:
            result["suggestions"] = self._generate_suggestions(issues)
        
        # 如果无效，生成错误消息
        if not is_valid:
            error_messages = [
                issue.message for issue in issues 
                if issue.severity == "error"
            ]
            result["error"] = "; ".join(error_messages)
        
        return result
    
    def _clean_sql(self, sql: str) -> str:
        """清理 SQL 语句"""
        # 移除前后空白
        sql = sql.strip()
        
        # 移除可能的 markdown 代码块标记
        sql = re.sub(r'^```sql\s*', '', sql)
        sql = re.sub(r'\s*```$', '', sql)
        
        # 确保以分号结尾
        if not sql.endswith(';'):
            sql += ';'
        
        return sql
    
    def _check_safety(self, sql: str) -> List[ValidationIssue]:
        """安全检查"""
        issues = []
        sql_upper = sql.upper()
        
        # 禁止的操作
        dangerous_keywords = [
            'DROP', 'DELETE', 'TRUNCATE', 'ALTER', 
            'CREATE', 'INSERT', 'UPDATE', 'GRANT', 'REVOKE'
        ]
        
        for keyword in dangerous_keywords:
            if re.search(rf'\b{keyword}\b', sql_upper):
                issues.append(ValidationIssue(
                    type="safety",
                    severity="error",
                    message=f"不允许执行 {keyword} 操作"
                ))
        
        # 检查注入风险（简单检查）
        if '--' in sql or '/*' in sql or '*/' in sql:
            issues.append(ValidationIssue(
                type="safety",
                severity="warning",
                message="SQL 中包含注释，可能存在注入风险"
            ))
        
        return issues
    
    def _check_syntax(self, sql: str) -> List[ValidationIssue]:
        """语法检查"""
        issues = []
        
        try:
            # 尝试解析 SQL（使用数据库的解析功能）
            # 使用 EXPLAIN 来检查语法
            explain_sql = f"EXPLAIN {sql}"
            self.db.run(explain_sql)
        except Exception as e:
            error_msg = str(e)
            issues.append(ValidationIssue(
                type="syntax",
                severity="error",
                message=f"SQL 语法错误: {error_msg}"
            ))
        
        # 基本语法检查
        sql_upper = sql.upper()
        
        # 检查 SELECT 语句的基本结构
        if 'SELECT' in sql_upper:
            if 'FROM' not in sql_upper:
                issues.append(ValidationIssue(
                    type="syntax",
                    severity="error",
                    message="SELECT 语句缺少 FROM 子句"
                ))
        
        # 检查括号匹配
        open_count = sql.count('(')
        close_count = sql.count(')')
        if open_count != close_count:
            issues.append(ValidationIssue(
                type="syntax",
                severity="error",
                message=f"括号不匹配: {open_count} 个左括号, {close_count} 个右括号"
            ))
        
        return issues
    
    def _check_semantics(self, sql: str) -> List[ValidationIssue]:
        """语义检查（检查表和列的存在性）"""
        issues = []
        
        # 提取 SQL 中的表名
        table_names = self._extract_table_names(sql)
        
        # 获取数据库中的实际表名
        actual_tables = set(self.db.get_usable_table_names())
        
        # 检查表是否存在
        for table in table_names:
            if table.lower() not in [t.lower() for t in actual_tables]:
                issues.append(ValidationIssue(
                    type="semantic",
                    severity="error",
                    message=f"表 '{table}' 不存在"
                ))
        
        # TODO: 可以进一步检查列是否存在
        
        return issues
    
    def _check_performance(self, sql: str) -> List[ValidationIssue]:
        """性能检查"""
        issues = []
        sql_upper = sql.upper()
        
        # 检查是否使用了 SELECT *
        if re.search(r'SELECT\s+\*', sql_upper):
            issues.append(ValidationIssue(
                type="performance",
                severity="warning",
                message="使用 SELECT * 可能影响性能，建议明确指定需要的列"
            ))
        
        # 检查是否缺少 WHERE 子句（对于 UPDATE/DELETE）
        if 'UPDATE' in sql_upper or 'DELETE' in sql_upper:
            if 'WHERE' not in sql_upper:
                issues.append(ValidationIssue(
                    type="performance",
                    severity="error",
                    message="UPDATE/DELETE 语句缺少 WHERE 子句，可能影响所有数据"
                ))
        
        # 检查是否有潜在的笛卡尔积
        if sql_upper.count('FROM') > 0:
            # 简单检查：如果有多个表但没有 JOIN 或 WHERE
            table_count = len(self._extract_table_names(sql))
            if table_count > 1:
                if 'JOIN' not in sql_upper and 'WHERE' not in sql_upper:
                    issues.append(ValidationIssue(
                        type="performance",
                        severity="warning",
                        message="多表查询缺少 JOIN 条件，可能产生笛卡尔积"
                    ))
        
        # 检查是否缺少 LIMIT
        if 'SELECT' in sql_upper and 'LIMIT' not in sql_upper:
            issues.append(ValidationIssue(
                type="performance",
                severity="info",
                message="建议添加 LIMIT 子句限制返回结果数量"
            ))
        
        return issues
    
    def _extract_table_names(self, sql: str) -> List[str]:
        """从 SQL 中提取表名"""
        tables = []
        
        # 移除字符串常量
        sql_cleaned = re.sub(r"'[^']*'", '', sql)
        sql_cleaned = re.sub(r'"[^"]*"', '', sql_cleaned)
        
        # 查找 FROM 和 JOIN 后的表名
        patterns = [
            r'FROM\s+(\w+)',
            r'JOIN\s+(\w+)',
            r'INTO\s+(\w+)',
            r'UPDATE\s+(\w+)',
            r'DELETE\s+FROM\s+(\w+)'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, sql_cleaned, re.IGNORECASE)
            for match in matches:
                table_name = match.group(1)
                if table_name.upper() not in ['SELECT', 'WHERE', 'SET', 'VALUES']:
                    tables.append(table_name)
        
        return list(set(tables))  # 去重
    
    def _generate_suggestions(self, issues: List[ValidationIssue]) -> List[str]:
        """根据问题生成改进建议"""
        suggestions = []
        
        # 根据问题类型生成建议
        issue_types = set(issue.type for issue in issues)
        
        if "syntax" in issue_types:
            suggestions.append("请检查 SQL 语法，确保符合数据库的语法规则")
        
        if "safety" in issue_types:
            suggestions.append("请使用安全的查询操作，避免修改数据的语句")
        
        if "semantic" in issue_types:
            suggestions.append("请检查表名和列名是否正确")
        
        if "performance" in issue_types:
            perf_issues = [i for i in issues if i.type == "performance"]
            for issue in perf_issues:
                if "SELECT *" in issue.message:
                    suggestions.append("明确指定需要查询的列，避免使用 SELECT *")
                if "LIMIT" in issue.message:
                    suggestions.append("添加 LIMIT 子句限制返回结果数量")
        
        return suggestions