"""
字段分类工具 - 对数据库字段进行语义分类
基于 LangChain BaseTool，参考field_classification_pipeline的实现
"""

from typing import Dict, Any, Type, List
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
import json
import logging

from models.exceptions import ToolExecutionError
from prompts.manager import PromptManager
from utils.database import DatabaseManager
from .base_analysis_tool import BaseAnalysisTool

logger = logging.getLogger(__name__)


class FieldClassificationInput(BaseModel):
    """字段分类输入"""
    schema_info: Dict[str, Any] = Field(default_factory=dict, description="数据库结构信息")
    domain_info: Dict[str, Any] = Field(default_factory=dict, description="业务领域信息")


class FieldClassificationTool(BaseAnalysisTool):
    """字段语义分类工具 - 使用LLM进行智能分类"""
    
    name: str = "field_classification"
    description: str = "使用LLM对数据库字段进行语义分类，识别字段的业务含义和用途"
    args_schema: Type[BaseModel] = FieldClassificationInput
    
    def __init__(self, llm: ChatOpenAI, db_manager: DatabaseManager = None, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, 'llm', llm)
        object.__setattr__(self, 'db_manager', db_manager)
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
            
            # 1. 计算字段熵值（如果有数据库连接）- 参考CalculateFieldEntropyStep
            field_entropy = {}
            if self.db_manager:
                field_entropy = self._calculate_field_entropy(schema_info)
            
            # 2. 批量分类字段 - 参考ClassifyFieldsStep
            field_classifications = self._classify_fields_batch(
                schema_info, domain_info, field_entropy
            )
            
            # 3. 生成分类统计
            classification_summary = self._generate_classification_summary(field_classifications)
            
            # 构建结果
            result = {
                "field_classifications": field_classifications,
                "classification_summary": classification_summary,
                "field_entropy": field_entropy
            }
            
            # 保存到记忆
            self.save_to_memory("field_classification", result)
            
            return result
            
        except Exception as e:
            raise ToolExecutionError(
                tool_name=self.name,
                reason=f"字段分类失败: {str(e)}"
            )
    
    def _calculate_field_entropy(self, schema_info: Dict[str, Any]) -> Dict[str, float]:
        """计算字段熵值（衡量字段值的多样性）"""
        field_entropy = {}
        tables = schema_info.get("tables", {})
        database_name = schema_info.get("database_name", "")
        
        for table_name, table_info in tables.items():
            row_count = table_info.get("row_count", 0)
            if row_count < 10:  # 数据太少，跳过熵计算
                continue
            
            columns = table_info.get("columns", {})
            for col_name, col_info in columns.items():
                # 跳过主键和大文本字段
                if col_name in table_info.get("primary_key", []):
                    continue
                if "text" in col_info["type"].lower() or "blob" in col_info["type"].lower():
                    continue
                
                try:
                    # 计算不同值的数量
                    query = f"""
                    SELECT COUNT(DISTINCT `{col_name}`) as distinct_count
                    FROM `{table_name}`
                    WHERE `{col_name}` IS NOT NULL
                    """
                    
                    result = self.db_manager._execute_query(query)
                    if result.get("success") and result.get("data"):
                        distinct_count = result["data"][0]["distinct_count"]
                        # 简单的熵估算：distinct_count / row_count
                        entropy = min(distinct_count / row_count, 1.0)
                        field_entropy[f"{table_name}.{col_name}"] = round(entropy, 3)
                
                except Exception as e:
                    logger.debug(f"无法计算 {table_name}.{col_name} 的熵值: {e}")
        
        return field_entropy
    
    def _classify_fields_batch(
        self,
        schema_info: Dict[str, Any],
        domain_info: Dict[str, Any],
        field_entropy: Dict[str, float]
    ) -> Dict[str, Dict[str, Any]]:
        """批量分类字段"""
        field_classifications = {}
        tables = schema_info.get("tables", {})
        
        # 准备批量分类数据
        batch_size = 20  # 每批处理20个字段
        all_fields = []
        
        for table_name, table_info in tables.items():
            columns = table_info.get("columns", {})
            sample_data = table_info.get("sample_data", [])
            
            for col_name, col_info in columns.items():
                field_key = f"{table_name}.{col_name}"
                
                # 收集样本值
                samples = []
                if sample_data:
                    for row in sample_data[:3]:  # 最多3个样本
                        if col_name in row and row[col_name] is not None:
                            samples.append(str(row[col_name]))
                
                field_data = {
                    "field_name": field_key,
                    "table_name": table_name,
                    "column_name": col_name,
                    "data_type": col_info["type"],
                    "is_nullable": col_info.get("nullable", True),
                    "is_primary": col_name in table_info.get("primary_key", []),
                    "samples": samples,
                    "entropy": field_entropy.get(field_key, 0)
                }
                
                all_fields.append(field_data)
        
        # 批量处理
        for i in range(0, len(all_fields), batch_size):
            batch = all_fields[i:i + batch_size]
            batch_classifications = self._classify_batch(batch, domain_info)
            
            # 整理结果
            for field_data in batch:
                table_name = field_data["table_name"]
                col_name = field_data["column_name"]
                field_key = field_data["field_name"]
                
                if table_name not in field_classifications:
                    field_classifications[table_name] = {}
                
                field_classifications[table_name][col_name] = batch_classifications.get(
                    field_key,
                    {
                        "category": "other",
                        "field_type": "unknown",
                        "importance": "low"
                    }
                )
        
        return field_classifications
    
    def _classify_batch(self, fields: List[Dict[str, Any]], domain_info: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """分类一批字段"""
        # 准备提示词数据
        prompt_data = {
            "fields": fields,
            "domain_type": domain_info.get("domain_type", "未知") if domain_info else "未知",
            "domain_description": domain_info.get("domain_description", "") if domain_info else ""
        }
        
        # 渲染提示词
        prompt = self.prompt_manager.get_analysis_prompt(
            "field_classification", **prompt_data
        )
        
        # 调用LLM
        response = self.llm.invoke(prompt)
        
        # 解析响应
        return self._parse_classification_response(response.content, fields)
    
    def _parse_classification_response(self, response: str, fields: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """解析分类响应"""
        classifications = {}
        
        try:
            # 尝试解析JSON
            result = json.loads(response)
            if isinstance(result, dict):
                # 如果是嵌套在field_classifications下
                if "field_classifications" in result:
                    flat_result = {}
                    for table_name, table_fields in result["field_classifications"].items():
                        for col_name, col_info in table_fields.items():
                            field_key = f"{table_name}.{col_name}"
                            flat_result[field_key] = col_info
                    return flat_result
                else:
                    return result
        except json.JSONDecodeError:
            pass
        
        # 如果JSON解析失败，返回默认分类
        for field in fields:
            field_key = field["field_name"]
            
            # 基于规则的简单分类
            category = "other"
            field_type = "unknown"
            importance = "low"
            
            col_name_lower = field["column_name"].lower()
            data_type_lower = field["data_type"].lower()
            
            # 分类逻辑
            if field["is_primary"] or col_name_lower.endswith("_id") or col_name_lower == "id":
                category = "identifier"
                field_type = "主键" if field["is_primary"] else "外键"
                importance = "high"
            elif any(dt in data_type_lower for dt in ["date", "time", "timestamp"]):
                category = "datetime"
                field_type = "时间戳"
                importance = "medium"
            elif any(dt in data_type_lower for dt in ["int", "decimal", "float", "numeric"]):
                if any(kw in col_name_lower for kw in ["amount", "price", "cost", "fee"]):
                    category = "measure"
                    field_type = "金额"
                    importance = "high"
                elif any(kw in col_name_lower for kw in ["count", "num", "qty"]):
                    category = "measure"
                    field_type = "数量"
                    importance = "medium"
                else:
                    category = "measure"
                    field_type = "数值"
                    importance = "medium"
            elif any(dt in data_type_lower for dt in ["varchar", "char", "text"]):
                if any(kw in col_name_lower for kw in ["name", "title"]):
                    category = "text"
                    field_type = "名称"
                    importance = "high"
                elif any(kw in col_name_lower for kw in ["status", "state", "type"]):
                    category = "dimension"
                    field_type = "状态"
                    importance = "medium"
                else:
                    category = "text"
                    field_type = "文本"
                    importance = "low"
            elif any(dt in data_type_lower for dt in ["bool", "bit", "tinyint(1)"]):
                category = "boolean"
                field_type = "布尔值"
                importance = "medium"
            
            classifications[field_key] = {
                "category": category,
                "field_type": field_type,
                "importance": importance
            }
        
        return classifications
    
    def _generate_classification_summary(self, field_classifications: Dict[str, Dict[str, Any]]) -> Dict[str, List[str]]:
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
        
        for table_name, table_fields in field_classifications.items():
            for field_name, field_info in table_fields.items():
                category = field_info.get("category", "other")
                if category in summary:
                    summary[category].append(f"{table_name}.{field_name}")
        
        return summary