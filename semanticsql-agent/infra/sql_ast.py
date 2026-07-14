"""SQL AST 解析抽象层（infra/sql_ast.py）

设计原则：
- 供 Phase 3 Diagnose 的程序化校验用（列/JOIN/聚合检查）
- SQLAstParser 协议可注入假实现做单测
- SqlglotParser 用 sqlglot（纯 Python 轻量包）解析

这是论文 Fig.1（AVG(CDSCode)）反例的程序化检测基础：
  extract_aggregates(sql) -> [AVG(CDSCode)]
  -> 查 K3 得 CDSCode=identifier
  -> 报错：aggregation_type_mismatch
"""

from typing import Protocol
from pydantic import BaseModel


class AggregateCall(BaseModel):
    """聚合函数调用（如 AVG(CDSCode)）"""

    func: str           # SUM/AVG/COUNT/MIN/MAX
    table: str          # 表名
    column: str         # 列名
    clause: str = ""    # 所在子句（SELECT/WHERE/HAVING）


class JoinClause(BaseModel):
    """JOIN 子句"""

    left_table: str
    right_table: str
    left_column: str
    right_column: str


class SQLAstParser(Protocol):
    """SQL AST 解析协议"""

    def extract_aggregates(self, sql: str) -> list[AggregateCall]:
        """提取所有聚合函数调用"""
        ...

    def extract_joins(self, sql: str) -> list[JoinClause]:
        """提取所有 JOIN 子句"""
        ...

    def extract_columns(self, sql: str) -> list[tuple[str, str]]:
        """提取所有引用的列，返回 [(table, column), ...]"""
        ...

    def extract_tables(self, sql: str) -> list[str]:
        """提取所有引用的表名"""
        ...


class SqlglotParser:
    """sqlglot 实现（纯 Python，轻量）

    需要安装: pip install sqlglot
    """

    def __init__(self, dialect: str = "sqlite"):
        self.dialect = dialect

    def _parse(self, sql: str):
        """解析 SQL 为 AST"""
        import sqlglot
        return sqlglot.parse_one(sql, dialect=self.dialect)

    @staticmethod
    def _nodes_by_classname(ast, class_name: str):
        """按类名遍历 AST 节点（兼容 sqlglot 各版本的 walk()）。

        sqlglot 30.x 的 find_all() 不再接受谓词 lambda，改用 walk()。
        """
        for node in ast.walk():
            # walk() yield 的元素在不同版本可能是 node 或 (node, parent, key)
            n = node[0] if isinstance(node, tuple) else node
            if n.__class__.__name__ == class_name:
                yield n

    def extract_aggregates(self, sql: str) -> list[AggregateCall]:
        """提取所有聚合函数调用（SUM/AVG/COUNT/MIN/MAX）"""
        try:
            ast = self._parse(sql)
        except Exception:
            return []

        aggregates = []
        agg_funcs = {"SUM", "AVG", "COUNT", "MIN", "MAX"}

        for node in self._nodes_by_classname(ast, "AggFunc"):
            func_name = str(node.key).upper() if hasattr(node, "key") else node.sql_name().upper()
            if func_name in agg_funcs:
                # 提取参数列
                arg = node.this if hasattr(node, "this") else None
                if arg is not None:
                    table, column = self._extract_table_column(arg)
                    clause = self._find_containing_clause(ast, node)
                    aggregates.append(AggregateCall(
                        func=func_name, table=table, column=column, clause=clause
                    ))
        return aggregates

    def extract_joins(self, sql: str) -> list[JoinClause]:
        """提取所有 JOIN 子句的 ON 条件"""
        try:
            ast = self._parse(sql)
        except Exception:
            return []

        joins = []
        for join_node in self._nodes_by_classname(ast, "Join"):
            # 获取 JOIN 的右侧表
            right_table = ""
            if hasattr(join_node, "this"):
                right_table = join_node.this.name or ""

            # 获取 ON 条件
            on_condition = None
            if hasattr(join_node, "on") and join_node.on is not None:
                on_condition = join_node.on

            if on_condition is not None:
                # 从 ON 条件提取左右列
                left_col, right_col = self._extract_join_columns(on_condition)
                left_table = self._find_table_for_column(ast, left_col, right_table)
                if left_col and right_col:
                    joins.append(JoinClause(
                        left_table=left_table,
                        right_table=right_table,
                        left_column=left_col,
                        right_column=right_col,
                    ))
        return joins

    def extract_columns(self, sql: str) -> list[tuple[str, str]]:
        """提取所有引用的列，返回 [(table, column), ...]"""
        try:
            ast = self._parse(sql)
        except Exception:
            return []

        columns = []
        seen = set()
        for col_node in self._nodes_by_classname(ast, "Column"):
            table = col_node.table or ""
            column = col_node.name or ""
            key = (table, column)
            if key not in seen and column:
                seen.add(key)
                columns.append(key)
        return columns

    def extract_tables(self, sql: str) -> list[str]:
        """提取所有引用的表名"""
        try:
            ast = self._parse(sql)
        except Exception:
            return []

        tables = []
        seen = set()
        for table_node in self._nodes_by_classname(ast, "Table"):
            name = table_node.name or ""
            if name and name not in seen:
                seen.add(name)
                tables.append(name)
        return tables

    # ========== 辅助方法 ==========

    def _extract_table_column(self, node) -> tuple[str, str]:
        """从 AST 节点提取 (table, column)"""
        if node is None:
            return ("", "")
        if hasattr(node, "table") and hasattr(node, "name"):
            return (node.table or "", node.name or "")
        if hasattr(node, "name"):
            return ("", node.name or "")
        return ("", str(node))

    def _find_containing_clause(self, ast, node) -> str:
        """判断节点所在的 SQL 子句"""
        # 简化实现：检查 node 的父节点链
        try:
            parent = node.parent
            while parent is not None:
                cls_name = parent.__class__.__name__
                if cls_name == "Select":
                    return "SELECT"
                elif cls_name == "Where":
                    return "WHERE"
                elif cls_name == "Having":
                    return "HAVING"
                elif cls_name == "Order":
                    return "ORDER BY"
                parent = parent.parent
        except Exception:
            pass
        return "UNKNOWN"

    def _extract_join_columns(self, on_condition) -> tuple[str, str]:
        """从 ON 条件提取左右列名"""
        try:
            # ON 条件通常是 a.x = b.y 形式
            if hasattr(on_condition, "left") and hasattr(on_condition, "right"):
                left = on_condition.left
                right = on_condition.right
                left_col = left.name if hasattr(left, "name") else str(left)
                right_col = right.name if hasattr(right, "name") else str(right)
                return (left_col, right_col)
        except Exception:
            pass
        return ("", "")

    def _find_table_for_column(self, ast, column: str, exclude_table: str = "") -> str:
        """推断列属于哪个表"""
        try:
            for col_node in self._nodes_by_classname(ast, "Column"):
                if col_node.name == column and col_node.table and col_node.table != exclude_table:
                    return col_node.table
        except Exception:
            pass
        return ""


class FakeSQLAstParser:
    """假 SQL 解析器（单测用）"""

    def __init__(self, aggregates=None, joins=None, columns=None, tables=None):
        self._aggregates = aggregates or []
        self._joins = joins or []
        self._columns = columns or []
        self._tables = tables or []

    def extract_aggregates(self, sql: str) -> list[AggregateCall]:
        return self._aggregates

    def extract_joins(self, sql: str) -> list[JoinClause]:
        return self._joins

    def extract_columns(self, sql: str) -> list[tuple[str, str]]:
        return self._columns

    def extract_tables(self, sql: str) -> list[str]:
        return self._tables
