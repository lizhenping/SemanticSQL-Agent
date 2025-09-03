"""
领域分析工具 - 分析数据库的业务领域
基于 LangChain BaseTool，参考initial_domain_analysis_pipeline的实现
"""

from typing import Dict, Any, Type, Union, List
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
import json
import logging

from models.exceptions import ToolExecutionError
from prompts.manager import PromptManager
from .base_analysis_tool import BaseAnalysisTool

logger = logging.getLogger(__name__)


class DomainAnalysisInput(BaseModel):
    """领域分析输入"""
    input: Union[Dict[str, Any], str] = Field(
        default={}, 
        description="输入数据，包含schema_info等"
    )


class DomainAnalysisTool(BaseAnalysisTool):
    """业务领域分析工具 - 使用LLM驱动的分析"""

    name: str = "domain_analysis"
    description: str = "使用LLM分析数据库的业务领域，识别主要业务场景和数据特征"
    args_schema: Type[BaseModel] = DomainAnalysisInput

    def __init__(self, llm: ChatOpenAI, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, "prompt_manager", PromptManager())
        object.__setattr__(self, "llm", llm)

    def _run(self, input: Union[Dict[str, Any], str] = None, **kwargs) -> str:
        """执行LLM驱动的领域分析"""
        try:
            # 获取schema_info
            schema_info = self.get_schema_info()
            if not schema_info:
                raise ToolExecutionError(
                    tool_name=self.name,
                    reason="未找到数据库结构信息，请先执行schema_extraction",
                )

            # 1. 格式化数据库DDL（参考FormatDatabaseDDLStep）
            database_ddl = self._format_database_ddl(schema_info)
            
            # 2. 收集字段统计（参考CollectFieldStatisticsStep）
            field_statistics = self._collect_field_statistics(schema_info)
            
            # 3. 使用LLM生成领域描述（参考GenerateDomainDescriptionStep）
            domain_knowledge = self._generate_domain_description(
                database_ddl, 
                field_statistics,
                schema_info.get("database_name", "unknown")
            )

            # 保存到记忆
            self.save_to_memory("domain_analysis", domain_knowledge)

            # 返回字典格式
            return domain_knowledge

        except Exception as e:
            raise ToolExecutionError(
                tool_name=self.name, reason=f"领域分析失败: {str(e)}"
            )

    def _format_database_ddl(self, schema_info: Dict[str, Any]) -> str:
        """格式化数据库DDL"""
        ddl_lines = []
        tables = schema_info.get("tables", {})
        
        for table_name, table_info in tables.items():
            # 表定义开始
            ddl_lines.append(f"CREATE TABLE `{table_name}` (")
            
            # 列定义
            columns = table_info.get("columns", {})
            column_defs = []
            primary_keys = table_info.get("primary_key", [])
            
            for col_name, col_info in columns.items():
                col_def = f"  `{col_name}` {col_info['type']}"
                if not col_info.get("nullable", True):
                    col_def += " NOT NULL"
                if col_info.get("default"):
                    col_def += f" DEFAULT {col_info['default']}"
                column_defs.append(col_def)
            
            # 主键定义
            if primary_keys:
                pk_def = f"  PRIMARY KEY ({', '.join([f'`{pk}`' for pk in primary_keys])})"
                column_defs.append(pk_def)
            
            ddl_lines.append(",\n".join(column_defs))
            ddl_lines.append(");")
            ddl_lines.append("")  # 空行分隔
        
        return "\n".join(ddl_lines)

    def _collect_field_statistics(self, schema_info: Dict[str, Any]) -> Dict[str, Any]:
        """收集字段统计信息"""
        type_stats = {}
        pattern_stats = {
            'id_fields': [],
            'date_fields': [],
            'status_fields': [],
            'amount_fields': [],
            'count_fields': []
        }
        
        tables = schema_info.get("tables", {})
        
        for table_name, table_info in tables.items():
            columns = table_info.get("columns", {})
            primary_keys = table_info.get("primary_key", [])
            
            for col_name, col_info in columns.items():
                # 类型统计
                data_type = col_info['type'].upper().split('(')[0]
                type_stats[data_type] = type_stats.get(data_type, 0) + 1
                
                # 模式统计
                col_name_lower = col_name.lower()
                field_key = f"{table_name}.{col_name}"
                
                # ID字段
                if col_name in primary_keys or col_name_lower.endswith('_id') or col_name_lower == 'id':
                    pattern_stats['id_fields'].append(field_key)
                
                # 日期时间字段
                if any(kw in col_name_lower for kw in ['date', 'time', 'created', 'updated']):
                    pattern_stats['date_fields'].append(field_key)
                
                # 状态字段
                if any(kw in col_name_lower for kw in ['status', 'state', 'type']):
                    pattern_stats['status_fields'].append(field_key)
                
                # 金额字段
                if any(kw in col_name_lower for kw in ['amount', 'price', 'cost', 'fee']):
                    pattern_stats['amount_fields'].append(field_key)
                
                # 计数字段
                if any(kw in col_name_lower for kw in ['count', 'num', 'qty', 'quantity']):
                    pattern_stats['count_fields'].append(field_key)
        
        return {
            'type_distribution': type_stats,
            'patterns': {k: len(v) for k, v in pattern_stats.items()},
            'pattern_examples': {k: v[:3] for k, v in pattern_stats.items()}
        }

    def _generate_domain_description(
        self, 
        database_ddl: str, 
        field_statistics: Dict[str, Any],
        database_name: str
    ) -> Dict[str, Any]:
        """使用LLM生成领域描述"""
        # 准备提示词数据，包含完整的统计信息
        prompt_data = {
            'database_name': database_name,
            'database_ddl': database_ddl,
            'type_distribution': field_statistics['type_distribution'],
            'field_patterns': field_statistics['patterns'],
            'pattern_examples': field_statistics.get('pattern_examples', {}),
            'total_tables': database_ddl.count('CREATE TABLE'),
            'total_fields': sum(field_statistics['type_distribution'].values())
        }
        
        # 使用结构化提示词
        prompt = self.prompt_manager.get_analysis_prompt(
            "initial_domain_analysis", **prompt_data
        )
        
        # 调用LLM
        response = self.llm.invoke(prompt)
        
        # 解析响应
        return self._parse_domain_response(response.content)

    def _parse_domain_response(self, response: str) -> Dict[str, Any]:
        """解析LLM响应为结构化的领域知识"""
        try:
            # 尝试直接解析JSON
            return json.loads(response)
        except json.JSONDecodeError:
            # 如果不是JSON，进行结构化提取
            import re
            
            result = {
                "domain_type": "",
                "domain_description": "",
                "key_entities": [],
                "business_rules": [],
                "data_characteristics": []
            }
            
            # 提取领域类型
            domain_match = re.search(r'领域类型[：:]\s*(.+)', response)
            if domain_match:
                result["domain_type"] = domain_match.group(1).strip()
            
            # 提取实体
            entities_match = re.search(r'核心实体[：:]\s*(.+)', response)
            if entities_match:
                entities_text = entities_match.group(1)
                result["key_entities"] = [e.strip() for e in re.split(r'[,，、]', entities_text)]
            
            # 提取业务规则
            rules_section = re.search(r'业务规则[：:]([\s\S]+?)(?=\n\n|\Z)', response)
            if rules_section:
                rules_text = rules_section.group(1)
                result["business_rules"] = [
                    line.strip() for line in rules_text.split('\n') 
                    if line.strip() and line.strip()[0] in '•·-*'
                ]
            
            # 如果没有提取到任何内容，使用整个响应作为描述
            if not any(result.values()):
                result["domain_description"] = response
                result["domain_type"] = "未知"
            
            return result