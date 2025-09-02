"""
领域分析工具 - 分析数据库的业务领域
基于 LangChain BaseTool，使用LLM进行智能分析
"""

from typing import Dict, Any, Type, Union
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

            # 准备分析数据
            tables = schema_info.get("tables", {})
            analysis_data = self._prepare_analysis_data(tables)

            # 使用LLM进行分析
            analysis_result = self._analyze_with_llm(schema_info, analysis_data)

            # 保存到记忆
            self.save_to_memory("domain_analysis", analysis_result)

            # 返回JSON字符串
            return json.dumps(analysis_result, ensure_ascii=False, indent=2)

        except Exception as e:
            raise ToolExecutionError(
                tool_name=self.name, reason=f"领域分析失败: {str(e)}"
            )

    def _prepare_analysis_data(self, tables: Dict[str, Any]) -> Dict[str, Any]:
        """准备分析数据"""
        # 统计信息
        stats = {
            "table_count": len(tables),
            "total_columns": sum(len(t.get("columns", {})) for t in tables.values()),
            "total_rows": sum(t.get("row_count", 0) for t in tables.values()),
        }

        # 提取关键表（行数最多的前10个表）
        key_tables = sorted(
            tables.items(),
            key=lambda x: x[1].get("row_count", 0),
            reverse=True
        )[:10]

        return {
            "stats": stats,
            "key_tables": [{"name": name, "info": info} for name, info in key_tables]
        }

    def _analyze_with_llm(
        self,
        schema_info: Dict[str, Any],
        analysis_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """使用LLM进行领域分析"""
        if not self.llm:
            raise ToolExecutionError(
                tool_name=self.name, reason="LLM实例未提供"
            )

        # 准备提示词参数
        prompt_params = {
            "database_name": schema_info.get("database_name", "unknown"),
            "table_count": analysis_data["stats"]["table_count"],
            "total_columns": analysis_data["stats"]["total_columns"],
            "key_tables": analysis_data["key_tables"],
        }

        # 渲染提示词
        prompt = self.prompt_manager.get_analysis_prompt(
            "domain_analysis", **prompt_params
        )

        # 调用LLM
        llm_response = self.llm.invoke(prompt).content

        if not llm_response:
            raise ToolExecutionError(
                tool_name=self.name,
                reason="LLM返回空响应"
            )

        # 解析LLM响应
        try:
            result = self._parse_llm_response(llm_response)
        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}")
            # 返回基础结果
            result = {
                "primary_domain": "未知",
                "characteristics": [],
                "entities": [],
                "business_processes": [],
                "raw_analysis": llm_response
            }

        # 添加统计信息
        result.update(analysis_data["stats"])

        return result

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """解析LLM响应"""
        # 尝试提取JSON
        try:
            # 先尝试直接解析
            return json.loads(response)
        except json.JSONDecodeError:
            # 尝试提取JSON部分
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
        
        # 如果无法解析JSON，进行文本解析
        result = {
            "primary_domain": "",
            "characteristics": [],
            "entities": [],
            "business_processes": []
        }

        # 简单的文本解析
        lines = response.split('\n')
        for line in lines:
            line = line.strip()
            if "领域" in line or "domain" in line.lower():
                result["primary_domain"] = line.split(":")[-1].strip() if ":" in line else line
            elif "特征" in line or "特点" in line:
                result["characteristics"].append(line)
            elif "实体" in line or "entity" in line.lower():
                result["entities"].append(line)
            elif "流程" in line or "process" in line.lower():
                result["business_processes"].append(line)

        return result