"""
SQL反思工具 - 分析执行结果并提供优化建议
基于 LangChain BaseTool
"""

from typing import Dict, Any, Type, List, Optional
from langchain.tools import BaseTool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from models.exceptions import ToolExecutionError


class SQLReflectionInput(BaseModel):
    """SQL反思输入"""
    question: str = Field(description="自然语言问题")
    sql: str = Field(description="生成的SQL")
    execution_result: Dict[str, Any] = Field(description="SQL执行结果")
    memory: Dict[str, Any] = Field(description="包含数据库分析结果的记忆")


class SQLReflectionTool(BaseTool):
    """SQL执行反思与优化工具"""
    
    name: str = "sql_reflection"
    description: str = "分析SQL执行结果，识别问题来源并建议下一步行动"
    args_schema: Type[BaseModel] = SQLReflectionInput
    
    def __init__(self, llm: ChatOpenAI):
        super().__init__()
        object.__setattr__(self, 'llm', llm)
        
        # 定义质量权重，使用object.__setattr__避开Pydantic验证
        object.__setattr__(self, 'quality_weights', {
            "syntax_correctness": 0.3,
            "semantic_match": 0.3,
            "execution_success": 0.25,
            "result_relevance": 0.15
        })
    
    def _run(
        self,
        question: str,
        sql: str,
        execution_result: Dict[str, Any],
        memory: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行SQL反思"""
        try:
            # 分析执行结果
            execution_success = execution_result.get("success", False)
            error_message = execution_result.get("error", "")
            result_data = execution_result.get("data", [])
            
            # 初始化反思结果
            reflection = {
                "needs_revision": False,
                "problem_source": None,
                "root_cause_analysis": "",
                "recommended_action": None,
                "quality_scores": {},
                "suggestions": []
            }
            
            # 1. 如果执行失败，分析失败原因
            if not execution_success:
                reflection["needs_revision"] = True
                failure_analysis = self._analyze_execution_failure(
                    sql, error_message, memory
                )
                reflection.update(failure_analysis)
            
            # 2. 如果执行成功但结果为空
            elif not result_data:
                reflection["needs_revision"] = True
                empty_analysis = self._analyze_empty_result(
                    question, sql, memory
                )
                reflection.update(empty_analysis)
            
            # 3. 执行成功且有结果，评估质量
            else:
                quality_analysis = self._analyze_result_quality(
                    question, sql, result_data, memory
                )
                reflection.update(quality_analysis)
            
            # 4. 计算整体质量分数
            reflection["overall_score"] = self._calculate_overall_score(
                reflection["quality_scores"]
            )
            
            return reflection
            
        except Exception as e:
            raise ToolExecutionError(
                tool_name=self.name,
                reason=f"SQL反思失败: {str(e)}"
            )
    
    def _analyze_execution_failure(
        self,
        sql: str,
        error_message: str,
        memory: Dict[str, Any]
    ) -> Dict[str, Any]:
        """分析执行失败原因"""
        error_lower = error_message.lower()
        
        # 识别错误类型
        if "table" in error_lower and "doesn't exist" in error_lower:
            return {
                "problem_source": "sql_generation",
                "root_cause_analysis": "SQL引用了不存在的表",
                "recommended_action": "sql_generation",
                "suggestions": ["检查表名拼写", "确认表是否存在于数据库中"]
            }
        
        elif "column" in error_lower and ("unknown" in error_lower or "doesn't exist" in error_lower):
            return {
                "problem_source": "sql_generation",
                "root_cause_analysis": "SQL引用了不存在的列",
                "recommended_action": "sql_generation",
                "suggestions": ["检查列名拼写", "确认列是否存在于表中"]
            }
        
        elif "syntax" in error_lower:
            return {
                "problem_source": "sql_generation",
                "root_cause_analysis": "SQL语法错误",
                "recommended_action": "sql_generation",
                "suggestions": ["检查SQL语法", "确认是否符合MySQL语法规范"]
            }
        
        elif "join" in error_lower or "on clause" in error_lower:
            return {
                "problem_source": "sql_generation",
                "root_cause_analysis": "JOIN条件错误",
                "recommended_action": "sql_generation",
                "suggestions": ["检查JOIN条件", "确认关联字段是否正确"]
            }
        
        elif "ambiguous" in error_lower:
            return {
                "problem_source": "sql_generation",
                "root_cause_analysis": "列名歧义，需要指定表名",
                "recommended_action": "sql_generation",
                "suggestions": ["为列名添加表前缀", "使用表别名"]
            }
        
        else:
            # 使用LLM分析复杂错误
            return self._analyze_complex_error_with_llm(sql, error_message, memory)
    
    def _analyze_empty_result(
        self,
        question: str,
        sql: str,
        memory: Dict[str, Any]
    ) -> Dict[str, Any]:
        """分析空结果原因"""
        # 基于LLM分析为什么没有结果
        prompt = f"""分析以下SQL查询返回空结果的原因：

问题：{question}
SQL：{sql}

可能的原因：
1. WHERE条件过于严格
2. JOIN条件不匹配
3. 数据确实不存在
4. 时间范围问题

请分析最可能的原因。"""

        try:
            response = self.llm.invoke(prompt)
            analysis = response.content.strip()
            
            # 简单解析分析结果
            if "WHERE条件" in analysis or "条件过于严格" in analysis:
                return {
                    "problem_source": "sql_generation",
                    "root_cause_analysis": "WHERE条件可能过于严格",
                    "recommended_action": "sql_generation",
                    "suggestions": ["放宽WHERE条件", "检查筛选条件是否合理"]
                }
            elif "JOIN" in analysis:
                return {
                    "problem_source": "sql_generation",
                    "root_cause_analysis": "JOIN条件可能不正确",
                    "recommended_action": "sql_generation",
                    "suggestions": ["检查JOIN条件", "确认表之间的关联关系"]
                }
            else:
                return {
                    "problem_source": "question_generation",
                    "root_cause_analysis": "问题可能不适合当前数据",
                    "recommended_action": "question_generation",
                    "suggestions": ["生成更适合数据的问题", "检查问题的合理性"]
                }
                
        except:
            return {
                "problem_source": "unknown",
                "root_cause_analysis": "查询返回空结果",
                "recommended_action": "sequential_thinking",
                "suggestions": ["需要深入分析问题和数据"]
            }
    
    def _analyze_result_quality(
        self,
        question: str,
        sql: str,
        result_data: List[Dict[str, Any]],
        memory: Dict[str, Any]
    ) -> Dict[str, Any]:
        """分析结果质量"""
        quality_scores = {
            "syntax_correctness": 1.0,  # 执行成功说明语法正确
            "execution_success": 1.0,   # 已经执行成功
            "semantic_match": 0.0,
            "result_relevance": 0.0
        }
        
        # 使用LLM评估语义匹配和结果相关性
        prompt = f"""评估SQL查询结果的质量：

用户问题：{question}
生成的SQL：{sql}
返回结果样例（前3行）：{result_data[:3]}

请评估：
1. SQL是否正确回答了用户的问题？（0-1分）
2. 结果是否相关且有意义？（0-1分）
3. 是否有改进空间？

格式：
语义匹配分数：X.X
结果相关性分数：X.X
改进建议：...
"""

        try:
            response = self.llm.invoke(prompt)
            content = response.content.strip()
            
            # 解析分数
            import re
            semantic_match = re.search(r'语义匹配分数[：:]\s*([\d.]+)', content)
            relevance_match = re.search(r'结果相关性分数[：:]\s*([\d.]+)', content)
            
            if semantic_match:
                quality_scores["semantic_match"] = float(semantic_match.group(1))
            if relevance_match:
                quality_scores["result_relevance"] = float(relevance_match.group(1))
            
            # 判断是否需要修订
            overall_score = self._calculate_overall_score(quality_scores)
            needs_revision = overall_score < 0.7
            
            # 提取改进建议
            suggestions = []
            if "改进建议" in content:
                suggestion_text = content.split("改进建议")[1].strip()
                suggestions = [s.strip() for s in suggestion_text.split("\n") if s.strip()]
            
            return {
                "needs_revision": needs_revision,
                "quality_scores": quality_scores,
                "problem_source": "sql_generation" if needs_revision else None,
                "root_cause_analysis": "SQL质量评分较低" if needs_revision else "SQL质量良好",
                "recommended_action": "sql_generation" if needs_revision else None,
                "suggestions": suggestions
            }
            
        except Exception as e:
            # 降级处理
            return {
                "needs_revision": False,
                "quality_scores": quality_scores,
                "suggestions": []
            }
    
    def _analyze_complex_error_with_llm(
        self,
        sql: str,
        error_message: str,
        memory: Dict[str, Any]
    ) -> Dict[str, Any]:
        """使用LLM分析复杂错误"""
        db_analysis = memory.get("db_analysis", {})
        schema_info = db_analysis.get("schema_info", {})
        
        # 构建简化的schema信息
        schema_summary = []
        for table_name, table_info in schema_info.get("tables", {}).items():
            columns = [col["name"] for col in table_info.get("columns", [])]
            schema_summary.append(f"{table_name}: {', '.join(columns[:10])}")
        
        prompt = f"""分析SQL执行错误：

SQL：{sql}
错误信息：{error_message}

数据库表结构：
{chr(10).join(schema_summary[:10])}

请分析：
1. 错误的根本原因
2. 问题出在哪个步骤（数据库分析、问题生成、SQL生成）
3. 建议采取什么行动
"""

        try:
            response = self.llm.invoke(prompt)
            analysis = response.content.strip()
            
            # 简单解析分析结果
            if "数据库分析" in analysis:
                return {
                    "problem_source": "schema_extraction",
                    "root_cause_analysis": "数据库结构分析可能有误",
                    "recommended_action": "schema_extraction",
                    "suggestions": ["重新分析数据库结构"]
                }
            elif "问题生成" in analysis:
                return {
                    "problem_source": "question_generation",
                    "root_cause_analysis": "生成的问题可能不合理",
                    "recommended_action": "question_generation",
                    "suggestions": ["生成更合理的问题"]
                }
            else:
                return {
                    "problem_source": "sql_generation",
                    "root_cause_analysis": error_message,
                    "recommended_action": "sql_generation",
                    "suggestions": ["修正SQL语句"]
                }
                
        except:
            return {
                "problem_source": "unknown",
                "root_cause_analysis": error_message,
                "recommended_action": "sequential_thinking",
                "suggestions": ["需要人工介入分析"]
            }
    
    def _calculate_overall_score(self, quality_scores: Dict[str, float]) -> float:
        """计算整体质量分数"""
        total_score = 0.0
        total_weight = 0.0
        
        for metric, weight in self.quality_weights.items():
            if metric in quality_scores:
                total_score += quality_scores[metric] * weight
                total_weight += weight
        
        return total_score / total_weight if total_weight > 0 else 0.0
    
    async def _arun(
        self,
        question: str,
        sql: str,
        execution_result: Dict[str, Any],
        memory: Dict[str, Any]
    ) -> Dict[str, Any]:
        """异步执行（当前实现为同步）"""
        return self._run(question, sql, execution_result, memory)