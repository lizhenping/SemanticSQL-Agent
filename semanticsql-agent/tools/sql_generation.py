"""SQL 生成工具（支持 tool calling）"""

from typing import Dict, Any, Optional, List
import logging
import re

from .base import Tool, ToolParameter
from ..utils.llm_clients import LLMClient, LLMMessage
from ..utils.json_parser import extract_code

logger = logging.getLogger(__name__)


# SQL 生成提示词模板
SQL_GENERATION_PROMPT = """你是一个 SQL 专家。根据用户的查询需求和数据库信息生成准确的 SQL 语句。

数据库信息：
{schema_info}

用户查询：{query}

要求：
1. 生成语法正确的 SQL
2. 使用合适的 JOIN 连接相关表
3. 添加必要的 WHERE 条件
4. 只返回 SQL 语句，使用 ```sql 代码块包围

请生成 SQL："""


class SQLGenerationTool(Tool):
    """SQL 生成工具"""
    
    def __init__(self, llm_client: LLMClient):
        super().__init__(
            name="generate_sql",
            description="根据用户的自然语言查询生成 SQL 语句。需要提供查询内容，可选提供数据库架构信息。"
        )
        self.llm = llm_client
    
    @property
    def parameters(self) -> List[ToolParameter]:
        """定义工具参数"""
        return [
            ToolParameter(
                name="query",
                type="string",
                description="用户的自然语言查询",
                required=True
            ),
            ToolParameter(
                name="schema_info",
                type="object",
                description="数据库架构信息，包含表结构、字段等",
                required=False
            )
        ]
    
    def execute(
        self,
        query: str,
        schema_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """生成 SQL
        
        这个方法会被 tool calling 机制调用
        """
        # 格式化 schema 信息
        schema_text = self._format_schema_info(schema_info) if schema_info else "无数据库结构信息"
        
        # 构建提示词
        prompt = SQL_GENERATION_PROMPT.format(
            schema_info=schema_text,
            query=query
        )
        
        # 调用 LLM（这里是普通调用，不是 tool calling）
        messages = [LLMMessage(role="user", content=prompt)]
        response = self.llm.chat(messages, tools=None, reuse_history=False)
        
        # 提取 SQL
        sql = extract_code(response.content, "sql")
        if not sql:
            # 如果没有代码块，尝试其他方式提取
            sql = self._extract_sql_fallback(response.content)
        
        return {
            "sql": sql,
            "query": query,
            "explanation": self._generate_explanation(sql, query)
        }
    
    def _format_schema_info(self, schema_info: Dict[str, Any]) -> str:
        """格式化数据库结构信息"""
        lines = []
        tables = schema_info.get("tables", [])
        
        for table in tables[:10]:  # 限制表数量
            table_name = table.get("name", "unknown")
            lines.append(f"\n表: {table_name}")
            
            # 列信息
            columns = table.get("columns", [])
            if columns:
                lines.append("  列:")
                for col in columns[:10]:  # 限制列数量
                    col_line = f"    - {col['name']}: {col['data_type']}"
                    if col.get("is_primary_key"):
                        col_line += " (主键)"
                    if col.get("comment"):
                        col_line += f" -- {col['comment']}"
                    lines.append(col_line)
        
        return "\n".join(lines)
    
    def _extract_sql_fallback(self, text: str) -> str:
        """备用 SQL 提取方法"""
        # 查找 SELECT 语句
        select_match = re.search(r'(SELECT\s+.*?)(?:;|\s*$)', text, re.IGNORECASE | re.DOTALL)
        if select_match:
            return select_match.group(1).strip()
        
        # 返回整个文本
        return text.strip()
    
    def _generate_explanation(self, sql: str, query: str) -> str:
        """生成 SQL 说明"""
        sql_upper = sql.upper()
        
        parts = []
        if "SELECT" in sql_upper:
            parts.append("查询")
        if "JOIN" in sql_upper:
            parts.append("多表关联")
        if "WHERE" in sql_upper:
            parts.append("条件筛选")
        if "GROUP BY" in sql_upper:
            parts.append("分组聚合")
        if "ORDER BY" in sql_upper:
            parts.append("排序")
        
        return f"根据'{query}'生成的{'/'.join(parts) if parts else 'SQL'}"