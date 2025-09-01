"""
列业务含义分析工具
分析数据库列的业务含义、数据特征和使用模式
"""

from typing import Dict, Any, Type
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from models.exceptions import ToolExecutionError


class ColumnMeaningInput(BaseModel):
    """列含义分析输入"""
    memory: Dict[str, Any] = Field(description="包含数据库分析结果的记忆")


class ColumnMeaningTool(BaseTool):
    """分析数据库列的业务含义"""
    
    name: str = "column_meaning_analysis"
    description: str = "分析数据库列的业务含义，识别列的业务用途、数据模式和常见值"
    args_schema: Type[BaseModel] = ColumnMeaningInput
    
    def _run(self, memory: Dict[str, Any]) -> Dict[str, Any]:
        """执行列含义分析"""
        try:
            # 从记忆中获取必要信息
            db_analysis = memory.get("db_analysis", {})
            schema_info = db_analysis.get("schema_info", {})
            domain_info = db_analysis.get("domain_info", {})
            field_classification = db_analysis.get("field_classification", {})
            
            if not schema_info:
                raise ToolExecutionError(
                    tool_name=self.name,
                    reason="未找到数据库结构信息，请先执行schema_extraction"
                )
            
            column_meanings = {}
            business_terms = {}
            data_patterns = {}
            
            # 分析每个表的列
            tables = schema_info.get("tables", {})
            for table_name, table_info in tables.items():
                table_columns = {}
                
                for column in table_info.get("columns", []):
                    column_name = column["name"]
                    column_type = column["type"]
                    
                    # 分析列的业务含义
                    meaning = self._analyze_column_meaning(
                        table_name, column_name, column_type,
                        domain_info, field_classification
                    )
                    
                    table_columns[column_name] = meaning
                    
                    # 提取业务术语
                    if meaning.get("business_term"):
                        business_terms[meaning["business_term"]] = {
                            "tables": [table_name],
                            "columns": [column_name],
                            "description": meaning.get("description", "")
                        }
                
                column_meanings[table_name] = table_columns
            
            # 识别数据模式
            data_patterns = self._identify_data_patterns(column_meanings)
            
            return {
                "column_meanings": column_meanings,
                "business_terms": business_terms,
                "data_patterns": data_patterns,
                "analysis_summary": self._generate_summary(column_meanings, business_terms)
            }
            
        except Exception as e:
            raise ToolExecutionError(
                tool_name=self.name,
                reason=f"列含义分析失败: {str(e)}"
            )
    
    def _analyze_column_meaning(
        self, 
        table_name: str, 
        column_name: str,
        column_type: str,
        domain_info: Dict[str, Any],
        field_classification: Dict[str, Any]
    ) -> Dict[str, Any]:
        """分析单个列的业务含义"""
        meaning = {
            "column_name": column_name,
            "data_type": column_type,
            "business_meaning": "",
            "business_term": "",
            "usage_pattern": "",
            "value_examples": [],
            "constraints": []
        }
        
        # 基于列名模式识别业务含义
        column_lower = column_name.lower()
        
        # 主键
        if column_lower in ["id", f"{table_name}_id", f"{table_name[:-1]}_id"]:
            meaning["business_meaning"] = "主键标识符"
            meaning["usage_pattern"] = "唯一标识"
            meaning["constraints"].append("PRIMARY KEY")
        
        # 时间相关
        elif any(term in column_lower for term in ["create", "update", "time", "date", "timestamp"]):
            if "create" in column_lower:
                meaning["business_meaning"] = "创建时间"
                meaning["business_term"] = "创建时间戳"
            elif "update" in column_lower:
                meaning["business_meaning"] = "更新时间"
                meaning["business_term"] = "修改时间戳"
            meaning["usage_pattern"] = "时间记录"
        
        # 状态相关
        elif any(term in column_lower for term in ["status", "state", "flag", "is_", "has_"]):
            meaning["business_meaning"] = "状态标识"
            meaning["business_term"] = "状态字段"
            meaning["usage_pattern"] = "状态控制"
        
        # 金额相关
        elif any(term in column_lower for term in ["price", "amount", "cost", "fee", "total"]):
            meaning["business_meaning"] = "金额数值"
            meaning["business_term"] = "金额"
            meaning["usage_pattern"] = "财务计算"
        
        # 数量相关
        elif any(term in column_lower for term in ["count", "quantity", "number", "num"]):
            meaning["business_meaning"] = "数量统计"
            meaning["business_term"] = "数量"
            meaning["usage_pattern"] = "计数统计"
        
        # 名称相关
        elif any(term in column_lower for term in ["name", "title"]):
            meaning["business_meaning"] = "名称标识"
            meaning["business_term"] = "名称"
            meaning["usage_pattern"] = "描述性文本"
        
        # 描述相关
        elif any(term in column_lower for term in ["description", "desc", "comment", "remark"]):
            meaning["business_meaning"] = "详细描述"
            meaning["business_term"] = "描述"
            meaning["usage_pattern"] = "长文本"
        
        # 关联外键
        elif column_lower.endswith("_id") and column_lower != "id":
            referenced_table = column_lower[:-3]
            meaning["business_meaning"] = f"关联到{referenced_table}表"
            meaning["business_term"] = "外键"
            meaning["usage_pattern"] = "关联引用"
            meaning["constraints"].append("FOREIGN KEY")
        
        return meaning
    
    def _identify_data_patterns(self, column_meanings: Dict[str, Any]) -> Dict[str, Any]:
        """识别数据模式"""
        patterns = {
            "timestamp_pattern": [],
            "status_pattern": [],
            "financial_pattern": [],
            "reference_pattern": []
        }
        
        for table_name, columns in column_meanings.items():
            for column_name, meaning in columns.items():
                pattern = meaning.get("usage_pattern", "")
                
                if pattern == "时间记录":
                    patterns["timestamp_pattern"].append(f"{table_name}.{column_name}")
                elif pattern == "状态控制":
                    patterns["status_pattern"].append(f"{table_name}.{column_name}")
                elif pattern == "财务计算":
                    patterns["financial_pattern"].append(f"{table_name}.{column_name}")
                elif pattern == "关联引用":
                    patterns["reference_pattern"].append(f"{table_name}.{column_name}")
        
        return patterns
    
    def _generate_summary(
        self, 
        column_meanings: Dict[str, Any],
        business_terms: Dict[str, Any]
    ) -> str:
        """生成分析摘要"""
        total_columns = sum(len(cols) for cols in column_meanings.values())
        total_terms = len(business_terms)
        
        summary = f"分析完成：共分析了{len(column_meanings)}个表的{total_columns}列，"
        summary += f"识别出{total_terms}个业务术语。"
        
        return summary
    
    async def _arun(self, memory: Dict[str, Any]) -> Dict[str, Any]:
        """异步执行（当前实现为同步）"""
        return self._run(memory)