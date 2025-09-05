"""
字段分类工具 - 对数据库字段进行语义分类
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


class FieldClassificationInput(BaseModel):
    """字段分类输入 - 无需参数，工具会从记忆中获取数据"""
    pass


class FieldClassification(BaseModel):
    """字段分类结果"""
    field_name: str = Field(description="字段名称")
    category: str = Field(description="字段类别")
    field_type: str = Field(description="具体类型")
    importance: str = Field(description="重要性")
    confidence: float = Field(default=0.0, description="置信度")
    reasoning: Optional[str] = Field(default=None, description="分类理由")


class FieldAnalysisTool(BaseSemanticSQLTool):
    """字段语义分类工具 - 从记忆中获取信息进行分析"""

    name: str = "field_analysis"
    description: str = "对数据库字段进行语义分类，识别字段的业务含义和用途。无需参数，自动从记忆中获取数据"
    args_schema: Type[BaseModel] = FieldClassificationInput

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, 'prompt_manager', PromptManager())

    def _run(self, **kwargs) -> str:
        """执行字段分类"""
        try:
            # 从记忆中获取必要信息
            schema_info = self.get_from_memory("schema_extraction")
            domain_info = self.get_from_memory("domain_analysis")
            
            if not schema_info:
                raise ToolExecutionError(
                    tool_name=self.name,
                    message="无法获取数据库结构信息，请先运行schema_extraction工具",
                    details="需要先提取数据库结构才能进行字段分类"
                )
            
            # 基于规则进行字段分类
            classification_result = self._classify_fields_by_rules(schema_info, domain_info)
            
            # 保存结果到记忆
            self.save_to_memory("field_analysis", classification_result)
            
            return json.dumps(classification_result, ensure_ascii=False)
            
        except Exception as e:
            self.logger.error(f"字段分类失败: {e}")
            raise ToolExecutionError(
                tool_name=self.name,
                message=f"字段分类执行失败: {str(e)}",
                details=str(e)
            )
    
    def _classify_fields_by_rules(self, schema_info: Dict[str, Any], domain_info: Dict[str, Any] = None) -> Dict[str, Any]:
        """基于规则对字段进行分类"""
        tables = schema_info.get("tables", [])
        field_classifications = {}
        
        for table in tables:
            table_name = table.get("name", "")
            columns = table.get("columns", [])
            primary_keys = table.get("primary_key", [])
            
            field_classifications[table_name] = {}
            
            for column in columns:
                col_name = column.get("name", "")
                data_type = column.get("type", "").lower()
                
                # 基于规则的分类逻辑
                category, field_type, importance = self._classify_field(
                    col_name, data_type, col_name in primary_keys
                )
                
                field_classifications[table_name][col_name] = {
                    "category": category,
                    "field_type": field_type,
                    "importance": importance,
                    "confidence": 0.8,
                    "reasoning": f"基于字段名'{col_name}'和数据类型'{data_type}'的规则分类"
                }
        
        return {
            "field_classifications": field_classifications,
            "classification_summary": self._generate_summary(field_classifications)
        }
    
    def _classify_field(self, col_name: str, data_type: str, is_primary: bool) -> tuple:
        """分类单个字段"""
        col_name_lower = col_name.lower()
        
        # 主键和ID字段
        if is_primary or col_name_lower.endswith("_id") or col_name_lower == "id":
            return "identifier", "主键" if is_primary else "外键", "high"
        
        # 时间类型字段
        if any(dt in data_type for dt in ["date", "time", "timestamp"]):
            return "datetime", "时间戳", "medium"
        
        # 数值类型字段
        if any(dt in data_type for dt in ["int", "decimal", "float", "numeric"]):
            if any(kw in col_name_lower for kw in ["amount", "price", "cost", "fee"]):
                return "measure", "金额", "high"
            elif any(kw in col_name_lower for kw in ["count", "num", "qty"]):
                return "measure", "数量", "medium"
            else:
                return "measure", "数值", "medium"
        
        # 文本类型字段
        if any(dt in data_type for dt in ["varchar", "char", "text"]):
            if any(kw in col_name_lower for kw in ["name", "title"]):
                return "text", "名称", "high"
            elif any(kw in col_name_lower for kw in ["status", "state", "type"]):
                return "dimension", "状态", "medium"
            else:
                return "text", "文本", "low"
        
        # 布尔类型字段
        if any(dt in data_type for dt in ["bool", "bit", "tinyint(1)"]):
            return "boolean", "布尔值", "medium"
        
        return "other", "其他", "low"
    
    def _generate_summary(self, field_classifications: Dict[str, Dict[str, Any]]) -> Dict[str, List[str]]:
        """生成分类摘要"""
        summary = {}
        
        for table_name, table_fields in field_classifications.items():
            for field_name, field_info in table_fields.items():
                category = field_info.get("category", "other")
                if category not in summary:
                    summary[category] = []
                summary[category].append(f"{table_name}.{field_name}")
        
        return summary