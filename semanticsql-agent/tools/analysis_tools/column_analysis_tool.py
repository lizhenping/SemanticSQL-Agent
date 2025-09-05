"""
列业务含义分析工具 - 为每个列生成业务描述
基于 LangChain BaseTool，参考column_description_pipeline的实现
"""

from typing import Dict, Any, Type, List, Optional

from pydantic import BaseModel, Field, ConfigDict
import json
import logging

from models.exceptions import ToolExecutionError
from prompts.manager import PromptManager
from ..base_tool import BaseSemanticSQLTool

logger = logging.getLogger(__name__)


class ColumnMeaningInput(BaseModel):
    """列含义分析输入 - 无需参数，工具会从记忆中获取数据"""
    pass


class ColumnMeaning(BaseModel):
    """列业务含义"""
    column_name: str = Field(description="列名")
    table_name: str = Field(description="表名")
    business_meaning: str = Field(description="业务含义")
    data_type: str = Field(description="数据类型")
    examples: List[str] = Field(default_factory=list, description="示例值")


class ColumnAnalysisTool(BaseSemanticSQLTool):
    """列业务含义分析工具"""
    
    name: str = "column_analysis"
    description: str = "为数据库每个列生成业务含义描述。无需参数，自动从记忆中获取数据"
    args_schema: Type[BaseModel] = ColumnMeaningInput
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, 'prompt_manager', PromptManager())
    
    def _run(self, **kwargs) -> str:
        """执行列含义分析"""
        try:
            # 从记忆中获取数据
            schema_info = self.get_from_memory("schema_extraction")
            domain_info = self.get_from_memory("domain_analysis")
            field_classification = self.get_from_memory("field_analysis")
            
            if not schema_info:
                raise ToolExecutionError(
                    tool_name=self.name,
                    reason="未找到数据库结构信息，请先执行schema_extraction"
                )
            
            # 基于规则生成列描述
            column_descriptions = self._generate_column_descriptions_by_rules(
                schema_info,
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
    
    def _generate_column_descriptions_by_rules(
        self,
        schema_info: Dict[str, Any],
        domain_info: Dict[str, Any],
        field_classification: Dict[str, Any]
    ) -> Dict[str, str]:
        """基于规则生成列描述"""
        column_descriptions = {}
        tables = schema_info.get("tables", {})
        domain_type = domain_info.get("domain_type", "未知") if domain_info else "未知"
        
        # 获取字段分类信息
        field_classifications = {}
        if field_classification:
            field_classifications = field_classification.get("field_classifications", {})
        
        for table_name, table_info in tables.items():
            columns = table_info.get("columns", {})
            sample_data = table_info.get("sample_data", [])
            
            for col_name, col_info in columns.items():
                col_key = f"{table_name}.{col_name}"
                
                # 获取字段分类
                field_class_info = {}
                if table_name in field_classifications:
                    field_class_info = field_classifications[table_name].get(col_name, {})
                
                # 基于规则生成描述
                description = self._infer_column_meaning(
                    col_name, col_info, field_class_info, domain_type, sample_data
                )
                
                column_descriptions[col_key] = description
        
        return column_descriptions
    
    def _infer_column_meaning(
        self,
        col_name: str,
        col_info: Dict[str, Any],
        field_class_info: Dict[str, Any],
        domain_type: str,
        sample_data: List[Dict[str, Any]]
    ) -> str:
        """基于规则推断列的业务含义"""
        col_name_lower = col_name.lower()
        data_type = col_info.get("type", "").lower()
        
        # 优先使用字段分类信息
        if field_class_info:
            category = field_class_info.get("category", "")
            field_type = field_class_info.get("field_type", "")
            if category and field_type:
                return f"{col_name}：{field_type}字段，属于{category}类别，用于{domain_type}业务"
        
        # 基于列名和类型推断
        if col_name_lower in ["id"] or col_name_lower.endswith("_id"):
            if col_name_lower == "id":
                return f"{col_name}：主键标识符，唯一标识该表中的每一条记录"
            else:
                ref_entity = col_name_lower[:-3]
                return f"{col_name}：外键标识符，关联{ref_entity}表的主键"
        
        elif any(keyword in col_name_lower for keyword in ["name", "title"]):
            return f"{col_name}：名称字段，存储易读的标识信息"
        
        elif any(keyword in col_name_lower for keyword in ["time", "date", "created", "updated"]):
            if "created" in col_name_lower:
                return f"{col_name}：创建时间，记录数据创建的时间点"
            elif "updated" in col_name_lower:
                return f"{col_name}：更新时间，记录数据最后修改的时间点"
            else:
                return f"{col_name}：时间字段，记录相关的时间信息"
        
        elif any(keyword in col_name_lower for keyword in ["status", "state", "type"]):
            return f"{col_name}：状态/类型字段，表示数据的当前状态或分类"
        
        elif any(keyword in col_name_lower for keyword in ["amount", "price", "cost", "fee", "money"]):
            return f"{col_name}：金额字段，存储货币数值信息"
        
        elif any(keyword in col_name_lower for keyword in ["count", "num", "qty", "quantity"]):
            return f"{col_name}：数量字段，记录相关的计数信息"
        
        elif any(keyword in col_name_lower for keyword in ["phone", "mobile", "tel"]):
            return f"{col_name}：电话号码字段，存储联系电话信息"
        
        elif "email" in col_name_lower or "mail" in col_name_lower:
            return f"{col_name}：电子邮箱字段，存储邮箱地址信息"
        
        elif "address" in col_name_lower:
            return f"{col_name}：地址字段，存储物理地址信息"
        
        # 基于数据类型推断
        elif any(dt in data_type for dt in ["text", "varchar", "char"]):
            return f"{col_name}：文本字段，存储字符串类型的{domain_type}业务数据"
        
        elif any(dt in data_type for dt in ["int", "decimal", "float", "numeric"]):
            return f"{col_name}：数值字段，存储数字类型的{domain_type}业务数据"
        
        elif any(dt in data_type for dt in ["bool", "bit"]):
            return f"{col_name}：布尔字段，表示是/否状态"
        
        # 默认描述
        return f"{col_name}：{domain_type}领域的业务数据字段"
    
