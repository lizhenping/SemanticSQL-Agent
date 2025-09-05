"""
SQL生成工具 - 根据问题生成SQL查询
基于 LangChain BaseTool
"""

import re
from typing import Dict, Any, Type, List, Optional
from langchain.tools import BaseTool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, ConfigDict, model_validator
import json

from models.base import SQLOperation
from models.exceptions import ToolExecutionError, LLMError
from prompts.manager import PromptManager
from ..base_tool import BaseSemanticSQLTool


class SQLGenerationInput(BaseModel):
    """SQL生成输入（新设计：从记忆中自动读取）"""
    combination_index: int = Field(default=0, description="要处理的场景组合索引")
    
    @model_validator(mode='before')
    @classmethod
    def validate_input(cls, data):
        """处理字符串输入"""
        if isinstance(data, str):
            import json
            try:
                data = json.loads(data)
            except:
                data = {}
        return data


class GeneratedSQL(BaseModel):
    """生成的SQL查询"""
    sql: str = Field(description="SQL语句")
    dialect: str = Field(default="mysql", description="SQL方言")
    tables_used: List[str] = Field(description="使用的表")
    operations_used: List[str] = Field(description="使用的操作")
    has_aggregation: bool = Field(description="是否包含聚合")
    has_join: bool = Field(default=False, description="是否包含JOIN")
    complexity: str = Field(default="medium", description="复杂度")


class SQLGenerationTool(BaseSemanticSQLTool):
    """SQL生成工具 - 从记忆中获取信息并生成SQL"""
    
    name: str = "sql_generation"
    description: str = "根据自然语言问题生成SQL查询。自动从记忆中获取schema和分析结果"
    args_schema: Type[BaseModel] = SQLGenerationInput
    
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, 'prompt_manager', PromptManager())
    
    def _run(
        self,
        question: str,
        scenario: Optional[Dict[str, Any]] = None,
        memory: Optional[Dict[str, Any]] = None,
        operations: Optional[List[str]] = None,
        dialect: str = "mysql"
    ,
        **kwargs  # 接受额外的参数如 verbose
    ) -> Dict[str, Any]:
        """生成SQL查询"""
        try:
            # 从记忆中获取所需信息
            schema_info = self.get_from_memory("schema_extraction")
            domain_analysis = self.get_from_memory("domain_analysis")
            table_meanings = self.get_from_memory("table_meaning_analysis")
            column_meanings = self.get_from_memory("column_meaning_analysis")
            er_relations = self.get_from_memory("er_analysis")
            field_classification = self.get_from_memory("field_analysis")
            
            if not schema_info:
                raise ToolExecutionError(
                    tool_name=self.name,
                    message="无法获取数据库结构信息",
                    details="需要先运行schema_extraction工具"
                )
            
            # 从记忆中获取LLM（如果可用）
            llm = self.get_from_memory("llm")
            
            if llm:
                # 使用LLM生成SQL
                context = self._build_context(
                    schema_info, domain_analysis, field_classification
                )
                sql = self._generate_sql_with_llm(question, context, dialect)
            else:
                # 使用规则生成SQL（简化版本）
                sql = self._generate_sql_by_rules(question, schema_info, dialect)
            
            # 后处理
            sql = self._postprocess_sql(sql, dialect)
            
            # 分析SQL
            analysis = self._analyze_sql(sql, schema_info)
            
            # 构建结果
            result = {
                "sql": sql,
                "dialect": dialect,
                "tables_used": analysis["tables"],
                "operations_used": analysis["operations"],
                "has_aggregation": analysis["has_aggregation"],
                "has_join": analysis["has_join"],
                "complexity": analysis["complexity"]
            }
            
            # 保存生成的SQL到记忆
            self.save_to_memory("current_sql", sql)
            self.save_to_memory("current_question", question)
            self.save_to_memory("sql_generation_result", result)
            
            return json.dumps(result, ensure_ascii=False)
            
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
    
    def _generate_sql_by_rules(self, question: str, schema_info: Dict[str, Any], dialect: str) -> str:
        """基于简单规则生成SQL（当LLM不可用时的备用方案）"""
        question_lower = question.lower()
        tables = schema_info.get("tables", {})
        
        if not tables:
            return "SELECT 1;"
        
        # 选择主表（通常选择第一个表）
        main_table = list(tables.keys())[0]
        table_info = tables[main_table]
        columns = list(table_info.get("columns", {}).keys())
        
        # 基本SELECT语句
        if "count" in question_lower or "数量" in question_lower or "多少" in question_lower:
            sql = f"SELECT COUNT(*) FROM {main_table};"
        elif "all" in question_lower or "所有" in question_lower or "全部" in question_lower:
            if len(columns) > 5:
                # 如果列太多，只选择前5列
                selected_cols = ", ".join(columns[:5])
            else:
                selected_cols = ", ".join(columns) if columns else "*"
            sql = f"SELECT {selected_cols} FROM {main_table};"
        else:
            # 默认查询
            if columns:
                sql = f"SELECT {columns[0]} FROM {main_table};"
            else:
                sql = f"SELECT * FROM {main_table};"
        
        return sql
    
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