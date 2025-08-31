"""
SQL验证工具 - 验证SQL语法和结构
"""

import re
import sqlparse
from typing import Dict, Any, List, Optional

from tools.base_tool import BaseTool, ToolParameter
from models.exceptions import ValidationError


class SQLValidationTool(BaseTool):
    """SQL语法验证工具"""
    
    @property
    def name(self) -> str:
        return "sql_validation"
    
    @property
    def description(self) -> str:
        return "验证SQL查询的语法和结构正确性"
    
    @property
    def category(self) -> str:
        return "validation"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="sql",
                type="string",
                description="要验证的SQL查询",
                required=True
            ),
            ToolParameter(
                name="schema_info",
                type="object",
                description="数据库结构信息",
                required=False,
                default={}
            ),
            ToolParameter(
                name="dialect",
                type="string",
                description="SQL方言",
                required=False,
                enum=["mysql", "postgresql", "sqlite"],
                default="mysql"
            ),
            ToolParameter(
                name="strict",
                type="boolean",
                description="是否严格验证",
                required=False,
                default=True
            )
        ]
    
    def _execute(self, sql: str, schema_info: Dict[str, Any] = None,
                 dialect: str = "mysql", strict: bool = True) -> Dict[str, Any]:
        """
        验证SQL
        
        Returns:
            验证结果
        """
        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "suggestions": []
        }
        
        # 基础语法验证
        syntax_result = self._validate_syntax(sql)
        if not syntax_result["valid"]:
            validation_results["valid"] = False
            validation_results["errors"].extend(syntax_result["errors"])
        
        # SQL结构验证
        structure_result = self._validate_structure(sql, dialect)
        if not structure_result["valid"]:
            validation_results["valid"] = False
            validation_results["errors"].extend(structure_result["errors"])
        validation_results["warnings"].extend(structure_result.get("warnings", []))
        
        # 如果提供了schema信息，验证表和字段
        if schema_info and strict:
            schema_result = self._validate_against_schema(sql, schema_info)
            if not schema_result["valid"]:
                validation_results["valid"] = False
                validation_results["errors"].extend(schema_result["errors"])
            validation_results["warnings"].extend(schema_result.get("warnings", []))
        
        # 安全性检查
        security_result = self._check_security(sql)
        if security_result["issues"]:
            validation_results["warnings"].extend(security_result["issues"])
        
        # 性能建议
        performance_suggestions = self._analyze_performance(sql)
        validation_results["suggestions"].extend(performance_suggestions)
        
        # 格式化SQL
        validation_results["formatted_sql"] = self._format_sql(sql)
        
        # 提取SQL元数据
        validation_results["metadata"] = self._extract_metadata(sql)
        
        return validation_results
    
    def _validate_syntax(self, sql: str) -> Dict[str, Any]:
        """验证SQL语法"""
        errors = []
        
        try:
            # 使用sqlparse解析SQL
            parsed = sqlparse.parse(sql)
            
            if not parsed:
                errors.append("无法解析SQL语句")
                return {"valid": False, "errors": errors}
            
            # 检查基本语法元素
            statement = parsed[0]
            
            # 检查是否有SQL关键字
            if not any(token.ttype in sqlparse.tokens.Keyword.DML for token in statement.tokens):
                errors.append("缺少SQL操作关键字（SELECT/INSERT/UPDATE/DELETE）")
            
            # 检查括号匹配
            open_parens = sql.count('(')
            close_parens = sql.count(')')
            if open_parens != close_parens:
                errors.append(f"括号不匹配：左括号{open_parens}个，右括号{close_parens}个")
            
            # 检查引号匹配
            single_quotes = sql.count("'")
            if single_quotes % 2 != 0:
                errors.append("单引号不匹配")
            
            double_quotes = sql.count('"')
            if double_quotes % 2 != 0:
                errors.append("双引号不匹配")
            
        except Exception as e:
            errors.append(f"语法解析错误：{str(e)}")
        
        return {"valid": len(errors) == 0, "errors": errors}
    
    def _validate_structure(self, sql: str, dialect: str) -> Dict[str, Any]:
        """验证SQL结构"""
        errors = []
        warnings = []
        
        sql_upper = sql.upper()
        
        # SELECT语句检查
        if 'SELECT' in sql_upper:
            # 检查是否有FROM子句
            if 'FROM' not in sql_upper:
                warnings.append("SELECT语句缺少FROM子句（可能是子查询）")
            
            # 检查GROUP BY和聚合函数
            if 'GROUP BY' in sql_upper:
                aggregates = ['COUNT', 'SUM', 'AVG', 'MAX', 'MIN']
                if not any(agg in sql_upper for agg in aggregates):
                    warnings.append("使用了GROUP BY但没有聚合函数")
            
            # 检查HAVING without GROUP BY
            if 'HAVING' in sql_upper and 'GROUP BY' not in sql_upper:
                errors.append("使用了HAVING但没有GROUP BY")
        
        # JOIN语句检查
        if 'JOIN' in sql_upper:
            # 检查ON条件
            join_pattern = r'(INNER|LEFT|RIGHT|FULL|CROSS)?\s*JOIN\s+\w+'
            joins = re.findall(join_pattern, sql_upper)
            on_conditions = sql_upper.count(' ON ')
            
            # CROSS JOIN不需要ON条件
            cross_joins = sql_upper.count('CROSS JOIN')
            expected_on = len(joins) - cross_joins
            
            if on_conditions < expected_on:
                warnings.append(f"JOIN缺少ON条件（期望{expected_on}个，实际{on_conditions}个）")
        
        # 检查UNION
        if 'UNION' in sql_upper:
            # 检查UNION的查询是否有相同数量的列
            union_parts = re.split(r'\bUNION\b', sql, flags=re.IGNORECASE)
            if len(union_parts) > 1:
                # 简单检查SELECT后的列数
                for part in union_parts:
                    if 'SELECT' not in part.upper():
                        errors.append("UNION中的某个部分缺少SELECT")
        
        # 方言特定检查
        if dialect == "mysql":
            # MySQL特定语法
            if '::' in sql:
                errors.append("MySQL不支持::类型转换语法，请使用CAST或CONVERT")
        elif dialect == "postgresql":
            # PostgreSQL特定语法
            if 'LIMIT' in sql_upper and ',' in sql[sql_upper.index('LIMIT'):]:
                errors.append("PostgreSQL的LIMIT语法不支持逗号分隔，请使用LIMIT n OFFSET m")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def _validate_against_schema(self, sql: str, schema_info: Dict[str, Any]) -> Dict[str, Any]:
        """验证SQL中的表和字段是否存在"""
        errors = []
        warnings = []
        
        # 提取SQL中的表名
        sql_tables = self._extract_tables(sql)
        schema_tables = set(schema_info.get("tables", {}).keys())
        
        # 检查表是否存在
        for table in sql_tables:
            if table not in schema_tables:
                errors.append(f"表 '{table}' 不存在于数据库中")
        
        # 提取并验证字段
        for table in sql_tables:
            if table in schema_info.get("tables", {}):
                table_info = schema_info["tables"][table]
                valid_columns = {col["name"] for col in table_info.get("columns", [])}
                
                # 尝试提取该表的字段引用
                sql_columns = self._extract_columns_for_table(sql, table)
                
                for column in sql_columns:
                    if column != '*' and column not in valid_columns:
                        errors.append(f"字段 '{table}.{column}' 不存在")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def _check_security(self, sql: str) -> Dict[str, Any]:
        """安全性检查"""
        issues = []
        
        sql_upper = sql.upper()
        
        # 检查危险操作
        dangerous_keywords = ['DROP', 'TRUNCATE', 'DELETE', 'ALTER', 'CREATE']
        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                issues.append(f"包含潜在危险操作：{keyword}")
        
        # 检查SQL注入风险标记
        injection_patterns = [
            r';\s*--',  # 分号后跟注释
            r'OR\s+1\s*=\s*1',  # 常见注入模式
            r'UNION\s+SELECT\s+NULL',  # UNION注入
            r'EXEC\s*\(',  # 执行存储过程
        ]
        
        for pattern in injection_patterns:
            if re.search(pattern, sql_upper):
                issues.append(f"检测到潜在SQL注入模式：{pattern}")
        
        # 检查是否有未参数化的字符串
        if "'" in sql or '"' in sql:
            issues.append("SQL中包含硬编码的字符串，建议使用参数化查询")
        
        return {"issues": issues}
    
    def _analyze_performance(self, sql: str) -> List[str]:
        """分析性能并提供优化建议"""
        suggestions = []
        
        sql_upper = sql.upper()
        
        # SELECT * 检查
        if 'SELECT *' in sql_upper:
            suggestions.append("避免使用SELECT *，只选择需要的列")
        
        # 缺少索引提示
        if 'WHERE' in sql_upper:
            # 检查是否在WHERE子句中使用函数
            if re.search(r'WHERE\s+\w+\([^)]+\)', sql_upper):
                suggestions.append("WHERE子句中对字段使用函数可能导致索引失效")
        
        # 大表JOIN提示
        join_count = sql_upper.count('JOIN')
        if join_count > 3:
            suggestions.append(f"包含{join_count}个JOIN，考虑是否可以优化查询逻辑")
        
        # 子查询提示
        if '(SELECT' in sql_upper.replace(' ', ''):
            suggestions.append("包含子查询，考虑是否可以改写为JOIN以提高性能")
        
        # LIKE查询优化
        if 'LIKE' in sql_upper:
            if re.search(r"LIKE\s+'%[^']+", sql):
                suggestions.append("LIKE查询以%开头会导致索引失效")
        
        # ORDER BY RAND()
        if 'ORDER BY RAND()' in sql_upper or 'ORDER BY RANDOM()' in sql_upper:
            suggestions.append("ORDER BY RAND()性能较差，考虑其他随机选择方案")
        
        return suggestions
    
    def _format_sql(self, sql: str) -> str:
        """格式化SQL"""
        try:
            return sqlparse.format(
                sql,
                reindent=True,
                keyword_case='upper',
                identifier_case='lower',
                strip_comments=False,
                use_space_around_operators=True
            )
        except:
            return sql
    
    def _extract_metadata(self, sql: str) -> Dict[str, Any]:
        """提取SQL元数据"""
        metadata = {
            "type": self._get_query_type(sql),
            "tables": self._extract_tables(sql),
            "has_where": 'WHERE' in sql.upper(),
            "has_join": 'JOIN' in sql.upper(),
            "has_group_by": 'GROUP BY' in sql.upper(),
            "has_order_by": 'ORDER BY' in sql.upper(),
            "has_limit": 'LIMIT' in sql.upper(),
            "has_subquery": '(SELECT' in sql.upper().replace(' ', ''),
            "estimated_complexity": self._estimate_complexity(sql)
        }
        return metadata
    
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
        else:
            return 'OTHER'
    
    def _extract_tables(self, sql: str) -> List[str]:
        """提取SQL中的表名"""
        tables = []
        
        # FROM子句中的表
        from_pattern = r'FROM\s+([^\s,]+)'
        from_matches = re.findall(from_pattern, sql, re.IGNORECASE)
        tables.extend(from_matches)
        
        # JOIN子句中的表
        join_pattern = r'JOIN\s+([^\s]+)'
        join_matches = re.findall(join_pattern, sql, re.IGNORECASE)
        tables.extend(join_matches)
        
        # 去重并清理
        tables = list(set(t.strip('`"[]') for t in tables))
        
        return tables
    
    def _extract_columns_for_table(self, sql: str, table: str) -> List[str]:
        """提取特定表的字段引用"""
        columns = []
        
        # 简单的字段提取（这里可以更复杂）
        # 查找 table.column 模式
        pattern = rf'{re.escape(table)}\.(\w+)'
        matches = re.findall(pattern, sql, re.IGNORECASE)
        columns.extend(matches)
        
        return list(set(columns))
    
    def _estimate_complexity(self, sql: str) -> str:
        """估算SQL复杂度"""
        score = 0
        sql_upper = sql.upper()
        
        # 基础分数
        score += 1
        
        # JOIN复杂度
        score += sql_upper.count('JOIN') * 2
        
        # 子查询复杂度
        score += sql_upper.count('(SELECT') * 3
        
        # GROUP BY复杂度
        if 'GROUP BY' in sql_upper:
            score += 2
        
        # HAVING复杂度
        if 'HAVING' in sql_upper:
            score += 2
        
        # UNION复杂度
        score += sql_upper.count('UNION') * 2
        
        # 窗口函数复杂度
        if 'OVER(' in sql_upper.replace(' ', ''):
            score += 3
        
        # CTE复杂度
        if 'WITH' in sql_upper and 'AS (' in sql_upper:
            score += 3
        
        # 根据分数判断复杂度
        if score <= 2:
            return "simple"
        elif score <= 5:
            return "medium"
        else:
            return "complex"