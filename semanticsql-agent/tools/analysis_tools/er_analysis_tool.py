"""
实体关系分析工具 - 分析表之间的关系
基于 LangChain BaseTool，参考er_analysis_pipeline的实现
"""

from typing import Dict, Any, Type, List, Optional
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, ConfigDict
import json
import logging

from models.exceptions import ToolExecutionError
from prompts.manager import PromptManager
from utils.database import DatabaseManager
from .base_analysis_tool import BaseAnalysisTool

logger = logging.getLogger(__name__)


class ERAnalysisInput(BaseModel):
    """ER分析输入"""
    schema_info: Dict[str, Any] = Field(default_factory=dict, description="数据库结构信息")
    column_meanings: Dict[str, Any] = Field(default_factory=dict, description="列含义信息")
    table_meanings: Dict[str, Any] = Field(default_factory=dict, description="表含义信息")


class ERAnalysisTool(BaseAnalysisTool):
    """实体关系分析工具"""
    
    name: str = "er_analysis"
    description: str = "分析数据库表之间的物理关系和逻辑关系"
    args_schema: Type[BaseModel] = ERAnalysisInput
    
    # 定义必需的字段
    llm: Optional[ChatOpenAI] = Field(default=None, exclude=True)
    db_manager: Optional[DatabaseManager] = Field(default=None, exclude=True)
    prompt_manager: Optional[PromptManager] = Field(default=None, exclude=True)
    
    # Pydantic v2配置
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    def __init__(self, llm: ChatOpenAI, db_manager: DatabaseManager = None, **kwargs):
        super().__init__(**kwargs)
        self.llm = llm
        self.db_manager = db_manager
        self.prompt_manager = PromptManager()
    
    def _run(
        self,
        schema_info: Dict[str, Any] = None,
        column_meanings: Dict[str, Any] = None,
        table_meanings: Dict[str, Any] = None
    ,
        **kwargs  # 接受额外的参数如 verbose
    ) -> Dict[str, Any]:
        """执行ER关系分析"""
        try:
            # 从参数或memory获取数据
            schema_info = schema_info or self.get_schema_info()
            column_meanings = column_meanings or self.get_column_meanings()
            table_meanings = table_meanings or self.get_table_meanings()
            
            if not schema_info:
                raise ToolExecutionError(
                    tool_name=self.name,
                    reason="未找到数据库结构信息，请先执行schema_extraction"
                )
            
            # 1. 分析物理关系（外键）- 参考AnalyzePhysicalRelationsStep
            physical_relations = self._analyze_physical_relations(schema_info)
            
            # 2. 使用LLM分析逻辑关系 - 参考AnalyzeLogicalRelationsStep
            logical_relations = self._analyze_logical_relations(
                schema_info, physical_relations, column_meanings, table_meanings
            )
            
            # 3. 使用LLM分析概念关系 - 参考AnalyzeConceptualRelationsStep
            conceptual_relations = self._analyze_conceptual_relations(
                schema_info, physical_relations, logical_relations, 
                column_meanings, table_meanings
            )
            
            # 构建结果
            result = {
                "physical_relations": physical_relations,
                "logical_relations": logical_relations,
                "conceptual_relations": conceptual_relations,
                "summary": self._generate_summary(
                    physical_relations, logical_relations, conceptual_relations
                )
            }
            
            # 保存到记忆
            self.save_to_memory("er_analysis", result)
            
            return result
            
        except Exception as e:
            raise ToolExecutionError(
                tool_name=self.name,
                reason=f"ER关系分析失败: {str(e)}"
            )
    
    def _analyze_physical_relations(self, schema_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """分析物理关系（外键约束）"""
        physical_relations = []
        
        # 如果有数据库连接，尝试从information_schema获取
        if self.db_manager:
            try:
                database_name = schema_info.get("database_name", "")
                query = """
                SELECT 
                    kcu.TABLE_NAME as from_table,
                    kcu.COLUMN_NAME as from_column,
                    kcu.REFERENCED_TABLE_NAME as to_table,
                    kcu.REFERENCED_COLUMN_NAME as to_column,
                    kcu.CONSTRAINT_NAME as constraint_name
                FROM information_schema.KEY_COLUMN_USAGE kcu
                WHERE kcu.TABLE_SCHEMA = :database_name
                    AND kcu.REFERENCED_TABLE_NAME IS NOT NULL
                ORDER BY kcu.TABLE_NAME, kcu.COLUMN_NAME
                """
                
                result = self.db_manager._execute_query(query, {"database_name": database_name})
                
                if result.get("success") and result.get("data"):
                    for row in result["data"]:
                        relation = {
                            "from_table": row["from_table"],
                            "from_column": row["from_column"],
                            "to_table": row["to_table"],
                            "to_column": row["to_column"],
                            "constraint_name": row["constraint_name"],
                            "relationship_type": "foreign_key"
                        }
                        physical_relations.append(relation)
            except Exception as e:
                logger.warning(f"无法从数据库获取外键信息: {e}")
        
        # 从schema信息中提取（备用方法）
        if not physical_relations:
            tables = schema_info.get("tables", {})
            for table_name, table_info in tables.items():
                foreign_keys = table_info.get("foreign_keys", [])
                for fk in foreign_keys:
                    relation = {
                        "from_table": table_name,
                        "from_column": fk.get("column", ""),
                        "to_table": fk.get("referenced_table", ""),
                        "to_column": fk.get("referenced_column", ""),
                        "constraint_name": fk.get("constraint_name", ""),
                        "relationship_type": "foreign_key"
                    }
                    physical_relations.append(relation)
        
        return physical_relations
    
    def _analyze_logical_relations(
        self,
        schema_info: Dict[str, Any],
        physical_relations: List[Dict[str, Any]],
        column_meanings: Dict[str, Any],
        table_meanings: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """使用LLM分析逻辑关系"""
        # 准备提示词数据
        formatted_schema = self._format_schema_with_comments(
            schema_info, column_meanings, table_meanings
        )
        
        fk_info = self._format_foreign_keys(physical_relations)
        
        prompt_data = {
            'formatted_schema': formatted_schema,
            'fk_info': fk_info,
            'database_name': schema_info.get('database_name', 'unknown')
        }
        
        # 使用LLM分析
        prompt = self.prompt_manager.get_analysis_prompt(
            "er_analysis_logical", **prompt_data
        )
        
        response = self.llm.invoke(prompt)
        
        # 解析响应
        return self._parse_logical_relations(response.content)
    
    def _analyze_conceptual_relations(
        self,
        schema_info: Dict[str, Any],
        physical_relations: List[Dict[str, Any]],
        logical_relations: List[Dict[str, Any]],
        column_meanings: Dict[str, Any],
        table_meanings: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """使用LLM分析概念关系"""
        # 准备数据
        formatted_schema = self._format_schema_with_comments(
            schema_info, column_meanings, table_meanings
        )
        
        prompt_data = {
            'formatted_schema': formatted_schema,
            'physical_relations': physical_relations,
            'logical_relations': logical_relations
        }
        
        # 使用LLM分析
        prompt = self.prompt_manager.get_analysis_prompt(
            "er_analysis_conceptual", **prompt_data
        )
        
        response = self.llm.invoke(prompt)
        
        # 解析响应
        return self._parse_conceptual_relations(response.content)
    
    def _format_schema_with_comments(
        self,
        schema_info: Dict[str, Any],
        column_meanings: Dict[str, Any],
        table_meanings: Dict[str, Any]
    ) -> str:
        """格式化带注释的表结构"""
        lines = ["数据库表结构（包含业务注释）："]
        tables = schema_info.get("tables", {})
        
        # 获取列描述和表描述
        col_descriptions = {}
        if column_meanings:
            col_descriptions = column_meanings.get("column_descriptions", {})
        
        table_descriptions = {}
        if table_meanings:
            table_descriptions = table_meanings.get("table_descriptions", {})
        
        for table_name, table_info in tables.items():
            lines.append(f"\n表: {table_name}")
            
            # 表描述
            if table_name in table_descriptions:
                lines.append(f"  注释: {table_descriptions[table_name]}")
            
            lines.append("  列:")
            columns = table_info.get("columns", {})
            primary_keys = table_info.get("primary_key", [])
            
            for col_name, col_info in columns.items():
                col_key = f"{table_name}.{col_name}"
                col_desc = col_descriptions.get(col_key, "")
                
                col_line = f"    - {col_name} ({col_info['type']})"
                if col_name in primary_keys:
                    col_line += " [主键]"
                if col_desc:
                    col_line += f" - {col_desc}"
                
                lines.append(col_line)
        
        return "\n".join(lines)
    
    def _format_foreign_keys(self, physical_relations: List[Dict[str, Any]]) -> str:
        """格式化外键信息"""
        if not physical_relations:
            return "无外键约束"
        
        lines = ["外键关系："]
        for rel in physical_relations:
            lines.append(
                f"- {rel['from_table']}.{rel['from_column']} -> "
                f"{rel['to_table']}.{rel['to_column']}"
            )
        
        return "\n".join(lines)
    
    def _parse_logical_relations(self, response: str) -> List[Dict[str, Any]]:
        """解析逻辑关系响应"""
        try:
            # 尝试解析JSON
            result = json.loads(response)
            if isinstance(result, list):
                return result
            elif isinstance(result, dict) and "logical_relations" in result:
                return result["logical_relations"]
        except json.JSONDecodeError:
            pass
        
        # 文本解析
        relations = []
        lines = response.split('\n')
        
        for line in lines:
            line = line.strip()
            if '->' in line or '←→' in line:
                # 简单解析关系描述
                parts = line.split('->' if '->' in line else '←→')
                if len(parts) == 2:
                    relations.append({
                        "from": parts[0].strip(),
                        "to": parts[1].strip(),
                        "type": "one-to-many" if '->' in line else "many-to-many",
                        "description": line
                    })
        
        return relations
    
    def _parse_conceptual_relations(self, response: str) -> List[Dict[str, Any]]:
        """解析概念关系响应"""
        try:
            # 尝试解析JSON
            result = json.loads(response)
            if isinstance(result, list):
                return result
            elif isinstance(result, dict) and "conceptual_relations" in result:
                return result["conceptual_relations"]
        except json.JSONDecodeError:
            pass
        
        # 文本解析
        relations = []
        current_relation = None
        
        lines = response.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 查找实体关系模式
            if any(keyword in line for keyword in ['包含', '属于', '关联', '依赖', '引用']):
                if current_relation:
                    relations.append(current_relation)
                
                current_relation = {
                    "description": line,
                    "entities": [],
                    "relationship_type": "conceptual"
                }
        
        if current_relation:
            relations.append(current_relation)
        
        return relations
    
    def _generate_summary(
        self,
        physical_relations: List[Dict[str, Any]],
        logical_relations: List[Dict[str, Any]],
        conceptual_relations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """生成关系分析摘要"""
        return {
            "total_physical_relations": len(physical_relations),
            "total_logical_relations": len(logical_relations),
            "total_conceptual_relations": len(conceptual_relations),
            "has_foreign_keys": len(physical_relations) > 0,
            "relationship_complexity": self._assess_complexity(
                physical_relations, logical_relations, conceptual_relations
            )
        }
    
    def _assess_complexity(
        self,
        physical_relations: List[Dict[str, Any]],
        logical_relations: List[Dict[str, Any]],
        conceptual_relations: List[Dict[str, Any]]
    ) -> str:
        """评估关系复杂度"""
        total_relations = (
            len(physical_relations) + 
            len(logical_relations) + 
            len(conceptual_relations)
        )
        
        if total_relations == 0:
            return "独立表结构"
        elif total_relations < 5:
            return "简单关系"
        elif total_relations < 15:
            return "中等复杂度"
        else:
            return "高度复杂"