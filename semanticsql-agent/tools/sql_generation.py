"""SQL 生成工具（无 LangChain 依赖）"""

from typing import Dict, Any, Optional
import logging
import re

from .base import Tool
from ..llm_client import LLMClient
from ..llm_basics import LLMMessage
from ..utils import extract_code

logger = logging.getLogger(__name__)


# SQL 生成提示词模板（内联）
SQL_GENERATION_PROMPT = """你是一个 SQL 专家。根据用户的查询需求和数据库信息生成准确的 SQL 语句。

数据库信息：
{schema_info}

{domain_info}

{field_info}

{relationship_info}

用户查询：{query}

要求：
1. 生成语法正确的 SQL
2. 使用合适的 JOIN 连接相关表
3. 添加必要的 WHERE 条件
4. 考虑性能，避免全表扫描
5. 只返回 SQL 语句，使用 ```sql 代码块包围

请生成 SQL："""


class SQLGenerationTool(Tool):
    """SQL 生成工具"""
    
    def __init__(self, llm_client: LLMClient):
        super().__init__(
            name="generate_sql",
            description="基于用户查询和数据库分析结果生成 SQL 语句"
        )
        self.llm = llm_client
    
    def execute(
        self,
        query: str,
        schema_info: Optional[Dict[str, Any]] = None,
        domain_analysis: Optional[Dict[str, Any]] = None,
        field_classification: Optional[Dict[str, Any]] = None,
        relationships: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """生成 SQL"""
        # 格式化各种信息
        schema_text = self._format_schema_info(schema_info) if schema_info else "无数据库结构信息"
        domain_text = self._format_domain_info(domain_analysis) if domain_analysis else ""
        field_text = self._format_field_info(field_classification) if field_classification else ""
        relationship_text = self._format_relationships(relationships) if relationships else ""
        
        # 构建提示词
        prompt = SQL_GENERATION_PROMPT.format(
            schema_info=schema_text,
            domain_info=f"领域信息：\n{domain_text}" if domain_text else "",
            field_info=f"字段分类：\n{field_text}" if field_text else "",
            relationship_info=f"表关系：\n{relationship_text}" if relationship_text else "",
            query=query
        )
        
        # 调用 LLM
        messages = [LLMMessage(role="user", content=prompt)]
        response = self.llm.chat(messages)
        
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
        
        for table in tables[:20]:  # 限制表数量
            table_name = table.get("name", "unknown")
            lines.append(f"\n表: {table_name}")
            
            # 行数
            if "row_count" in table:
                lines.append(f"  行数: {table['row_count']}")
            
            # 列信息
            columns = table.get("columns", [])
            if columns:
                lines.append("  列:")
                for col in columns[:15]:  # 限制列数量
                    col_line = f"    - {col['name']}: {col['data_type']}"
                    if col.get("is_primary_key"):
                        col_line += " (主键)"
                    if col.get("is_foreign_key"):
                        col_line += " (外键)"
                    if col.get("comment"):
                        col_line += f" -- {col['comment']}"
                    lines.append(col_line)
            
            # 外键
            foreign_keys = table.get("foreign_keys", [])
            if foreign_keys:
                lines.append("  外键:")
                for fk in foreign_keys[:5]:
                    lines.append(f"    - {fk['column']} -> {fk['referenced_table']}.{fk['referenced_column']}")
        
        return "\n".join(lines)
    
    def _format_domain_info(self, domain_analysis: Dict[str, Any]) -> str:
        """格式化领域信息"""
        lines = []
        
        if "domain" in domain_analysis:
            lines.append(f"业务领域: {domain_analysis['domain']}")
        
        if "key_entities" in domain_analysis:
            entities = domain_analysis["key_entities"][:10]
            lines.append(f"关键实体: {', '.join(entities)}")
        
        if "business_rules" in domain_analysis:
            lines.append("业务规则:")
            for rule in domain_analysis["business_rules"][:5]:
                lines.append(f"  - {rule}")
        
        return "\n".join(lines)
    
    def _format_field_info(self, field_classification: Dict[str, Any]) -> str:
        """格式化字段分类信息"""
        lines = []
        
        # 获取关键字段
        overall_stats = field_classification.get("overall_statistics", {})
        
        if "top_measures" in overall_stats:
            measures = overall_stats["top_measures"][:5]
            if measures:
                lines.append(f"度量字段: {', '.join(measures)}")
        
        if "top_dimensions" in overall_stats:
            dimensions = overall_stats["top_dimensions"][:5]
            if dimensions:
                lines.append(f"维度字段: {', '.join(dimensions)}")
        
        if "all_timestamps" in overall_stats:
            timestamps = overall_stats["all_timestamps"][:3]
            if timestamps:
                lines.append(f"时间字段: {', '.join(timestamps)}")
        
        return "\n".join(lines)
    
    def _format_relationships(self, relationships: Dict[str, Any]) -> str:
        """格式化关系信息"""
        lines = []
        
        relations = relationships.get("relationships", [])
        for rel in relations[:10]:
            if rel.get("type") == "foreign_key":
                lines.append(f"- {rel['from_table']}.{rel['from_column']} -> {rel['to_table']}.{rel['to_column']}")
            elif rel.get("type") == "many-to-many":
                lines.append(f"- {rel['from_table']} <-> {rel['to_table']} (通过 {rel.get('via_table', 'unknown')})")
        
        return "\n".join(lines)
    
    def _extract_sql_fallback(self, text: str) -> str:
        """备用 SQL 提取方法"""
        # 查找 SELECT 语句
        select_match = re.search(r'(SELECT\s+.*?);?\s*$', text, re.IGNORECASE | re.DOTALL)
        if select_match:
            return select_match.group(1).strip()
        
        # 查找其他 SQL 语句
        sql_keywords = ['INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP']
        for keyword in sql_keywords:
            match = re.search(rf'({keyword}\s+.*?);?\s*$', text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()
        
        # 返回整个文本
        return text.strip()
    
    def _generate_explanation(self, sql: str, query: str) -> str:
        """生成 SQL 说明"""
        # 简单分析 SQL
        explanations = []
        
        sql_upper = sql.upper()
        
        # 检查查询类型
        if "SELECT" in sql_upper:
            if "COUNT(" in sql_upper:
                explanations.append("统计查询")
            elif "SUM(" in sql_upper or "AVG(" in sql_upper:
                explanations.append("聚合查询")
            elif "GROUP BY" in sql_upper:
                explanations.append("分组查询")
            else:
                explanations.append("数据查询")
        
        # 检查 JOIN
        if "JOIN" in sql_upper:
            join_count = sql_upper.count("JOIN")
            explanations.append(f"包含 {join_count} 个表连接")
        
        # 检查条件
        if "WHERE" in sql_upper:
            explanations.append("有筛选条件")
        
        # 检查排序
        if "ORDER BY" in sql_upper:
            explanations.append("结果已排序")
        
        return f"根据 '{query}' 生成的 {', '.join(explanations) if explanations else 'SQL 查询'}"