"""
字段分类工具 - 对数据库字段进行语义分类
基于 LangChain BaseTool
"""

from typing import Dict, Any, Type, List
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from models.exceptions import ToolExecutionError


class FieldClassificationInput(BaseModel):
    """字段分类输入"""
    memory: Dict[str, Any] = Field(description="包含数据库分析结果的记忆")


class FieldClassificationTool(BaseTool):
    """字段语义分类工具"""
    
    name: str = "field_classification"
    description: str = "对数据库字段进行语义分类，识别字段的业务含义和用途"
    args_schema: Type[BaseModel] = FieldClassificationInput
    
    def _run(self, memory: Dict[str, Any]) -> Dict[str, Any]:
        """执行字段分类"""
        try:
            # 从记忆中获取必要信息
            db_analysis = memory.get("db_analysis", {})
            schema_info = db_analysis.get("schema_info", {})
            domain_info = db_analysis.get("domain_info", {})
            
            if not schema_info:
                raise ToolExecutionError(
                    tool_name=self.name,
                    reason="未找到数据库结构信息，请先执行schema_extraction"
                )
            
            # 分类结果
            field_classifications = {}
            classification_summary = {
                "identifier": [],
                "temporal": [],
                "numeric": [],
                "status": [],
                "descriptive": [],
                "reference": [],
                "configuration": [],
                "other": []
            }
            
            # 对每个表的字段进行分类
            tables = schema_info.get("tables", {})
            for table_name, table_info in tables.items():
                table_fields = {}
                
                for column in table_info.get("columns", []):
                    column_name = column["name"]
                    column_type = column["type"]
                    
                    # 分类字段
                    classification = self._classify_field(
                        column_name, column_type, table_name, domain_info
                    )
                    
                    table_fields[column_name] = classification
                    
                    # 添加到分类汇总
                    category = classification["category"]
                    classification_summary[category].append(
                        f"{table_name}.{column_name}"
                    )
                
                field_classifications[table_name] = table_fields
            
            # 生成分类洞察
            insights = self._generate_classification_insights(
                field_classifications, classification_summary
            )
            
            return {
                "field_classifications": field_classifications,
                "classification_summary": classification_summary,
                "insights": insights,
                "total_fields": sum(len(fields) for fields in classification_summary.values())
            }
            
        except Exception as e:
            raise ToolExecutionError(
                tool_name=self.name,
                reason=f"字段分类失败: {str(e)}"
            )
    
    def _classify_field(
        self, 
        field_name: str, 
        field_type: str,
        table_name: str,
        domain_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """对单个字段进行分类"""
        field_lower = field_name.lower()
        type_lower = field_type.lower()
        
        classification = {
            "field_name": field_name,
            "field_type": field_type,
            "category": "other",
            "sub_category": "",
            "business_meaning": "",
            "is_nullable": True,
            "is_key": False,
            "common_patterns": []
        }
        
        # 标识符字段
        if (field_lower == "id" or 
            field_lower.endswith("_id") or 
            field_lower in ["uuid", "guid", "code", "no", "number"]):
            classification["category"] = "identifier"
            
            if field_lower == "id" or field_lower == f"{table_name}_id":
                classification["sub_category"] = "primary_key"
                classification["is_key"] = True
                classification["business_meaning"] = "主键标识"
            elif field_lower.endswith("_id"):
                classification["sub_category"] = "foreign_key"
                classification["is_key"] = True
                classification["business_meaning"] = f"关联{field_lower[:-3]}表"
            else:
                classification["sub_category"] = "business_key"
                classification["business_meaning"] = "业务编号"
        
        # 时间字段
        elif any(time_word in field_lower for time_word in [
            "time", "date", "created", "updated", "modified", "expired", "start", "end"
        ]):
            classification["category"] = "temporal"
            
            if "created" in field_lower:
                classification["sub_category"] = "creation_time"
                classification["business_meaning"] = "创建时间"
            elif "updated" in field_lower or "modified" in field_lower:
                classification["sub_category"] = "update_time"
                classification["business_meaning"] = "更新时间"
            elif "expired" in field_lower:
                classification["sub_category"] = "expiry_time"
                classification["business_meaning"] = "过期时间"
            else:
                classification["sub_category"] = "general_time"
                classification["business_meaning"] = "时间字段"
        
        # 数值字段
        elif (any(num_word in field_lower for num_word in [
            "amount", "price", "cost", "total", "count", "quantity", "num", "rate", "ratio"
        ]) or any(num_type in type_lower for num_type in ["int", "decimal", "float", "double"])):
            classification["category"] = "numeric"
            
            if any(money in field_lower for money in ["price", "cost", "amount", "fee"]):
                classification["sub_category"] = "monetary"
                classification["business_meaning"] = "金额"
            elif any(qty in field_lower for qty in ["count", "quantity", "num"]):
                classification["sub_category"] = "quantity"
                classification["business_meaning"] = "数量"
            elif "rate" in field_lower or "ratio" in field_lower:
                classification["sub_category"] = "percentage"
                classification["business_meaning"] = "比率"
            else:
                classification["sub_category"] = "measure"
                classification["business_meaning"] = "度量值"
        
        # 状态字段
        elif any(status_word in field_lower for status_word in [
            "status", "state", "flag", "is_", "has_", "can_", "enable"
        ]):
            classification["category"] = "status"
            
            if field_lower.startswith("is_"):
                classification["sub_category"] = "boolean_flag"
                classification["business_meaning"] = f"是否{field_lower[3:]}"
            elif "status" in field_lower:
                classification["sub_category"] = "status_code"
                classification["business_meaning"] = "状态码"
            else:
                classification["sub_category"] = "flag"
                classification["business_meaning"] = "标志位"
        
        # 描述性字段
        elif any(desc_word in field_lower for desc_word in [
            "name", "title", "description", "desc", "comment", "remark", "note", "content"
        ]) or any(text_type in type_lower for text_type in ["varchar", "text", "char"]):
            classification["category"] = "descriptive"
            
            if "name" in field_lower or "title" in field_lower:
                classification["sub_category"] = "name"
                classification["business_meaning"] = "名称"
            elif any(long_text in field_lower for long_text in ["description", "content", "comment"]):
                classification["sub_category"] = "long_text"
                classification["business_meaning"] = "详细描述"
            else:
                classification["sub_category"] = "short_text"
                classification["business_meaning"] = "文本信息"
        
        # 引用字段（除了ID以外的引用）
        elif any(ref_word in field_lower for ref_word in ["type", "category", "class", "group"]):
            classification["category"] = "reference"
            classification["sub_category"] = "classification"
            classification["business_meaning"] = "分类引用"
        
        # 配置字段
        elif any(config_word in field_lower for config_word in ["config", "setting", "option", "param"]):
            classification["category"] = "configuration"
            classification["sub_category"] = "setting"
            classification["business_meaning"] = "配置项"
        
        # 根据数据类型补充信息
        if "int" in type_lower and classification["category"] == "other":
            classification["category"] = "numeric"
            classification["sub_category"] = "integer"
        elif "json" in type_lower:
            classification["sub_category"] = "structured_data"
            classification["business_meaning"] = "结构化数据"
        
        return classification
    
    def _generate_classification_insights(
        self, 
        classifications: Dict[str, Any],
        summary: Dict[str, List[str]]
    ) -> List[str]:
        """生成分类洞察"""
        insights = []
        
        # 统计各类字段数量
        total_fields = sum(len(fields) for fields in summary.values())
        
        # 主键外键分析
        id_fields = summary["identifier"]
        pk_count = sum(1 for f in id_fields if f.endswith(".id"))
        fk_count = sum(1 for f in id_fields if f.endswith("_id") and not f.endswith(".id"))
        
        if fk_count > 0:
            insights.append(f"发现{fk_count}个外键字段，数据库具有关联关系")
        
        # 时间字段分析
        temporal_fields = summary["temporal"]
        if len(temporal_fields) > total_fields * 0.1:
            insights.append("系统包含大量时间字段，适合时序分析查询")
        
        # 数值字段分析
        numeric_fields = summary["numeric"]
        if len(numeric_fields) > total_fields * 0.2:
            insights.append("系统包含较多数值字段，适合统计分析查询")
        
        # 状态字段分析
        status_fields = summary["status"]
        if len(status_fields) > 0:
            insights.append(f"发现{len(status_fields)}个状态字段，可生成状态过滤查询")
        
        # 文本字段分析
        desc_fields = summary["descriptive"]
        long_text_count = sum(1 for f in desc_fields if "description" in f or "content" in f)
        if long_text_count > 0:
            insights.append("包含长文本字段，可能需要全文搜索功能")
        
        # 数据完整性
        if pk_count == len(classifications):
            insights.append("所有表都有主键，数据完整性良好")
        
        return insights
    
    async def _arun(self, memory: Dict[str, Any]) -> Dict[str, Any]:
        """异步执行（当前实现为同步）"""
        return self._run(memory)