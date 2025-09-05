"""
SQL生成工具 - 优化版本
拆分长方法，移除过度异常处理，按就近原则组织代码
"""

import re
import json
from typing import Dict, Any, Type, List, Optional
from pydantic import BaseModel, Field, model_validator

from models.base import SQLOperation
from models.exceptions import ToolExecutionError, LLMError
from prompts.manager import PromptManager
from utils.database import DatabaseManager
from ..base_tool import BaseSemanticSQLTool


# ========== 工具内部数据模型（就近原则）==========
class SQLGenerationInput(BaseModel):
    """SQL生成输入参数"""
    question: str = Field(description="自然语言问题")
    scenario: Optional[Dict[str, Any]] = Field(default=None, description="场景信息")
    operations: Optional[List[str]] = Field(default=None, description="建议的SQL操作")
    dialect: str = Field(default="mysql", description="SQL方言")
    
    @model_validator(mode='before')
    @classmethod
    def validate_input(cls, data):
        """处理字符串输入"""
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except:
                data = {"question": data}
        return data


class SQLAnalysisResult(BaseModel):
    """SQL分析结果"""
    tables: List[str]
    operations: List[str] 
    has_aggregation: bool
    has_join: bool
    complexity: str


class GeneratedSQLResult(BaseModel):
    """生成的SQL结果"""
    sql: str
    dialect: str
    tables_used: List[str]
    operations_used: List[str]
    has_aggregation: bool
    has_join: bool
    complexity: str


