"""
SQL反思工具 - 分析执行结果并提供优化建议
基于 LangChain BaseTool，从记忆中获取所需信息
"""

from typing import Dict, Any, Type, List, Optional
from pydantic import BaseModel, Field
import json
import logging

from models.exceptions import ToolExecutionError
from prompts.manager import PromptManager
from ..base_tool import BaseSemanticSQLTool

logger = logging.getLogger(__name__)


class SQLReflectionInput(BaseModel):
    """SQL反思输入 - 从记忆中自动获取所需信息"""
    pass


class ReflectionResult(BaseModel):
    """反思结果"""
    quality_score: float = Field(description="质量分数 0-1")
    needs_revision: bool = Field(description="是否需要修正")
    suggested_tool: Optional[str] = Field(default=None, description="建议的工具")
    suggestion: str = Field(description="修正建议")


class SQLReflectionTool(BaseSemanticSQLTool):
    """SQL执行反思与优化工具"""
    
    name: str = "sql_reflection"
    description: str = "分析SQL执行结果，评估质量并提供改进建议。自动从记忆中获取所需信息"
    args_schema: Type[BaseModel] = SQLReflectionInput
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, 'prompt_manager', PromptManager())

    def _run(self, **kwargs) -> str:
        """执行SQL反思分析"""
        try:
            # 从记忆中获取当前生成的问题、SQL和执行结果
            # 这些信息应该在Agent执行过程中被保存
            current_question = self.get_from_memory("current_question")
            current_sql = self.get_from_memory("current_sql") 
            execution_result = self.get_from_memory("execution_result")
            
            # 基础质量评估
            reflection_result = self._evaluate_sql_quality(
                current_question, current_sql, execution_result
            )
            
            # 保存反思结果到记忆
            self.save_to_memory("sql_reflection", reflection_result)
            
            return json.dumps(reflection_result, ensure_ascii=False)
            
        except Exception as e:
            self.logger.error(f"SQL反思失败: {e}")
            raise ToolExecutionError(
                tool_name=self.name,
                message=f"SQL反思执行失败: {str(e)}",
                details=str(e)
            )
    
    def _evaluate_sql_quality(self, question: str, sql: str, execution_result: Dict[str, Any]) -> Dict[str, Any]:
        """评估SQL质量"""
        quality_score = 1.0
        needs_revision = False
        suggested_tool = None
        suggestions = []
        
        # 检查执行结果
        if not execution_result:
            quality_score = 0.0
            needs_revision = True
            suggested_tool = "sql_generation"
            suggestions.append("SQL执行失败，需要重新生成")
            
        elif not execution_result.get("success", False):
            quality_score = 0.2
            needs_revision = True
            error_msg = execution_result.get("error", "")
            
            if "syntax" in error_msg.lower():
                suggested_tool = "sql_generation"
                suggestions.append("SQL语法错误，需要重新生成")
            elif "table" in error_msg.lower() or "column" in error_msg.lower():
                suggested_tool = "sql_generation"
                suggestions.append("表名或列名错误，需要检查数据库结构")
            else:
                suggested_tool = "sql_generation"
                suggestions.append("SQL执行错误，需要重新生成")
                
        else:
            # 执行成功，评估结果质量
            row_count = execution_result.get("row_count", 0)
            
            if row_count == 0:
                quality_score = 0.6
                suggestions.append("查询结果为空，可能条件过于严格")
            elif row_count > 1000:
                quality_score = 0.7
                suggestions.append("查询结果过多，建议添加LIMIT限制")
            else:
                quality_score = 0.85
                suggestions.append("SQL执行成功，结果合理")
        
        # 检查SQL复杂度合理性
        if sql and len(sql.split()) > 50:
            quality_score *= 0.9
            suggestions.append("SQL较为复杂，建议简化")
        
        return {
            "quality_score": round(quality_score, 2),
            "needs_revision": needs_revision,
            "suggested_tool": suggested_tool,
            "suggestion": "; ".join(suggestions) if suggestions else "SQL质量良好"
        }