"""
表业务含义分析工具 - 分析每个表的业务职责
基于 LangChain BaseTool，参考table_description_pipeline的实现
"""

from typing import Dict, Any, Type, Optional, List
from pydantic import BaseModel, Field
import json
import logging

from models.exceptions import ToolExecutionError
from prompts.manager import PromptManager
from ..base_tool import BaseSemanticSQLTool

logger = logging.getLogger(__name__)


class TableMeaningInput(BaseModel):
    """表含义分析输入 - 无需参数，工具会从记忆中获取数据"""
    pass


class TableMeaning(BaseModel):
    """表业务含义"""
    table_name: str = Field(description="表名")
    business_purpose: str = Field(description="业务用途")
    entity_type: str = Field(description="实体类型")
    relationships: List[str] = Field(default_factory=list, description="关联关系")


class TableAnalysisTool(BaseSemanticSQLTool):
    """表业务含义分析工具"""
    
    name: str = "table_analysis"
    description: str = "分析每个表的业务职责和含义。无需参数，自动从记忆中获取数据"
    args_schema: Type[BaseModel] = TableMeaningInput
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, 'prompt_manager', PromptManager())
    
    def _run(self, **kwargs) -> str:
        """执行表含义分析"""
        try:
            # 从记忆中获取数据
            schema_info = self.get_from_memory("schema_extraction")
            domain_info = self.get_from_memory("domain_analysis")
            column_meanings = self.get_from_memory("column_meaning_analysis")
            
            if not schema_info:
                raise ToolExecutionError(
                    tool_name=self.name,
                    message="无法获取数据库结构信息，请先运行schema_extraction工具",
                    details="需要先提取数据库结构才能进行表含义分析"
                )
            
            # 基于规则生成表描述
            table_descriptions = self._generate_table_descriptions_by_rules(
                schema_info,
                domain_info,
                column_meanings
            )
            
            # 构建结果
            result = {
                "table_descriptions": table_descriptions,
                "total_tables": len(table_descriptions),
                "domain_type": domain_info.get("domain_type", "未知") if domain_info else "未知"
            }
            
            # 保存到记忆
            self.save_to_memory("table_meaning_analysis", result)
            
            return json.dumps(result, ensure_ascii=False)
            
        except Exception as e:
            self.logger.error(f"表含义分析失败: {e}")
            raise ToolExecutionError(
                tool_name=self.name,
                message=f"表含义分析执行失败: {str(e)}",
                details=str(e)
            )
    
    def _generate_table_descriptions_by_rules(
        self,
        schema_info: Dict[str, Any],
        domain_info: Dict[str, Any],
        column_meanings: Dict[str, Any]
    ) -> Dict[str, str]:
        """基于规则生成表描述"""
        table_descriptions = {}
        tables = schema_info.get("tables", {})
        
        domain_type = domain_info.get("domain_type", "未知") if domain_info else "未知"
        
        for table_name, table_info in tables.items():
            # 基于表名和列信息推断业务含义
            description = self._infer_table_purpose(
                table_name, 
                table_info, 
                domain_type
            )
            table_descriptions[table_name] = description
        
        return table_descriptions
    
    def _infer_table_purpose(
        self,
        table_name: str,
        table_info: Dict[str, Any],
        domain_type: str
    ) -> str:
        """基于规则推断表的业务用途"""
        table_name_lower = table_name.lower()
        columns = table_info.get("columns", {})
        
        # 基于表名推断
        if any(keyword in table_name_lower for keyword in ["user", "customer", "client", "member"]):
            return f"{table_name}表：存储用户/客户基础信息，包含用户身份标识和相关属性"
        elif any(keyword in table_name_lower for keyword in ["order", "transaction", "payment"]):
            return f"{table_name}表：记录交易订单信息，包含订单状态、金额等业务数据"
        elif any(keyword in table_name_lower for keyword in ["product", "item", "goods", "commodity"]):
            return f"{table_name}表：管理商品/产品信息，包含商品属性和分类数据"
        elif any(keyword in table_name_lower for keyword in ["log", "audit", "history"]):
            return f"{table_name}表：记录系统日志或历史数据，用于审计和追踪"
        elif any(keyword in table_name_lower for keyword in ["config", "setting", "param"]):
            return f"{table_name}表：存储系统配置参数，管理应用设置信息"
        elif table_name_lower.endswith("_info"):
            base_name = table_name_lower[:-5]
            return f"{table_name}表：存储{base_name}相关的详细信息数据"
        elif table_name_lower.endswith("_detail"):
            base_name = table_name_lower[:-7]
            return f"{table_name}表：记录{base_name}的详细明细数据"
        
        # 基于列名推断
        col_names = [col.lower() for col in columns.keys()]
        if any("name" in col for col in col_names):
            if any("price" in col or "amount" in col for col in col_names):
                return f"{table_name}表：业务实体表，包含名称和价格信息，可能是商品或服务相关"
            else:
                return f"{table_name}表：基础信息表，主要存储名称等标识信息"
        elif any("time" in col or "date" in col for col in col_names):
            return f"{table_name}表：时间相关的业务数据表，记录事件发生的时间信息"
        
        # 默认描述
        return f"{table_name}表：{domain_type}领域的业务数据表"
    