class SQLGenerationTool(BaseSemanticSQLTool):
    """SQL生成工具 - 优化版本
    
    职责：
    - 根据自然语言问题生成SQL查询
    - 分析SQL复杂度和使用的操作
    - 支持多种SQL方言
    
    设计原则：
    - 单一职责：专注SQL生成
    - 方法拆分：每个方法<30行
    - 类型安全：使用Pydantic模型
    - 简化异常：让异常自然传播
    """
    
    name: str = "sql_generation"
    description: str = "根据自然语言问题生成SQL查询，自动从记忆中获取schema和分析结果"
    args_schema: Type[BaseModel] = SQLGenerationInput
    
    def __init__(self, llm=None, db_manager: DatabaseManager = None, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, 'llm', llm)
        object.__setattr__(self, 'db_manager', db_manager)
        object.__setattr__(self, 'prompt_manager', PromptManager())

    def _run(
        self,
        question: str,
        scenario: Optional[Dict[str, Any]] = None,
        operations: Optional[List[str]] = None,
        dialect: str = "mysql",
        **kwargs
    ) -> str:
        """生成SQL查询 - 主流程"""
        # 获取分析上下文
        context = self._gather_analysis_context()
        
        # 生成SQL
        sql = self._generate_sql(question, context, operations, dialect)
        
        # 分析SQL
        analysis = self._analyze_generated_sql(sql, context["schema_info"])
        
        # 构建结果
        result = self._build_generation_result(sql, dialect, analysis)
        
        # 保存并返回
        self.save_to_memory("sql_generation", result)
        return json.dumps(result, ensure_ascii=False)

    # ========== 上下文收集和处理 ==========
    def _gather_analysis_context(self) -> Dict[str, Any]:
        """收集分析上下文信息"""
        context = {
            "schema_info": self.get_from_memory("schema_extraction"),
            "domain_analysis": self.get_from_memory("domain_analysis"), 
            "field_classification": self.get_from_memory("field_classification"),
            "column_meanings": self.get_from_memory("column_meanings"),
            "table_meanings": self.get_from_memory("table_meanings"),
            "er_relations": self.get_from_memory("er_analysis")
        }
        
        if not context["schema_info"]:
            raise ToolExecutionError(
                tool_name=self.name,
                reason="无法获取数据库结构信息，需要先运行schema_extraction工具"
            )
        
        return context

    def _generate_sql(
        self,
        question: str,
        context: Dict[str, Any],
        operations: Optional[List[str]],
        dialect: str
    ) -> str:
        """生成SQL语句"""
        llm = self._get_llm_instance()
        
        if llm:
            return self._generate_with_llm(question, context, operations, dialect, llm)
        else:
            return self._generate_with_rules(question, context["schema_info"], dialect)

    def _get_llm_instance(self):
        """获取LLM实例"""
        if self.llm:
            return self.llm
        return self.get_from_memory("llm")

    def _generate_with_llm(
        self,
        question: str,
        context: Dict[str, Any],
        operations: Optional[List[str]],
        dialect: str,
        llm
    ) -> str:
        """使用LLM生成SQL"""
        prompt_context = self._build_llm_context(context, operations)
        prompt = self.prompt_manager.get_tool_prompt(
            "sql_generation",
            context=prompt_context,
            dialect=dialect,
            question=question
        )
        
        response = llm.invoke(prompt)
        sql = self._extract_sql_from_response(response.content)
        return self._postprocess_sql(sql, dialect)

    def _build_llm_context(self, context: Dict[str, Any], operations: Optional[List[str]]) -> str:
        """构建LLM上下文字符串"""
        context_parts = []
        
        # 添加领域信息
        if context.get("domain_analysis", {}).get("primary_domain"):
            domain = context["domain_analysis"]["primary_domain"]
            context_parts.append(f"业务领域：{domain}")
        
        # 添加数据库结构
        context_parts.extend(self._build_schema_context(context["schema_info"]))
        
        # 添加字段分类信息
        if context.get("field_classification"):
            context_parts.extend(self._build_field_context(context["field_classification"]))
        
        # 添加操作建议
        if operations:
            context_parts.append(f"建议使用的SQL操作：{', '.join(operations)}")
        
        return "\n".join(context_parts)

    def _build_schema_context(self, schema_info: Dict[str, Any]) -> List[str]:
        """构建数据库结构上下文"""
        context_parts = ["数据库结构："]
        tables = schema_info.get("tables", {})
        
        for table_name, table_info in list(tables.items())[:10]:  # 限制表数量
            context_parts.append(f"\n表：{table_name}")
            
            if table_info.get("comment"):
                context_parts.append(f"  说明：{table_info['comment']}")
            
            # 添加列信息
            columns = table_info.get("columns", [])
            context_parts.append("  列：")
            for col in columns[:15]:  # 限制列数量
                col_desc = f"    - {col.get('name')} ({col.get('type')})"
                if col.get("comment"):
                    col_desc += f" -- {col['comment']}"
                context_parts.append(col_desc)
            
            # 添加主键
            if table_info.get("primary_keys"):
                context_parts.append(f"  主键：{', '.join(table_info['primary_keys'])}")
        
        return context_parts

    def _build_field_context(self, field_classification: Dict[str, Any]) -> List[str]:
        """构建字段分类上下文"""
        context_parts = []
        field_classifications = field_classification.get("field_classifications", {})
        
        if field_classifications:
            context_parts.append("\n重要字段分类：")
            for table, fields in field_classifications.items():
                for field, info in list(fields.items())[:5]:  # 限制字段数量
                    if info.get("business_meaning"):
                        context_parts.append(f"  {table}.{field}: {info['business_meaning']}")
        
        return context_parts

    def _extract_sql_from_response(self, response_content: str) -> str:
        """从LLM响应中提取SQL"""
        sql_match = re.search(r'```sql\s*(.*?)\s*```', response_content, re.DOTALL | re.IGNORECASE)
        if sql_match:
            return sql_match.group(1).strip()
        return response_content.strip()

    def _postprocess_sql(self, sql: str, dialect: str) -> str:
        """后处理SQL语句"""
        # 移除多余空白
        sql = re.sub(r'\s+', ' ', sql).strip()
        
        # 确保以分号结尾
        if not sql.endswith(';'):
            sql += ';'
        
        # MySQL特定处理
        if dialect == "mysql":
            sql = sql.replace('"', '`')
        
        return sql

    def _generate_with_rules(self, question: str, schema_info: Dict[str, Any], dialect: str) -> str:
        """基于规则生成SQL（备用方案）"""
        tables = schema_info.get("tables", {})
        if not tables:
            return "SELECT 1;"
        
        # 选择主表
        main_table = list(tables.keys())[0]
        table_info = tables[main_table]
        columns = [col.get("name") for col in table_info.get("columns", [])]
        
        question_lower = question.lower()
        
        if any(keyword in question_lower for keyword in ["count", "数量", "多少"]):
            return f"SELECT COUNT(*) FROM {main_table};"
        elif any(keyword in question_lower for keyword in ["all", "所有", "全部"]):
            selected_cols = ", ".join(columns[:5]) if columns else "*"
            return f"SELECT {selected_cols} FROM {main_table};"
        else:
            first_col = columns[0] if columns else "*"
            return f"SELECT {first_col} FROM {main_table};"

    # ========== SQL分析和结果构建 ==========
    def _analyze_generated_sql(self, sql: str, schema_info: Dict[str, Any]) -> SQLAnalysisResult:
        """分析生成的SQL"""
        sql_lower = sql.lower()
        
        # 提取使用的表
        tables_used = self._extract_tables_from_sql(sql, schema_info)
        
        # 识别SQL操作
        operations_used = self._identify_sql_operations(sql_lower)
        
        # 检查聚合和连接
        has_aggregation = self._has_aggregation(sql_lower)
        has_join = self._has_join(sql_lower)
        
        # 估计复杂度
        complexity = self._estimate_sql_complexity(len(operations_used), len(tables_used), has_aggregation, has_join)
        
        return SQLAnalysisResult(
            tables=tables_used,
            operations=operations_used,
            has_aggregation=has_aggregation,
            has_join=has_join,
            complexity=complexity
        )

    def _extract_tables_from_sql(self, sql: str, schema_info: Dict[str, Any]) -> List[str]:
        """从SQL中提取使用的表名"""
        tables_used = []
        all_tables = list(schema_info.get("tables", {}).keys())
        
        for table in all_tables:
            table_pattern = rf'\b{re.escape(table)}\b'
            if re.search(table_pattern, sql, re.IGNORECASE):
                tables_used.append(table)
        
        return tables_used

    def _identify_sql_operations(self, sql_lower: str) -> List[str]:
        """识别SQL中使用的操作"""
        operations = []
        
        if 'select' in sql_lower:
            operations.append(SQLOperation.SELECT.value)
        if 'join' in sql_lower:
            operations.append(SQLOperation.JOIN.value)
        if 'group by' in sql_lower:
            operations.append(SQLOperation.GROUP.value)
        if 'with ' in sql_lower and ' as ' in sql_lower:
            operations.append(SQLOperation.CTE.value)
        if 'over(' in sql_lower.replace(' ', ''):
            operations.append(SQLOperation.WINDOW.value)
        if 'union' in sql_lower:
            operations.append(SQLOperation.UNION.value)
        if sql_lower.count('select') > 1:
            operations.append(SQLOperation.SUBQUERY.value)
        
        return operations

    def _has_aggregation(self, sql_lower: str) -> bool:
        """检查是否包含聚合函数"""
        return any(agg in sql_lower for agg in ['count(', 'sum(', 'avg(', 'max(', 'min('])

    def _has_join(self, sql_lower: str) -> bool:
        """检查是否包含JOIN"""
        return 'join' in sql_lower

    def _estimate_sql_complexity(self, operation_count: int, table_count: int, has_aggregation: bool, has_join: bool) -> str:
        """估计SQL复杂度"""
        score = operation_count * 2
        
        if table_count > 3:
            score += 3
        elif table_count > 1:
            score += 1
        
        if has_aggregation:
            score += 1
        if has_join:
            score += 2
        
        if score <= 2:
            return "简单"
        elif score <= 5:
            return "中等"
        elif score <= 8:
            return "复杂"
        else:
            return "高级"

    def _build_generation_result(self, sql: str, dialect: str, analysis: SQLAnalysisResult) -> Dict[str, Any]:
        """构建生成结果"""
        return {
            "sql": sql,
            "dialect": dialect,
            "tables_used": analysis.tables,
            "operations_used": analysis.operations,
            "has_aggregation": analysis.has_aggregation,
            "has_join": analysis.has_join,
            "complexity": analysis.complexity,
            "generation_summary": f"生成了{analysis.complexity}级别的SQL，使用{len(analysis.tables)}个表"
        }

    async def _arun(
        self,
        question: str,
        scenario: Optional[Dict[str, Any]] = None,
        operations: Optional[List[str]] = None,
        dialect: str = "mysql",
        **kwargs
    ) -> str:
        """异步执行（当前实现为同步）"""
        return self._run(question, scenario, operations, dialect, **kwargs)