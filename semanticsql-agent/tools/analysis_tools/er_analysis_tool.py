"""
实体关系分析工具 - 分析表之间的关系
基于 LangChain BaseTool，参考er_analysis_pipeline的实现
"""

from typing import Dict, Any, Type, List, Optional
from pydantic import BaseModel, Field
import json
import logging

from models.exceptions import ToolExecutionError
from prompts.manager import PromptManager
from utils.database import DatabaseManager
from ..base_tool import BaseSemanticSQLTool

logger = logging.getLogger(__name__)


class ERAnalysisInput(BaseModel):
    """ER分析输入 - 无需参数，工具会从记忆中获取数据"""
    pass


class ERRelation(BaseModel):
    """实体关系"""
    from_table: str = Field(description="源表")
    to_table: str = Field(description="目标表")
    from_column: str = Field(description="源列")
    to_column: str = Field(description="目标列")
    relation_type: str = Field(description="关系类型")
    description: str = Field(description="关系描述")


class ERAnalysisTool(BaseSemanticSQLTool):
    """实体关系分析工具"""
    
    name: str = "er_analysis"
    description: str = "分析数据库表之间的物理关系和逻辑关系。无需参数，自动从记忆中获取数据"
    args_schema: Type[BaseModel] = ERAnalysisInput
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, 'prompt_manager', PromptManager())
    
    def _run(self, **kwargs) -> str:
        """执行ER关系分析"""
        try:
            # 从记忆中获取数据
            schema_info = self.get_from_memory("schema_extraction")
            column_meanings = self.get_from_memory("column_meaning_analysis")
            table_meanings = self.get_from_memory("table_meaning_analysis")
            
            if not schema_info:
                raise ToolExecutionError(
                    tool_name=self.name,
                    message="无法获取数据库结构信息，请先运行schema_extraction工具",
                    details="需要先提取数据库结构才能进行ER关系分析"
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
            
            return json.dumps(result, ensure_ascii=False)
            
        except Exception as e:
            self.logger.error(f"ER关系分析失败: {e}")
            raise ToolExecutionError(
                tool_name=self.name,
                message=f"ER关系分析执行失败: {str(e)}",
                details=str(e)
            )
    
    def _analyze_physical_relations(self, schema_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """分析物理关系（外键约束）"""
        physical_relations = []
        
        # 如果有数据库连接，尝试从information_schema获取
        db_manager = self.get_from_memory("database_manager")
        if db_manager:
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
                
                result = db_manager._execute_query(query, {"database_name": database_name})
                
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
        
        # 使用LLM分析 - 简化版本，基于规则分析
        # 实际实现中可以从记忆中获取LLM并调用
        # 这里先返回基于物理关系的逻辑分析结果
        
        # 基于物理关系生成逻辑关系
        return self._generate_logical_relations_from_physical(physical_relations, schema_info)
    
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
        
        # 基于逻辑关系生成概念关系
        return self._generate_conceptual_relations_from_logical(
            physical_relations, logical_relations, schema_info
        )
    
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
    
    def _generate_logical_relations_from_physical(self, physical_relations: List[Dict[str, Any]], schema_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """基于物理关系生成逻辑关系"""
        logical_relations = []
        
        for rel in physical_relations:
            logical_relations.append({
                "from_entity": rel["from_table"],
                "to_entity": rel["to_table"],
                "relationship_type": "references",
                "description": f"{rel['from_table']}通过{rel['from_column']}引用{rel['to_table']}的{rel['to_column']}",
                "cardinality": "many-to-one"
            })
        
        return logical_relations
    
    def _generate_conceptual_relations_from_logical(self, physical_relations: List[Dict[str, Any]], logical_relations: List[Dict[str, Any]], schema_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """基于逻辑关系生成概念关系"""
        conceptual_relations = []
        tables = schema_info.get("tables", {})
        
        # 基于表名推断概念关系
        for table_name in tables.keys():
            # 简单的概念关系推断
            if any(keyword in table_name.lower() for keyword in ["user", "customer", "client"]):
                conceptual_relations.append({
                    "entity": table_name,
                    "concept": "用户实体",
                    "description": f"{table_name}表表示用户相关的业务概念"
                })
            elif any(keyword in table_name.lower() for keyword in ["order", "transaction"]):
                conceptual_relations.append({
                    "entity": table_name,
                    "concept": "交易实体",
                    "description": f"{table_name}表表示交易相关的业务概念"
                })
            elif any(keyword in table_name.lower() for keyword in ["product", "item", "goods"]):
                conceptual_relations.append({
                    "entity": table_name,
                    "concept": "商品实体",
                    "description": f"{table_name}表表示商品相关的业务概念"
                })
        
        return conceptual_relations
    
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