"""
领域分析工具 - 分析数据库的业务领域
基于 LangChain BaseTool，完全从记忆中获取信息
"""

from typing import Dict, Any, Type, List, Optional
from pydantic import BaseModel, Field
import json
import logging

from models.exceptions import ToolExecutionError
from prompts.manager import PromptManager
from ..base_tool import BaseSemanticSQLTool

logger = logging.getLogger(__name__)


class DomainAnalysisInput(BaseModel):
    """领域分析输入 - 无需参数，工具会从记忆中获取schema_info"""
    pass


class DomainAnalysis(BaseModel):
    """领域分析结果"""
    domain_type: str = Field(description="业务领域类型")
    domain_description: str = Field(description="领域描述")
    confidence: float = Field(default=0.0, description="置信度")
    key_entities: List[str] = Field(default_factory=list, description="关键实体")
    business_characteristics: List[str] = Field(default_factory=list, description="业务特征")
    business_rules: List[str] = Field(default_factory=list, description="业务规则")


class DomainAnalysisTool(BaseSemanticSQLTool):
    """业务领域分析工具 - 从记忆中获取schema信息进行分析"""

    name: str = "domain_analysis"
    description: str = "分析数据库的业务领域，识别主要业务场景和数据特征。无需参数，自动从记忆中获取schema_info"
    args_schema: Type[BaseModel] = DomainAnalysisInput

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, 'prompt_manager', PromptManager())

    def _run(self, **kwargs) -> str:
        """执行领域分析"""
        try:
            # 从记忆中获取schema_info
            schema_info = self.get_from_memory("schema_extraction")
            if not schema_info:
                raise ToolExecutionError(
                    tool_name=self.name,
                    message="无法获取数据库结构信息，请先运行schema_extraction工具",
                    details="需要先提取数据库结构才能进行领域分析"
                )
            
            # 使用LLM进行领域分析（这里Agent会提供LLM调用能力）
            # 简化实现：基于表名和列名进行基础分析
            analysis_result = self._analyze_domain_from_schema(schema_info)
            
            # 保存结果到记忆
            self.save_to_memory("domain_analysis", analysis_result)
            
            return json.dumps(analysis_result, ensure_ascii=False)
            
        except Exception as e:
            self.logger.error(f"领域分析失败: {e}")
            raise ToolExecutionError(
                tool_name=self.name,
                message=f"领域分析执行失败: {str(e)}",
                details=str(e)
            )
    
    def _analyze_domain_from_schema(self, schema_info: Dict[str, Any]) -> Dict[str, Any]:
        """基于数据库结构分析业务领域"""
        tables = schema_info.get("tables", [])
        
        # 基础的域名推断逻辑
        domain_keywords = {
            "电商": ["order", "product", "customer", "payment", "cart"],
            "财务": ["account", "transaction", "payment", "invoice", "billing"],
            "人事": ["employee", "department", "salary", "attendance"],
            "库存": ["inventory", "stock", "warehouse", "supplier"]
        }
        
        detected_domains = []
        for domain, keywords in domain_keywords.items():
            for table in tables:
                table_name = table.get("name", "").lower()
                if any(keyword in table_name for keyword in keywords):
                    detected_domains.append(domain)
                    break
        
        # 确定主要域名
        primary_domain = detected_domains[0] if detected_domains else "通用业务"
        
        return {
            "domain_type": primary_domain,
            "domain_description": f"基于数据库结构分析，该数据库主要用于{primary_domain}系统",
            "confidence": 0.8,
            "key_entities": [table.get("name", "") for table in tables[:5]],
            "business_characteristics": detected_domains,
            "business_rules": [f"{primary_domain}相关的业务逻辑"]
        }