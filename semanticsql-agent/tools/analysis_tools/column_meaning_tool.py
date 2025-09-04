"""
列业务含义分析工具 - 为每个列生成业务描述
基于 LangChain BaseTool，参考column_description_pipeline的实现
"""

from typing import Dict, Any, Type, List, Optional
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, ConfigDict
import json
import logging

from models.exceptions import ToolExecutionError
from prompts.manager import PromptManager
from .base_analysis_tool import BaseAnalysisTool

logger = logging.getLogger(__name__)


class ColumnMeaningInput(BaseModel):
    """列含义分析输入 - 无需参数，工具会从记忆中获取数据"""
    pass


class ColumnMeaningTool(BaseAnalysisTool):
    """列业务含义分析工具"""
    
    name: str = "column_meaning_analysis"
    description: str = "使用LLM为数据库每个列生成业务含义描述。无需参数，自动从记忆中获取数据"
    args_schema: Type[BaseModel] = ColumnMeaningInput
    
    # 定义必需的字段
    llm: Optional[ChatOpenAI] = Field(default=None, exclude=True)
    prompt_manager: Optional[PromptManager] = Field(default=None, exclude=True)
    
    # Pydantic v2配置
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    def __init__(self, llm: ChatOpenAI, **kwargs):
        super().__init__(**kwargs)
        self.llm = llm
        self.prompt_manager = PromptManager()
    
    def _run(
        self,
        schema_info: Dict[str, Any] = None,
        domain_info: Dict[str, Any] = None,
        field_classification: Dict[str, Any] = None
    ,
        **kwargs  # 接受额外的参数如 verbose
    ) -> Dict[str, Any]:
        """执行列含义分析"""
        try:
            # 从参数或memory获取数据
            schema_info = schema_info or self.get_schema_info()
            domain_info = domain_info or self.get_domain_info()
            field_classification = field_classification or self.get_field_classification()
            
            if not schema_info:
                raise ToolExecutionError(
                    tool_name=self.name,
                    reason="未找到数据库结构信息，请先执行schema_extraction"
                )
            
            # 1. 格式化表DDL（参考FormatTableDDLStep）
            table_ddls = self._format_table_ddls(schema_info)
            
            # 2. 收集列样例数据（参考CollectColumnExamplesStep）
            field_examples = self._collect_column_examples(schema_info)
            
            # 3. 批量生成列描述（参考GenerateColumnDescriptionsStep）
            column_descriptions = self._generate_column_descriptions(
                table_ddls,
                field_examples,
                domain_info,
                field_classification
            )
            
            # 构建结果
            result = {
                "column_descriptions": column_descriptions,
                "total_columns": len(column_descriptions),
                "tables_processed": len(set(k.split('.')[0] for k in column_descriptions.keys()))
            }
            
            # 保存到记忆
            self.save_to_memory("column_meaning_analysis", result)
            
            return result
            
        except Exception as e:
            raise ToolExecutionError(
                tool_name=self.name,
                reason=f"列含义分析失败: {str(e)}"
            )
    
    def _format_table_ddls(self, schema_info: Dict[str, Any]) -> Dict[str, str]:
        """格式化每个表的DDL"""
        table_ddls = {}
        tables = schema_info.get("tables", {})
        
        for table_name, table_info in tables.items():
            ddl_lines = [f"CREATE TABLE `{table_name}` ("]
            
            # 列定义
            columns = table_info.get("columns", {})
            column_defs = []
            
            for col_name, col_info in columns.items():
                col_def = f"  `{col_name}` {col_info['type']}"
                if not col_info.get("nullable", True):
                    col_def += " NOT NULL"
                if col_info.get("default"):
                    col_def += f" DEFAULT {col_info['default']}"
                if col_info.get("comment"):
                    col_def += f" COMMENT '{col_info['comment']}'"
                column_defs.append(col_def)
            
            # 主键
            primary_keys = table_info.get("primary_key", [])
            if primary_keys:
                pk_def = f"  PRIMARY KEY ({', '.join([f'`{pk}`' for pk in primary_keys])})"
                column_defs.append(pk_def)
            
            ddl_lines.extend([f"{cd}," if i < len(column_defs) - 1 else cd 
                            for i, cd in enumerate(column_defs)])
            ddl_lines.append(");")
            
            table_ddls[table_name] = "\n".join(ddl_lines)
        
        return table_ddls
    
    def _collect_column_examples(self, schema_info: Dict[str, Any]) -> Dict[str, List[Any]]:
        """收集列的样例数据"""
        field_examples = {}
        tables = schema_info.get("tables", {})
        
        for table_name, table_info in tables.items():
            # 从sample_data中提取每列的样例
            sample_data = table_info.get("sample_data", [])
            
            if sample_data:
                columns = table_info.get("columns", {})
                for col_name in columns:
                    field_key = f"{table_name}.{col_name}"
                    # 提取该列的所有样例值
                    examples = []
                    for row in sample_data:
                        if col_name in row:
                            value = row[col_name]
                            if value is not None and value not in examples:
                                examples.append(value)
                    
                    field_examples[field_key] = examples[:5]  # 最多保留5个样例
        
        return field_examples
    
    def _generate_column_descriptions(
        self,
        table_ddls: Dict[str, str],
        field_examples: Dict[str, List[Any]],
        domain_info: Dict[str, Any],
        field_classification: Dict[str, Any]
    ) -> Dict[str, str]:
        """批量生成列描述"""
        column_descriptions = {}
        
        # 按表批量处理
        for table_name, table_ddl in table_ddls.items():
            # 准备该表的列信息
            table_columns = []
            for field_key, examples in field_examples.items():
                if field_key.startswith(f"{table_name}."):
                    col_name = field_key.split('.', 1)[1]
                    
                    # 获取字段分类信息
                    field_class = {}
                    if field_classification:
                        classifications = field_classification.get("field_classifications", {})
                        table_fields = classifications.get(table_name, {})
                        field_class = table_fields.get(col_name, {})
                    
                    table_columns.append({
                        'name': col_name,
                        'examples': examples,
                        'classification': field_class
                    })
            
            if table_columns:
                # 使用LLM批量生成该表所有列的描述
                descriptions = self._generate_table_column_descriptions(
                    table_name,
                    table_ddl,
                    table_columns,
                    domain_info
                )
                
                # 更新结果
                for col_name, desc in descriptions.items():
                    column_descriptions[f"{table_name}.{col_name}"] = desc
        
        return column_descriptions
    
    def _generate_table_column_descriptions(
        self,
        table_name: str,
        table_ddl: str,
        columns: List[Dict[str, Any]],
        domain_info: Dict[str, Any]
    ) -> Dict[str, str]:
        """为一个表的所有列生成描述"""
        # 准备提示词数据，包含所有前面步骤的信息
        prompt_data = {
            'table_name': table_name,
            'table_ddl': table_ddl,
            'columns': columns,
            'domain_type': domain_info.get('domain_type', '未知'),
            'domain_description': domain_info.get('domain_description', ''),
            'key_entities': domain_info.get('key_entities', []),
            'business_characteristics': domain_info.get('business_characteristics', [])
        }
        
        # 渲染提示词
        prompt = self.prompt_manager.get_analysis_prompt(
            "column_description", **prompt_data
        )
        
        # 调用LLM
        response = self.llm.invoke(prompt)
        
        # 解析响应
        return self._parse_descriptions_response(response.content, table_name, columns)
    
    def _parse_descriptions_response(
        self, 
        response: str, 
        table_name: str,
        columns: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """解析LLM生成的列描述"""
        descriptions = {}
        
        try:
            # 尝试解析JSON响应
            result = json.loads(response)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass
        
        # 文本解析
        lines = response.split('\n')
        current_col = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 查找列名
            for col in columns:
                col_name = col['name']
                if col_name in line and ':' in line:
                    current_col = col_name
                    # 提取描述
                    desc = line.split(':', 1)[1].strip()
                    descriptions[col_name] = desc
                    break
        
        # 确保所有列都有描述
        for col in columns:
            if col['name'] not in descriptions:
                descriptions[col['name']] = f"{col['name']}字段"
        
        return descriptions