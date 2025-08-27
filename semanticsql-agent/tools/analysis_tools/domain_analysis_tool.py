"""业务领域分析工具"""

from tools.base import BaseSemanticSQLTool
from pydantic import BaseModel, Field
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class DomainAnalysisInput(BaseModel):
    """输入模式"""
    schema_info: Dict[str, Any] = Field(
        description="数据库结构信息，通常来自 schema_extraction 工具"
    )
    focus_tables: Optional[List[str]] = Field(
        default=None,
        description="需要重点分析的表"
    )


class DomainAnalysisTool(BaseSemanticSQLTool):
    """业务领域分析工具"""
    
    name = "analyze_business_domain"
    description = (
        "分析数据库的业务领域，识别关键实体、业务规则和专业术语。"
        "帮助理解数据的业务含义，为 SQL 生成提供上下文。"
    )
    args_schema = DomainAnalysisInput
    
    def execute(
        self, 
        schema_info: Dict[str, Any],
        focus_tables: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """执行领域分析"""
        # 构建分析提示词
        tables_desc = []
        tables_to_analyze = focus_tables or list(schema_info.get("tables", {}).keys())
        
        for table in tables_to_analyze:
            table_info = schema_info.get("tables", {}).get(table, {})
            if table_info:
                desc = f"\n表名: {table}"
                
                # 添加表结构
                if "structure" in table_info:
                    desc += f"\n结构:\n{table_info['structure']}"
                
                # 添加样本数据
                if table_info.get("sample_data"):
                    desc += f"\n样本数据:\n{table_info['sample_data']}"
                
                tables_desc.append(desc)
        
        prompt = f"""请分析以下数据库的业务领域和含义：

{chr(10).join(tables_desc)}

请识别并返回：
1. 业务领域（如：电商、金融、教育、医疗等）
2. 关键业务实体（如：用户、订单、产品等）
3. 主要业务流程或规则
4. 重要的业务术语及其含义

请用简洁明了的语言描述。"""
        
        # 调用 LLM 分析
        response = self.llm.invoke(prompt)
        
        # 解析响应
        analysis_result = {
            "raw_analysis": response.content,
            "tables_analyzed": len(tables_to_analyze),
            "schema_summary": self._summarize_schema(schema_info)
        }
        
        # 尝试结构化解析
        try:
            analysis_result.update(self._parse_analysis_response(response.content))
        except Exception as e:
            logger.warning(f"结构化解析失败: {e}")
        
        return analysis_result
    
    def _summarize_schema(self, schema_info: Dict[str, Any]) -> Dict[str, Any]:
        """总结 schema 信息"""
        tables = schema_info.get("tables", {})
        
        summary = {
            "total_tables": len(tables),
            "tables_with_data": 0,
            "total_columns": 0,
            "table_names": list(tables.keys())
        }
        
        for table_name, table_info in tables.items():
            if table_info.get("row_count", 0) > 0:
                summary["tables_with_data"] += 1
            
            columns = table_info.get("columns", [])
            summary["total_columns"] += len(columns)
        
        return summary
    
    def _parse_analysis_response(self, response: str) -> Dict[str, Any]:
        """尝试从响应中提取结构化信息"""
        result = {
            "domain": "未知",
            "key_entities": [],
            "business_rules": [],
            "terminology": {}
        }
        
        # 简单的关键词提取
        lines = response.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 识别章节
            if "领域" in line and "：" in line:
                domain_text = line.split("：", 1)[-1].strip()
                result["domain"] = domain_text
            elif "实体" in line and "：" in line:
                current_section = "entities"
            elif "规则" in line or "流程" in line:
                current_section = "rules"
            elif "术语" in line:
                current_section = "terms"
            elif line.startswith("-") or line.startswith("•"):
                # 处理列表项
                item = line.lstrip("-•").strip()
                if current_section == "entities" and item:
                    result["key_entities"].append(item)
                elif current_section == "rules" and item:
                    result["business_rules"].append(item)
            elif "：" in line and current_section == "terms":
                # 处理术语
                term, desc = line.split("：", 1)
                result["terminology"][term.strip()] = desc.strip()
        
        return result