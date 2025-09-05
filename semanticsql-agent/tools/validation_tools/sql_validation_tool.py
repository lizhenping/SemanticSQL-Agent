"""
SQL验证工具 - 验证SQL语法正确性
基于 LangChain BaseTool
"""

from typing import Dict, Any, Type, List, Optional
import sqlparse
from pydantic import BaseModel, Field
import json

from models.exceptions import ToolExecutionError
from ..base_tool import BaseSemanticSQLTool


class SQLValidationInput(BaseModel):
    """SQL验证输入"""
    sql: str = Field(description="要验证的SQL语句")


class SQLValidationTool(BaseSemanticSQLTool):
    """SQL语法验证工具"""
    
    name: str = "sql_validation"
    description: str = "验证SQL语句的语法正确性。自动从记忆中获取数据库管理器"
    args_schema: Type[BaseModel] = SQLValidationInput
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    def _run(self, sql: str, **kwargs) -> str:
        """验证SQL"""
        try:
            # 基本语法验证
            parsed = sqlparse.parse(sql)
            if not parsed:
                result = {
                    "valid": False,
                    "error": "无法解析SQL语句",
                    "suggestions": ["检查SQL语法是否完整"]
                }
                self.save_to_memory("sql_validation_result", result)
                return json.dumps(result, ensure_ascii=False)
            
            # 格式化SQL
            formatted_sql = sqlparse.format(
                sql,
                reindent=True,
                keyword_case='upper'
            )
            
            # 使用数据库的EXPLAIN验证
            validation_result = self._validate_with_explain(formatted_sql)
            
            result = {
                "valid": validation_result["valid"],
                "formatted_sql": formatted_sql,
                "error": validation_result.get("error"),
                "suggestions": validation_result.get("suggestions", [])
            }
            
            # 保存验证结果到记忆
            self.save_to_memory("sql_validation_result", result)
            
            return json.dumps(result, ensure_ascii=False)
            
        except Exception as e:
            raise ToolExecutionError(
                tool_name=self.name,
                reason=f"SQL验证失败: {str(e)}"
            )
    
    def _validate_with_explain(self, sql: str) -> Dict[str, Any]:
        """使用EXPLAIN验证SQL"""
        try:
            # 从记忆中获取数据库管理器
            db_manager = self.get_from_memory("database_manager")
            if not db_manager:
                self.logger.warning("数据库管理器不可用，跳过EXPLAIN验证")
                return {
                    "valid": True,
                    "warning": "无法执行EXPLAIN验证，仅进行语法检查"
                }
            
            # 使用EXPLAIN检查SQL
            explain_sql = f"EXPLAIN {sql}"
            result = db_manager.execute_query(explain_sql)
            
            return {
                "valid": True,
                "explain_result": result
            }
            
        except Exception as e:
            error_msg = str(e)
            suggestions = self._generate_suggestions(error_msg)
            
            return {
                "valid": False,
                "error": error_msg,
                "suggestions": suggestions
            }
    
    def _generate_suggestions(self, error_msg: str) -> List[str]:
        """根据错误信息生成建议"""
        suggestions = []
        error_lower = error_msg.lower()
        
        if "table" in error_lower and "doesn't exist" in error_lower:
            suggestions.append("检查表名是否正确")
            suggestions.append("确认表是否存在于数据库中")
        elif "column" in error_lower:
            suggestions.append("检查列名是否正确")
            suggestions.append("确认列是否存在于表中")
        elif "syntax" in error_lower:
            suggestions.append("检查SQL语法")
            suggestions.append("确认关键字使用是否正确")
        
        return suggestions
    
    async def _arun(self, sql: str, **kwargs) -> str:
        """异步执行（当前实现为同步）"""
        return self._run(sql, **kwargs)