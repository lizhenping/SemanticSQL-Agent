"""
SQL反思工具 - 分析执行结果并提供优化建议
"""

from typing import Dict, Any, List, Optional
from openai import OpenAI

from tools.base_tool import BaseTool, ToolParameter
from config.settings import Settings


class SQLReflectionTool(BaseTool):
    """SQL执行反思与优化工具"""
    
    def __init__(self, settings: Settings):
        super().__init__(settings)
        # 初始化LLM客户端（可选）
        self.llm_client = OpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key
        )
        self.model = settings.llm_model
        
        # 定义质量权重
        self.quality_weights = {
            "syntax_correctness": 0.3,
            "semantic_match": 0.3,
            "execution_success": 0.25,
            "result_relevance": 0.15
        }
    
    @property
    def name(self) -> str:
        return "sql_reflection"
    
    @property
    def description(self) -> str:
        return "分析SQL执行结果并提供质量评估和优化建议"
    
    @property
    def category(self) -> str:
        return "reflection"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="question",
                type="string",
                description="自然语言问题",
                required=True
            ),
            ToolParameter(
                name="sql",
                type="string",
                description="生成的SQL查询",
                required=True
            ),
            ToolParameter(
                name="validation_result",
                type="object",
                description="SQL验证结果",
                required=False,
                default={}
            ),
            ToolParameter(
                name="execution_result",
                type="object",
                description="SQL执行结果",
                required=False,
                default={}
            ),
            ToolParameter(
                name="use_llm",
                type="boolean",
                description="是否使用LLM进行深度分析",
                required=False,
                default=False
            )
        ]
    
    def _execute(self, question: str, sql: str,
                 validation_result: Dict[str, Any] = None,
                 execution_result: Dict[str, Any] = None,
                 use_llm: bool = False) -> Dict[str, Any]:
        """
        执行反思分析
        
        Returns:
            反思结果
        """
        reflection_result = {
            "quality_score": 0.0,
            "quality_breakdown": {},
            "issues": [],
            "suggestions": [],
            "optimized_sql": None,
            "confidence": 0.0
        }
        
        # 基于规则的分析
        rule_analysis = self._rule_based_analysis(
            question, sql, validation_result, execution_result
        )
        reflection_result.update(rule_analysis)
        
        # LLM深度分析（如果启用）
        if use_llm and self.llm_client:
            llm_analysis = self._llm_based_analysis(
                question, sql, validation_result, execution_result
            )
            # 合并LLM分析结果
            if llm_analysis:
                reflection_result["llm_analysis"] = llm_analysis
                reflection_result["suggestions"].extend(
                    llm_analysis.get("suggestions", [])
                )
                if llm_analysis.get("optimized_sql"):
                    reflection_result["optimized_sql"] = llm_analysis["optimized_sql"]
        
        # 生成改进建议
        improvements = self._generate_improvements(reflection_result)
        reflection_result["improvements"] = improvements
        
        # 计算最终置信度
        reflection_result["confidence"] = self._calculate_confidence(reflection_result)
        
        return reflection_result
    
    def _rule_based_analysis(self, question: str, sql: str,
                            validation_result: Dict[str, Any] = None,
                            execution_result: Dict[str, Any] = None) -> Dict[str, Any]:
        """基于规则的分析"""
        analysis = {
            "quality_score": 0.0,
            "quality_breakdown": {},
            "issues": [],
            "suggestions": []
        }
        
        # 1. 语法正确性评分
        syntax_score = self._evaluate_syntax(sql, validation_result)
        analysis["quality_breakdown"]["syntax_correctness"] = syntax_score
        
        # 2. 语义匹配度评分
        semantic_score = self._evaluate_semantic_match(question, sql)
        analysis["quality_breakdown"]["semantic_match"] = semantic_score
        
        # 3. 执行成功率评分
        execution_score = self._evaluate_execution(execution_result)
        analysis["quality_breakdown"]["execution_success"] = execution_score
        
        # 4. 结果相关性评分
        relevance_score = self._evaluate_result_relevance(
            question, execution_result
        )
        analysis["quality_breakdown"]["result_relevance"] = relevance_score
        
        # 计算加权总分
        total_score = 0.0
        for metric, weight in self.quality_weights.items():
            score = analysis["quality_breakdown"].get(metric, 0.0)
            total_score += score * weight
        
        analysis["quality_score"] = round(total_score, 2)
        
        # 识别问题
        analysis["issues"] = self._identify_issues(
            sql, validation_result, execution_result, analysis["quality_breakdown"]
        )
        
        # 生成建议
        analysis["suggestions"] = self._generate_suggestions(
            analysis["issues"], sql
        )
        
        return analysis
    
    def _evaluate_syntax(self, sql: str, validation_result: Dict[str, Any]) -> float:
        """评估语法正确性"""
        if not validation_result:
            # 基础语法检查
            sql_upper = sql.upper()
            if not any(keyword in sql_upper for keyword in ['SELECT', 'INSERT', 'UPDATE', 'DELETE']):
                return 0.0
            if sql.count('(') != sql.count(')'):
                return 20.0
            return 60.0  # 基础语法看起来正确
        
        # 基于验证结果评分
        if validation_result.get("valid", False):
            score = 100.0
            # 根据警告数量扣分
            warnings = len(validation_result.get("warnings", []))
            score -= warnings * 5
            return max(score, 70.0)
        else:
            # 有错误
            errors = len(validation_result.get("errors", []))
            return max(100.0 - errors * 20, 0.0)
    
    def _evaluate_semantic_match(self, question: str, sql: str) -> float:
        """评估语义匹配度"""
        score = 100.0
        question_lower = question.lower()
        sql_lower = sql.lower()
        
        # 检查关键词匹配
        if "统计" in question or "计算" in question or "总数" in question:
            if not any(func in sql_lower for func in ['count', 'sum', 'avg']):
                score -= 30
        
        if "排序" in question or "排名" in question:
            if 'order by' not in sql_lower:
                score -= 20
        
        if "分组" in question:
            if 'group by' not in sql_lower:
                score -= 20
        
        if "关联" in question or "相关" in question:
            if 'join' not in sql_lower:
                score -= 20
        
        # 检查时间相关
        time_keywords = ["本月", "今年", "最近", "昨天", "上周"]
        if any(keyword in question for keyword in time_keywords):
            if not any(func in sql_lower for func in ['date', 'time', 'now()', 'current']):
                score -= 15
        
        return max(score, 30.0)
    
    def _evaluate_execution(self, execution_result: Dict[str, Any]) -> float:
        """评估执行成功率"""
        if not execution_result:
            return 50.0  # 未执行
        
        if execution_result.get("success", False):
            score = 100.0
            
            # 根据执行时间调整
            exec_time = execution_result.get("execution_time", 0)
            if exec_time > 5:
                score -= 10
            elif exec_time > 2:
                score -= 5
            
            return score
        else:
            # 执行失败
            return 0.0
    
    def _evaluate_result_relevance(self, question: str, 
                                  execution_result: Dict[str, Any]) -> float:
        """评估结果相关性"""
        if not execution_result or not execution_result.get("success"):
            return 50.0
        
        score = 100.0
        
        # 检查结果数量
        row_count = execution_result.get("row_count", 0)
        
        # 如果问题要求特定数量
        if "所有" in question and row_count == 0:
            score -= 30
        elif "唯一" in question or "单个" in question:
            if row_count != 1:
                score -= 20
        
        # 检查结果是否为空
        if row_count == 0 and "不存在" not in question:
            score -= 20
        
        return max(score, 40.0)
    
    def _identify_issues(self, sql: str, validation_result: Dict[str, Any],
                        execution_result: Dict[str, Any],
                        quality_breakdown: Dict[str, float]) -> List[str]:
        """识别问题"""
        issues = []
        
        # 语法问题
        if quality_breakdown.get("syntax_correctness", 0) < 70:
            issues.append("SQL语法存在问题")
            if validation_result:
                issues.extend(validation_result.get("errors", []))
        
        # 语义问题
        if quality_breakdown.get("semantic_match", 0) < 70:
            issues.append("SQL与问题语义不完全匹配")
        
        # 执行问题
        if quality_breakdown.get("execution_success", 0) < 50:
            issues.append("SQL执行失败或性能较差")
            if execution_result and not execution_result.get("success"):
                error = execution_result.get("error", "Unknown error")
                issues.append(f"执行错误: {error}")
        
        # 结果问题
        if quality_breakdown.get("result_relevance", 0) < 60:
            issues.append("查询结果可能不符合预期")
        
        # 性能问题
        sql_upper = sql.upper()
        if 'SELECT *' in sql_upper:
            issues.append("使用了SELECT *，建议只选择需要的列")
        
        if sql_upper.count('JOIN') > 3:
            issues.append("JOIN操作过多，可能影响性能")
        
        return issues
    
    def _generate_suggestions(self, issues: List[str], sql: str) -> List[str]:
        """生成改进建议"""
        suggestions = []
        
        for issue in issues:
            if "语法" in issue:
                suggestions.append("检查SQL语法，确保括号匹配、关键字正确")
            elif "语义" in issue:
                suggestions.append("调整SQL逻辑以更好地匹配问题需求")
            elif "执行失败" in issue:
                suggestions.append("检查表名和字段名是否正确")
            elif "性能" in issue:
                suggestions.append("考虑添加索引或优化查询逻辑")
            elif "SELECT *" in issue:
                suggestions.append("明确指定需要的列名而不是使用SELECT *")
            elif "JOIN" in issue:
                suggestions.append("考虑是否可以减少JOIN操作或使用子查询")
        
        # 通用建议
        if not suggestions:
            if 'WHERE' not in sql.upper():
                suggestions.append("考虑添加WHERE条件以筛选数据")
            if 'LIMIT' not in sql.upper() and 'SELECT' in sql.upper():
                suggestions.append("考虑添加LIMIT限制返回行数")
        
        return suggestions
    
    def _llm_based_analysis(self, question: str, sql: str,
                           validation_result: Dict[str, Any],
                           execution_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """使用LLM进行深度分析"""
        try:
            prompt = f"""请分析以下SQL查询的质量：

问题：{question}
生成的SQL：{sql}

验证结果：{validation_result}
执行结果：{execution_result}

请从以下几个方面进行分析：
1. SQL语法是否正确
2. 是否正确回答了问题
3. 执行是否成功
4. 结果是否符合预期
5. 性能优化建议

如果有优化建议，请提供改进的SQL。"""
            
            response = self.llm_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个SQL专家，擅长分析和优化SQL查询。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            # 解析LLM响应
            llm_response = response.choices[0].message.content
            
            # 尝试提取结构化信息
            analysis = {
                "assessment": llm_response,
                "suggestions": [],
                "optimized_sql": None
            }
            
            # 简单的文本解析
            if "建议" in llm_response:
                suggestions_text = llm_response.split("建议")[1]
                suggestions = [s.strip() for s in suggestions_text.split("\n") if s.strip()]
                analysis["suggestions"] = suggestions[:3]
            
            # 检查是否有优化的SQL
            if "```sql" in llm_response:
                sql_match = llm_response.split("```sql")[1].split("```")[0]
                analysis["optimized_sql"] = sql_match.strip()
            
            return analysis
            
        except Exception as e:
            self.logger.warning(f"LLM analysis failed: {e}")
            return None
    
    def _generate_improvements(self, reflection_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成具体的改进方案"""
        improvements = []
        
        # 基于问题生成改进
        for issue in reflection_result.get("issues", []):
            improvement = {
                "issue": issue,
                "priority": self._get_issue_priority(issue),
                "action": self._get_improvement_action(issue)
            }
            improvements.append(improvement)
        
        # 排序改进建议
        improvements.sort(key=lambda x: x["priority"], reverse=True)
        
        return improvements
    
    def _get_issue_priority(self, issue: str) -> int:
        """获取问题优先级"""
        if "执行失败" in issue or "语法" in issue:
            return 3  # 高优先级
        elif "语义" in issue or "结果" in issue:
            return 2  # 中优先级
        else:
            return 1  # 低优先级
    
    def _get_improvement_action(self, issue: str) -> str:
        """获取改进行动"""
        action_map = {
            "语法": "修正SQL语法错误",
            "语义": "调整查询逻辑以匹配问题",
            "执行": "检查并修复执行错误",
            "性能": "优化查询性能",
            "SELECT *": "指定具体的列名",
            "JOIN": "优化JOIN操作"
        }
        
        for key, action in action_map.items():
            if key in issue:
                return action
        
        return "分析并解决问题"
    
    def _calculate_confidence(self, reflection_result: Dict[str, Any]) -> float:
        """计算置信度"""
        quality_score = reflection_result.get("quality_score", 0)
        issues_count = len(reflection_result.get("issues", []))
        
        # 基础置信度来自质量分数
        confidence = quality_score / 100.0
        
        # 根据问题数量调整
        if issues_count == 0:
            confidence *= 1.1
        elif issues_count > 3:
            confidence *= 0.8
        
        # 如果有LLM分析，提高置信度
        if "llm_analysis" in reflection_result:
            confidence *= 1.05
        
        return min(round(confidence, 2), 1.0)