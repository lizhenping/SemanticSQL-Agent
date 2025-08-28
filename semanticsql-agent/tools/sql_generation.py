"""SQL 生成工具"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Union
import logging
import re

from .base import BaseSemanticSQLTool, ToolExecResult, ToolParameter

logger = logging.getLogger(__name__)


class SQLGenerationTool(BaseSemanticSQLTool):
    """SQL 生成工具"""
    
    name = "generate_sql"
    description = (
        "基于用户查询和数据库分析结果生成 SQL 语句。"
        "会考虑表结构、字段类型、实体关系等信息生成准确的查询。"
    )
    
    def _init_tool(self) -> None:
        """初始化工具"""
        if not self.prompt_manager:
            from prompts.manager import PromptManager
            self.prompt_manager = PromptManager()
    
    def get_parameters(self) -> List[ToolParameter]:
        """获取工具参数定义"""
        return [
            ToolParameter(
                name="query",
                type="string",
                description="用户的自然语言查询",
                required=True
            ),
            ToolParameter(
                name="schema_info",
                type="dict",
                description="数据库结构信息",
                required=False
            ),
            ToolParameter(
                name="domain_analysis",
                type="dict",
                description="领域分析结果",
                required=False
            ),
            ToolParameter(
                name="field_classification",
                type="dict",
                description="字段分类结果",
                required=False
            ),
            ToolParameter(
                name="relationships",
                type="dict",
                description="实体关系信息",
                required=False
            )
        ]
    
    def execute(
        self,
        query: str,
        schema_info: Optional[Dict[str, Any]] = None,
        domain_analysis: Optional[Dict[str, Any]] = None,
        field_classification: Optional[Dict[str, Any]] = None,
        relationships: Optional[Dict[str, Any]] = None
    ) -> Union[str, ToolExecResult]:
        """生成 SQL"""
        # 使用 Jinja2 模板构建提示词
        pm = self.prompt_manager
        
        # 准备上下文
        context = {
            "query": query,
            "schema": self._format_schema_info(schema_info),
            "domain": self._format_domain_info(domain_analysis),
            "fields": self._format_field_classification(field_classification),
            "relations": self._format_relationships(relationships)
        }
        
        # 获取提示词
        prompt = pm.get_prompt("sql_generation", **context)
        
        # 调用 LLM 生成 SQL
        response = self.llm.invoke(prompt)
        
        # 提取 SQL
        sql = self._extract_sql(response.content)
        
        # 格式化输出
        output = f"""生成的 SQL:
```sql
{sql}
```

说明: {self._generate_explanation(sql, query)}"""
        
        # 返回 ToolExecResult
        return ToolExecResult(
            output=output,
            metadata={
                "sql": sql,
                "query": query,
                "has_schema_info": schema_info is not None,
                "has_domain_analysis": domain_analysis is not None
            }
        )
    
    def _format_schema_info(self, schema_info: Optional[Dict[str, Any]]) -> str:
        """格式化 schema 信息"""
        if not schema_info:
            return "无数据库结构信息"
        
        lines = []
        tables = schema_info.get("tables", [])
        
        for table_info in tables:
            table_name = table_info.get("name", "unknown")
            lines.append(f"\n表: {table_name}")
            
            # 添加行数信息
            if table_info.get("row_count"):
                lines.append(f"  行数: {table_info['row_count']}")
            
            # 添加列信息
            columns = table_info.get("columns", [])
            if columns:
                lines.append("  列:")
                for col in columns[:10]:  # 限制显示数量
                    col_line = f"    - {col['name']}: {col['data_type']}"
                    if col.get("comment"):
                        col_line += f" -- {col['comment']}"
                    lines.append(col_line)
                
                if len(columns) > 10:
                    lines.append(f"    ... 还有 {len(columns) - 10} 列")
        
        return "\n".join(lines)
    
    def _format_domain_info(self, domain_analysis: Optional[Dict[str, Any]]) -> str:
        """格式化领域信息"""
        if not domain_analysis:
            return ""
        
        lines = []
        
        if domain_analysis.get("domain"):
            lines.append(f"业务领域: {domain_analysis['domain']}")
        
        if domain_analysis.get("key_entities"):
            lines.append(f"关键实体: {', '.join(domain_analysis['key_entities'][:5])}")
        
        if domain_analysis.get("business_rules"):
            lines.append("业务规则:")
            for rule in domain_analysis["business_rules"][:3]:
                lines.append(f"  - {rule}")
        
        return "\n".join(lines)
    
    def _format_field_classification(self, field_classification: Optional[Dict[str, Any]]) -> str:
        """格式化字段分类信息"""
        if not field_classification:
            return ""
        
        lines = []
        classification = field_classification.get("classification", {})
        
        # 按类型组织字段
        by_type = {}
        for field, info in classification.items():
            field_type = info.get("type", "unknown")
            if field_type not in by_type:
                by_type[field_type] = []
            by_type[field_type].append(field)
        
        # 只显示重要类型
        important_types = ["measures", "dimensions", "timestamps"]
        for field_type in important_types:
            if field_type in by_type:
                fields = by_type[field_type][:5]  # 限制数量
                lines.append(f"{field_type}: {', '.join(fields)}")
        
        return "\n".join(lines)
    
    def _format_relationships(self, relationships: Optional[Dict[str, Any]]) -> str:
        """格式化关系信息"""
        if not relationships:
            return ""
        
        lines = []
        relationship_list = relationships.get("relationships", [])
        
        for rel in relationship_list[:5]:  # 限制显示数量
            if rel.get("type") == "foreign_key":
                lines.append(
                    f"- {rel['from_table']}.{rel['from_column']} -> "
                    f"{rel['to_table']}.{rel['to_column']}"
                )
        
        return "\n".join(lines)
    
    def _extract_sql(self, content: str) -> str:
        """从响应中提取 SQL"""
        # 查找 SQL 代码块
        sql_match = re.search(r'```sql\n(.*?)\n```', content, re.DOTALL)
        if sql_match:
            return sql_match.group(1).strip()
        
        # 备选方案：查找 SELECT/INSERT/UPDATE 等语句
        sql_keywords = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'WITH']
        for keyword in sql_keywords:
            pattern = rf'({keyword}\s+.*?)(?:;|$)'
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()
        
        # 如果还是没找到，返回整个内容
        return content.strip()
    
    def _generate_explanation(self, sql: str, query: str) -> str:
        """生成 SQL 说明"""
        # 简单分析 SQL
        sql_upper = sql.upper()
        
        explanations = []
        
        # 识别操作类型
        if 'SELECT' in sql_upper:
            if 'GROUP BY' in sql_upper:
                explanations.append("执行分组聚合查询")
            elif 'JOIN' in sql_upper:
                explanations.append("执行表连接查询")
            else:
                explanations.append("执行数据查询")
        
        # 识别聚合函数
        agg_functions = ['COUNT', 'SUM', 'AVG', 'MAX', 'MIN']
        used_functions = [f for f in agg_functions if f in sql_upper]
        if used_functions:
            explanations.append(f"使用了聚合函数: {', '.join(used_functions)}")
        
        # 识别排序
        if 'ORDER BY' in sql_upper:
            if 'DESC' in sql_upper:
                explanations.append("按降序排序")
            else:
                explanations.append("按升序排序")
        
        # 识别限制
        if 'LIMIT' in sql_upper:
            limit_match = re.search(r'LIMIT\s+(\d+)', sql_upper)
            if limit_match:
                explanations.append(f"限制返回 {limit_match.group(1)} 条记录")
        
        return "。".join(explanations) if explanations else "查询数据以回答用户问题"