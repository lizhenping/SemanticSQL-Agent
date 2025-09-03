"""
表业务含义分析工具 - 分析每个表的业务职责
基于 LangChain BaseTool，参考table_description_pipeline的实现
"""

from typing import Dict, Any, Type
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
import json
import logging

from models.exceptions import ToolExecutionError
from prompts.manager import PromptManager
from .base_analysis_tool import BaseAnalysisTool

logger = logging.getLogger(__name__)


class TableMeaningInput(BaseModel):
    """表含义分析输入"""
    schema_info: Dict[str, Any] = Field(default_factory=dict, description="数据库结构信息")
    domain_info: Dict[str, Any] = Field(default_factory=dict, description="领域信息")
    column_meanings: Dict[str, Any] = Field(default_factory=dict, description="列含义信息")


class TableMeaningTool(BaseAnalysisTool):
    """表业务含义分析工具"""
    
    name: str = "table_meaning_analysis"
    description: str = "使用LLM分析每个表的业务职责和含义"
    args_schema: Type[BaseModel] = TableMeaningInput
    
    def __init__(self, llm: ChatOpenAI, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, 'llm', llm)
        object.__setattr__(self, 'prompt_manager', PromptManager())
    
    def _run(
        self,
        schema_info: Dict[str, Any] = None,
        domain_info: Dict[str, Any] = None,
        column_meanings: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """执行表含义分析"""
        try:
            # 从参数或memory获取数据
            schema_info = schema_info or self.get_schema_info()
            domain_info = domain_info or self.get_domain_info()
            column_meanings = column_meanings or self.get_column_meanings()
            
            if not schema_info:
                raise ToolExecutionError(
                    tool_name=self.name,
                    reason="未找到数据库结构信息，请先执行schema_extraction"
                )
            
            # 批量生成表描述
            table_descriptions = self._generate_table_descriptions(
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
            
            return result
            
        except Exception as e:
            raise ToolExecutionError(
                tool_name=self.name,
                reason=f"表含义分析失败: {str(e)}"
            )
    
    def _generate_table_descriptions(
        self,
        schema_info: Dict[str, Any],
        domain_info: Dict[str, Any],
        column_meanings: Dict[str, Any]
    ) -> Dict[str, str]:
        """批量生成表描述"""
        table_descriptions = {}
        tables = schema_info.get("tables", {})
        
        # 获取列描述
        col_descriptions = {}
        if column_meanings:
            col_descriptions = column_meanings.get("column_descriptions", {})
        
        # 批量处理（每批10个表）
        batch_size = 10
        table_list = list(tables.items())
        
        for i in range(0, len(table_list), batch_size):
            batch = table_list[i:i + batch_size]
            
            # 准备批次数据
            batch_tables = []
            for table_name, table_info in batch:
                # 收集该表的列描述
                table_col_descriptions = {}
                for col_name in table_info.get("columns", {}):
                    col_key = f"{table_name}.{col_name}"
                    if col_key in col_descriptions:
                        table_col_descriptions[col_name] = col_descriptions[col_key]
                
                batch_tables.append({
                    "name": table_name,
                    "info": table_info,
                    "column_descriptions": table_col_descriptions
                })
            
            # 使用LLM生成该批次的表描述
            batch_descriptions = self._generate_batch_descriptions(
                batch_tables,
                domain_info
            )
            
            # 更新结果
            table_descriptions.update(batch_descriptions)
        
        return table_descriptions
    
    def _generate_batch_descriptions(
        self,
        batch_tables: list,
        domain_info: Dict[str, Any]
    ) -> Dict[str, str]:
        """为一批表生成描述"""
        # 准备提示词数据
        tables_info = []
        for table_data in batch_tables:
            table_info = {
                "name": table_data["name"],
                "columns": [],
                "row_count": table_data["info"].get("row_count", 0),
                "comment": table_data["info"].get("comment", "")
            }
            
            # 添加列信息
            columns = table_data["info"].get("columns", {})
            for col_name, col_info in columns.items():
                col_desc = table_data["column_descriptions"].get(col_name, "")
                table_info["columns"].append({
                    "name": col_name,
                    "type": col_info["type"],
                    "description": col_desc
                })
            
            tables_info.append(table_info)
        
        prompt_data = {
            "tables": tables_info,
            "domain_type": domain_info.get("domain_type", "未知") if domain_info else "未知",
            "domain_description": domain_info.get("domain_description", "") if domain_info else ""
        }
        
        # 渲染提示词
        prompt = self.prompt_manager.get_analysis_prompt(
            "table_description", **prompt_data
        )
        
        # 调用LLM
        response = self.llm.invoke(prompt)
        
        # 解析响应
        return self._parse_table_descriptions(response.content, batch_tables)
    
    def _parse_table_descriptions(self, response: str, batch_tables: list) -> Dict[str, str]:
        """解析表描述响应"""
        descriptions = {}
        
        try:
            # 尝试解析JSON
            result = json.loads(response)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass
        
        # 文本解析
        lines = response.split('\n')
        current_table = None
        current_desc = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 查找表名
            found_table = False
            for table_data in batch_tables:
                table_name = table_data["name"]
                if table_name in line and (":" in line or "：" in line):
                    # 保存之前的表描述
                    if current_table and current_desc:
                        descriptions[current_table] = " ".join(current_desc)
                    
                    # 开始新表
                    current_table = table_name
                    # 提取描述
                    desc_part = line.split(":" if ":" in line else "：", 1)[1].strip()
                    current_desc = [desc_part] if desc_part else []
                    found_table = True
                    break
            
            # 如果不是新表，添加到当前描述
            if not found_table and current_table and line:
                current_desc.append(line)
        
        # 保存最后一个表的描述
        if current_table and current_desc:
            descriptions[current_table] = " ".join(current_desc)
        
        # 确保所有表都有描述
        for table_data in batch_tables:
            table_name = table_data["name"]
            if table_name not in descriptions:
                descriptions[table_name] = f"{table_name}表"
        
        return descriptions