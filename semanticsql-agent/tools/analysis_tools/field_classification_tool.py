"""
字段分类工具 - 对数据库字段进行语义分类
基于 LangChain BaseTool，使用LLM进行智能分类
"""

from typing import Dict, Any, Type
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
import json

from models.exceptions import ToolExecutionError
from prompts.manager import PromptManager
from .base_analysis_tool import BaseAnalysisTool


class FieldClassificationInput(BaseModel):
    """字段分类输入"""
    schema_info: Dict[str, Any] = Field(default_factory=dict, description="数据库结构信息")
    domain_info: Dict[str, Any] = Field(default_factory=dict, description="业务领域信息")


class FieldClassificationTool(BaseAnalysisTool):
    """字段语义分类工具 - 使用LLM进行智能分类"""
    
    name: str = "field_classification"
    description: str = "使用LLM对数据库字段进行语义分类，识别字段的业务含义和用途"
    args_schema: Type[BaseModel] = FieldClassificationInput
    
    def __init__(self, llm: ChatOpenAI, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, 'llm', llm)
        object.__setattr__(self, 'prompt_manager', PromptManager())
    
    def _run(self, schema_info: Dict[str, Any] = None, domain_info: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行字段分类"""
        try:
            # 从参数或memory获取数据
            schema_info = schema_info or self.get_schema_info()
            domain_info = domain_info or self.get_domain_info()
            
            if not schema_info:
                raise ToolExecutionError(
                    tool_name=self.name,
                    reason="未找到数据库结构信息，请先执行schema_extraction"
                )
            
            # 准备提示词参数
            tables = schema_info.get("tables", {})
            
            # 使用LLM进行分类
            prompt = self.prompt_manager.get_analysis_prompt(
                "field_classification",
                tables=tables,
                domain_info=domain_info
            )
            
            response = self.llm.invoke(prompt)
            
            # 解析LLM响应
            try:
                result = json.loads(response.content)
            except json.JSONDecodeError:
                # 尝试提取JSON部分
                import re
                json_match = re.search(r'\{[\s\S]*\}', response.content)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    raise ToolExecutionError(
                        tool_name=self.name,
                        reason="LLM返回的不是有效的JSON格式"
                    )
            
            # 添加分类统计
            result["classification_summary"] = self._generate_summary(
                result.get("field_classifications", {})
            )
            
            # 保存到记忆
            self.save_to_memory("field_classification", result)
            
            return result
            
        except Exception as e:
            raise ToolExecutionError(
                tool_name=self.name,
                reason=f"字段分类失败: {str(e)}"
            )
    
    def _generate_summary(self, classifications: Dict[str, Dict[str, Any]]) -> Dict[str, list]:
        """生成分类统计摘要"""
        summary = {
            "identifier": [],
            "measure": [],
            "dimension": [],
            "datetime": [],
            "text": [],
            "boolean": [],
            "other": []
        }
        
        for table_name, table_fields in classifications.items():
            for field_name, field_info in table_fields.items():
                category = field_info.get("category", "other")
                if category in summary:
                    summary[category].append(f"{table_name}.{field_name}")
        
        return summary