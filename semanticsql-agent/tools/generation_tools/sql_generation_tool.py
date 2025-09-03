"""
SQL生成工具 - 根据问题生成SQL查询
基于 LangChain BaseTool
"""

import re
from typing import Dict, Any, Type, List, Optional
from langchain.tools import BaseTool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from models.base import SQLOperation
from models.exceptions import ToolExecutionError, LLMError
from utils.database import DatabaseManager
from prompts.manager import PromptManager


class SQLGenerationInput(BaseModel):
    """SQL生成输入"""
    question: str = Field(description="自然语言问题")
    memory: Dict[str, Any] = Field(description="包含数据库分析结果的记忆")
    operations: List[str] = Field(default_factory=list, description="建议的SQL操作")


class GeneratedSQL(BaseModel):
    """生成的SQL查询"""
    sql: str = Field(description="SQL语句")
    dialect: str = Field(default="mysql", description="SQL方言")
    tables_used: List[str] = Field(description="使用的表")
    operations_used: List[str] = Field(description="使用的操作")
    has_aggregation: bool = Field(description="是否包含聚合")
    has_join: bool = Field(default=False, description="是否包含JOIN")
    complexity: str = Field(default="medium", description="复杂度")


class SQLGenerationTool(BaseTool):
    """生成SQL查询语句"""
    
    name: str = "sql_generation"
    description: str = "根据自然语言问题和数据库结构生成对应的SQL查询"
    args_schema: Type[BaseModel] = SQLGenerationInput
    
    def __init__(self, llm: ChatOpenAI, db_manager: Optional[DatabaseManager] = None):
        super().__init__()
        object.__setattr__(self, 'llm', llm)
        object.__setattr__(self, 'db_manager', db_manager)
        object.__setattr__(self, 'prompt_manager', PromptManager())
    
    def _run(
        self,
        question: str,
        memory: Dict[str, Any],
        operations: List[str] = None,
        dialect: str = "mysql"
    ) -> Dict[str, Any]:
        """生成SQL查询"""
        try:
            # 从记忆中获取必要信息
            db_analysis = memory.get("db_analysis", {})
            schema_info = db_analysis.get("schema_info", {})
            domain_info = db_analysis.get("domain_info", {})
            field_classification = db_analysis.get("field_classification", {})
            
            if not schema_info:
                raise ToolExecutionError(
                    tool_name=self.name,
                    reason="未找到数据库结构信息，请先执行数据库分析"
                )
            
            # 构建提示词上下文
            context = self._build_context(
                schema_info, domain_info, field_classification, operations
            )
            
            # 生成SQL
            sql = self._generate_sql_with_llm(question, context, dialect)
            
            # 后处理
            sql = self._postprocess_sql(sql, dialect)
            
            # 分析SQL
            analysis = self._analyze_sql(sql, schema_info)
            
            return {
                "sql": sql,
                "dialect": dialect,
                "tables_used": analysis["tables"],
                "operations_used": analysis["operations"],
                "has_aggregation": analysis["has_aggregation"],
                "has_join": analysis["has_join"],
                "complexity": analysis["complexity"]
            }
            
        except LLMError:
            raise
        except Exception as e:
            raise ToolExecutionError(
                tool_name=self.name,
                reason=f"SQL生成失败: {str(e)}"
            )
    
    def _build_context(
        self,
        schema_info: Dict[str, Any],
        domain_info: Dict[str, Any],
        field_classification: Dict[str, Any],
        operations: Optional[List[str]]
    ) -> str:
        """构建LLM生成SQL所需的上下文"""
        context_parts = []
        
        # 添加领域信息
        if domain_info:
            primary_domain = domain_info.get("primary_domain", "")
            if primary_domain:
                context_parts.append(f"业务领域：{primary_domain}")
        
        # 添加表结构信息
        context_parts.append("\n数据库结构：")
        tables = schema_info.get("tables", {})
        
        for table_name, table_info in tables.items():
            context_parts.append(f"\n表：{table_name}")
            
            # 添加表注释
            if table_info.get("comment"):
                context_parts.append(f"  说明：{table_info['comment']}")
            
            # 添加列信息
            columns = table_info.get("columns", [])
            context_parts.append("  列：")
            
            for col in columns[:20]:  # 限制列数避免上下文过长
                col_desc = f"    - {col['name']} ({col['type']})"
                
                # 添加列的业务含义（如果有）
                if field_classification:
                    table_fields = field_classification.get("field_classifications", {}).get(table_name, {})
                    field_info = table_fields.get(col['name'], {})
                    if field_info.get("business_meaning"):
                        col_desc += f" -- {field_info['business_meaning']}"
                
                context_parts.append(col_desc)
            
            # 添加主键信息
            if table_info.get("primary_keys"):
                context_parts.append(f"  主键：{', '.join(table_info['primary_keys'])}")
            
            # 添加外键信息
            foreign_keys = table_info.get("foreign_keys", [])
            if foreign_keys:
                for fk in foreign_keys[:5]:  # 限制外键数量
                    fk_cols = ', '.join(fk.get("constrained_columns", []))
                    ref_table = fk.get("referred_table", "")
                    ref_cols = ', '.join(fk.get("referred_columns", []))
                    context_parts.append(
                        f"  外键：{fk_cols} -> {ref_table}({ref_cols})"
                    )
        
        # 添加操作建议
        if operations:
            context_parts.append(f"\n建议使用的SQL操作：{', '.join(operations)}")
        
        return "\n".join(context_parts)
    
    def _generate_sql_with_llm(
        self,
        question: str,
        context: str,
        dialect: str
    ) -> str:
        """使用LLM生成SQL"""
        prompt = self.prompt_manager.get_tool_prompt(
            "sql_generation",
            context=context,
            dialect=dialect,
            question=question
        )

        try:
            response = self.llm.invoke(prompt)
            sql = response.content.strip()
            
            # 提取SQL（如果被包裹在代码块中）
            sql_match = re.search(r'```sql\s*(.*?)\s*```', sql, re.DOTALL | re.IGNORECASE)
            if sql_match:
                sql = sql_match.group(1).strip()
            
            return sql
            
        except Exception as e:
            raise LLMError(
                model=self.llm.model_name,
                reason=f"LLM生成SQL失败: {str(e)}"
            )
    
    def _postprocess_sql(self, sql: str, dialect: str) -> str:
        """后处理SQL"""
        # 移除多余的空白
        sql = re.sub(r'\s+', ' ', sql).strip()
        
        # 确保以分号结尾
        if not sql.endswith(';'):
            sql += ';'
        
        # MySQL特定处理
        if dialect == "mysql":
            # 确保使用反引号而不是双引号
            sql = sql.replace('"', '`')
        
        return sql
    
    def _analyze_sql(self, sql: str, schema_info: Dict[str, Any]) -> Dict[str, Any]:
        """分析SQL语句"""
        sql_lower = sql.lower()
        
        # 提取使用的表
        tables_used = []
        all_tables = list(schema_info.get("tables", {}).keys())
        
        for table in all_tables:
            # 检查表名是否在SQL中（考虑别名）
            table_pattern = rf'\b{re.escape(table)}\b'
            if re.search(table_pattern, sql, re.IGNORECASE):
                tables_used.append(table)
        
        # 识别SQL操作
        operations_used = []
        
        if re.search(r'\bselect\b', sql_lower):
            operations_used.append(SQLOperation.SELECT.value)
        
        if re.search(r'\bjoin\b', sql_lower):
            operations_used.append(SQLOperation.JOIN.value)
        
        if re.search(r'\bgroup\s+by\b', sql_lower):
            operations_used.append(SQLOperation.GROUP.value)
        
        if re.search(r'\bwith\s+\w+\s+as\s*\(', sql_lower):
            operations_used.append(SQLOperation.CTE.value)
        
        if re.search(r'over\s*\(', sql_lower):
            operations_used.append(SQLOperation.WINDOW.value)
        
        if re.search(r'\bunion\b', sql_lower):
            operations_used.append(SQLOperation.UNION.value)
        
        # 检查子查询
        if sql_lower.count('select') > 1:
            operations_used.append(SQLOperation.SUBQUERY.value)
        
        # 检查聚合
        has_aggregation = any(
            agg in sql_lower 
            for agg in ['count(', 'sum(', 'avg(', 'max(', 'min(']
        )
        
        # 检查连接
        has_join = 'join' in sql_lower
        
        # 估计复杂度
        complexity = self._estimate_complexity(
            len(operations_used),
            len(tables_used),
            has_aggregation,
            has_join
        )
        
        return {
            "tables": tables_used,
            "operations": operations_used,
            "has_aggregation": has_aggregation,
            "has_join": has_join,
            "complexity": complexity
        }
    
    def _estimate_complexity(
        self,
        operation_count: int,
        table_count: int,
        has_aggregation: bool,
        has_join: bool
    ) -> str:
        """估计SQL复杂度"""
        score = 0
        
        # 基于操作数量
        score += operation_count * 2
        
        # 基于表数量
        if table_count > 3:
            score += 3
        elif table_count > 1:
            score += 1
        
        # 特殊操作
        if has_aggregation:
            score += 1
        if has_join:
            score += 2
        
        # 判断复杂度
        if score <= 2:
            return "简单"
        elif score <= 5:
            return "中等"
        elif score <= 8:
            return "复杂"
        else:
            return "高级"
    
    async def _arun(
        self,
        question: str,
        memory: Dict[str, Any],
        operations: List[str] = None,
        dialect: str = "mysql"
    ) -> Dict[str, Any]:
        """异步执行（当前实现为同步）"""
        return self._run(question, memory, operations, dialect)