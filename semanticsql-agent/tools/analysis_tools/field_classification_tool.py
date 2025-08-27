"""字段分类工具"""

from tools.base import BaseSemanticSQLTool
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from models.schemas import FieldType
import logging

logger = logging.getLogger(__name__)


class FieldClassificationInput(BaseModel):
    """输入模式"""
    table_name: str = Field(description="要分类的表名")
    table_info: Dict[str, Any] = Field(
        description="表信息，包括结构和样本数据"
    )


class FieldClassificationTool(BaseSemanticSQLTool):
    """字段分类工具"""
    
    name = "classify_table_fields"
    description = (
        "对表的字段进行分类，识别维度、度量、标识符、时间戳等类型。"
        "这有助于理解数据结构，生成正确的聚合查询。"
    )
    args_schema = FieldClassificationInput
    
    def execute(
        self,
        table_name: str,
        table_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行字段分类"""
        # 构建分类提示词
        prompt = self._build_classification_prompt(table_name, table_info)
        
        # 调用 LLM 分类
        response = self.llm.invoke(prompt)
        
        # 解析分类结果
        classification = self._parse_classification_response(
            response.content,
            table_info.get("columns", [])
        )
        
        return {
            "table": table_name,
            "classification": classification,
            "summary": self._generate_summary(classification)
        }
    
    def _build_classification_prompt(
        self, 
        table_name: str,
        table_info: Dict[str, Any]
    ) -> str:
        """构建分类提示词"""
        # 表结构
        structure = table_info.get("structure", "")
        
        # 样本数据
        sample_data = table_info.get("sample_data", "")
        
        prompt = f"""请对表 {table_name} 的字段进行分类。

表结构：
{structure}

样本数据：
{sample_data}

请将每个字段分类为以下类型之一：
1. dimensions（维度）: 用于分组、筛选的分类字段，如地区、产品类别、状态
2. measures（度量）: 可以进行数学运算的数值字段，如金额、数量、分数
3. identifiers（标识符）: 唯一标识记录的字段，如 ID、编号、代码
4. timestamps（时间戳）: 时间相关的字段，如创建时间、更新时间、日期
5. descriptions（描述）: 文本描述性字段，如备注、说明、名称

请按以下格式返回分类结果：
字段名: 类型 - 简短说明

例如：
user_id: identifiers - 用户唯一标识
order_amount: measures - 订单金额
create_time: timestamps - 创建时间
status: dimensions - 订单状态
remark: descriptions - 备注信息"""
        
        return prompt
    
    def _parse_classification_response(
        self,
        response: str,
        columns: List[Dict[str, str]]
    ) -> Dict[str, Dict[str, Any]]:
        """解析分类响应"""
        classification = {}
        
        # 创建列名到列信息的映射
        column_map = {col["name"]: col for col in columns}
        
        # 解析响应
        lines = response.split('\n')
        for line in lines:
            line = line.strip()
            if not line or not ':' in line:
                continue
            
            parts = line.split(':', 1)
            if len(parts) != 2:
                continue
            
            field_name = parts[0].strip()
            type_desc = parts[1].strip()
            
            # 提取类型
            field_type = None
            description = type_desc
            
            for ft in FieldType:
                if ft.value in type_desc.lower():
                    field_type = ft
                    # 提取描述
                    if '-' in type_desc:
                        description = type_desc.split('-', 1)[-1].strip()
                    break
            
            # 如果没有识别出类型，尝试根据字段名和类型推断
            if not field_type and field_name in column_map:
                field_type = self._infer_field_type(
                    field_name,
                    column_map[field_name]
                )
            
            if field_name in column_map:
                classification[field_name] = {
                    "type": field_type.value if field_type else "unknown",
                    "data_type": column_map[field_name].get("type", ""),
                    "nullable": column_map[field_name].get("nullable", True),
                    "description": description
                }
        
        # 补充未分类的字段
        for col in columns:
            if col["name"] not in classification:
                field_type = self._infer_field_type(col["name"], col)
                classification[col["name"]] = {
                    "type": field_type.value if field_type else "unknown",
                    "data_type": col.get("type", ""),
                    "nullable": col.get("nullable", True),
                    "description": col.get("comment", "")
                }
        
        return classification
    
    def _infer_field_type(
        self,
        field_name: str,
        column_info: Dict[str, str]
    ) -> Optional[FieldType]:
        """根据字段名和类型推断字段类型"""
        field_name_lower = field_name.lower()
        data_type_lower = column_info.get("type", "").lower()
        
        # 标识符
        if any(keyword in field_name_lower for keyword in ["id", "code", "no", "key"]):
            return FieldType.IDENTIFIER
        
        # 时间戳
        if any(keyword in field_name_lower for keyword in ["time", "date", "created", "updated"]):
            return FieldType.TIMESTAMP
        if any(keyword in data_type_lower for keyword in ["datetime", "timestamp", "date"]):
            return FieldType.TIMESTAMP
        
        # 度量
        if any(keyword in data_type_lower for keyword in ["int", "decimal", "float", "double", "numeric"]):
            if not any(keyword in field_name_lower for keyword in ["id", "code", "status"]):
                return FieldType.MEASURE
        
        # 描述
        if any(keyword in data_type_lower for keyword in ["text", "varchar", "char"]):
            if any(keyword in field_name_lower for keyword in ["name", "desc", "remark", "comment"]):
                return FieldType.DESCRIPTION
        
        # 默认：维度
        return FieldType.DIMENSION
    
    def _generate_summary(self, classification: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """生成分类摘要"""
        summary = {
            "total_fields": len(classification),
            "by_type": {},
            "key_measures": [],
            "key_dimensions": []
        }
        
        # 统计各类型字段数量
        for field_type in FieldType:
            count = sum(1 for f in classification.values() if f["type"] == field_type.value)
            summary["by_type"][field_type.value] = count
            
            # 记录关键字段
            if field_type == FieldType.MEASURE:
                summary["key_measures"] = [
                    name for name, info in classification.items()
                    if info["type"] == field_type.value
                ][:5]  # 最多5个
            elif field_type == FieldType.DIMENSION:
                summary["key_dimensions"] = [
                    name for name, info in classification.items()
                    if info["type"] == field_type.value
                ][:5]  # 最多5个
        
        return summary