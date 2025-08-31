"""
Sequential thinking tool for deep analysis
Based on the design specification - provides structured thinking capabilities
"""

from typing import Dict, Any, List, Optional
from tools.base_tool import BaseTool
from models.schemas import ToolInput, ToolOutput


class SequentialThinkingInput(ToolInput):
    """Input for sequential thinking tool"""
    context: Dict[str, Any]
    problem: str
    thinking_steps: Optional[List[str]] = None


class SequentialThinkingOutput(ToolOutput):
    """Output for sequential thinking tool"""
    reasoning_chain: List[Dict[str, str]]
    conclusion: str
    confidence: float
    next_actions: List[str]


class SequentialThinkingTool(BaseTool):
    """Sequential thinking tool for structured analysis"""
    
    @property
    def name(self) -> str:
        return "sequential_thinking"
    
    @property
    def description(self) -> str:
        return "Perform structured sequential thinking and analysis"
    
    @property
    def category(self) -> str:
        return "thinking"
    
    @property
    def parameters(self) -> List:
        from tools.base_tool import ToolParameter
        return [
            ToolParameter(
                name="context",
                type="object",
                description="当前上下文信息，包括已分析的数据库结构、领域信息等",
                required=True
            ),
            ToolParameter(
                name="problem",
                type="string",
                description="需要分析和思考的问题或情况",
                required=True
            ),
            ToolParameter(
                name="thinking_steps",
                type="array",
                description="预定义的思考步骤（可选）",
                required=False,
                default=None
            )
        ]
    
    def _execute(self, **kwargs) -> Dict[str, Any]:
        """Execute thinking tool"""
        return self.run(**kwargs)
    
    def run(self, context: Dict[str, Any], problem: str, 
            thinking_steps: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Perform sequential thinking analysis
        
        Args:
            context: Current context information
            problem: Problem to analyze
            thinking_steps: Optional predefined thinking steps
            
        Returns:
            Thinking result with reasoning chain
        """
        try:
            # Default thinking steps if not provided
            if not thinking_steps:
                thinking_steps = [
                    "分析当前情况",
                    "识别关键问题", 
                    "评估可能的解决方案",
                    "选择最佳行动方案",
                    "制定执行计划"
                ]
            
            reasoning_chain = []
            
            # Execute each thinking step
            for i, step in enumerate(thinking_steps, 1):
                reasoning = self._execute_thinking_step(
                    step, problem, context, i, len(thinking_steps)
                )
                reasoning_chain.append({
                    "step": step,
                    "reasoning": reasoning,
                    "step_number": i
                })
            
            # Generate final conclusion
            conclusion = self._generate_conclusion(reasoning_chain, problem)
            
            # Determine confidence level
            confidence = self._calculate_confidence(reasoning_chain, context)
            
            # Suggest next actions
            next_actions = self._suggest_next_actions(reasoning_chain, context)
            
            return {
                "success": True,
                "data": {
                    "reasoning_chain": reasoning_chain,
                    "conclusion": conclusion,
                    "confidence": confidence,
                    "next_actions": next_actions,
                    "problem": problem
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def _execute_thinking_step(self, step: str, problem: str, 
                             context: Dict[str, Any], step_num: int, 
                             total_steps: int) -> str:
        """Execute a single thinking step"""
        
        # Analyze based on step type
        if "分析当前情况" in step:
            return self._analyze_current_situation(context, problem)
        elif "识别关键问题" in step:
            return self._identify_key_issues(context, problem)
        elif "评估可能的解决方案" in step:
            return self._evaluate_solutions(context, problem)
        elif "选择最佳行动方案" in step:
            return self._select_best_action(context, problem)
        elif "制定执行计划" in step:
            return self._create_execution_plan(context, problem)
        else:
            # Generic thinking step
            return self._generic_thinking(step, context, problem)
    
    def _analyze_current_situation(self, context: Dict[str, Any], problem: str) -> str:
        """Analyze current situation"""
        analysis = []
        
        # Analyze available data
        if "schema" in context:
            schema_info = context["schema"]
            table_count = len(schema_info.get("tables", {}))
            analysis.append(f"数据库包含{table_count}个表")
        
        # Analyze problem complexity
        if "复杂" in problem or "统计" in problem:
            analysis.append("问题涉及复杂查询或统计分析")
        elif "查询" in problem:
            analysis.append("问题涉及基础查询操作")
        
        # Analyze available tools
        if "tools" in context:
            tools = context["tools"]
            analysis.append(f"可用工具: {', '.join(tools)}")
        
        return "; ".join(analysis) if analysis else "当前情况分析中..."
    
    def _identify_key_issues(self, context: Dict[str, Any], problem: str) -> str:
        """Identify key issues"""
        issues = []
        
        # Check for data requirements
        if "表" in problem:
            issues.append("需要确定涉及的数据表")
        
        # Check for query type
        if "统计" in problem or "数量" in problem:
            issues.append("需要生成聚合查询")
        elif "关联" in problem:
            issues.append("需要处理表关联")
        else:
            issues.append("需要确定查询类型")
        
        # Check for complexity
        if "复杂" in problem:
            issues.append("查询复杂度较高，需要仔细规划")
        
        return "; ".join(issues) if issues else "关键问题识别中..."
    
    def _evaluate_solutions(self, context: Dict[str, Any], problem: str) -> str:
        """Evaluate possible solutions"""
        solutions = []
        
        # Direct SQL generation
        solutions.append("方案1: 直接生成SQL查询")
        
        # Schema analysis first
        if "schema" not in context:
            solutions.append("方案2: 先分析数据库结构，再生成查询")
        
        # Multi-step approach
        if "复杂" in problem:
            solutions.append("方案3: 分步骤处理，先简单查询再优化")
        
        return "; ".join(solutions)
    
    def _select_best_action(self, context: Dict[str, Any], problem: str) -> str:
        """Select best action plan"""
        # Simple heuristic-based selection
        if "schema" not in context:
            return "最佳方案: 先提取数据库结构信息，再生成SQL查询"
        elif "复杂" in problem:
            return "最佳方案: 使用多步骤方法，确保SQL正确性"
        else:
            return "最佳方案: 直接生成SQL查询并验证"
    
    def _create_execution_plan(self, context: Dict[str, Any], problem: str) -> str:
        """Create execution plan"""
        plan_steps = []
        
        # Check if schema analysis is needed
        if "schema" not in context:
            plan_steps.append("1. 提取数据库结构")
        
        # Add SQL generation step
        plan_steps.append("2. 生成SQL查询")
        
        # Add validation step
        plan_steps.append("3. 验证SQL语法和逻辑")
        
        # Add execution step
        plan_steps.append("4. 执行SQL并获取结果")
        
        return "; ".join(plan_steps)
    
    def _generic_thinking(self, step: str, context: Dict[str, Any], problem: str) -> str:
        """Generic thinking for custom steps"""
        return f"执行思考步骤: {step}"
    
    def _generate_conclusion(self, reasoning_chain: List[Dict], problem: str) -> str:
        """Generate final conclusion from reasoning chain"""
        # Simple conclusion based on the last reasoning step
        if reasoning_chain:
            last_reasoning = reasoning_chain[-1]["reasoning"]
            return f"基于分析，{last_reasoning}"
        else:
            return "需要进一步分析"
    
    def _calculate_confidence(self, reasoning_chain: List[Dict], context: Dict[str, Any]) -> float:
        """Calculate confidence level"""
        base_confidence = 0.7
        
        # Increase confidence if we have schema info
        if "schema" in context:
            base_confidence += 0.1
        
        # Increase confidence if reasoning chain is complete
        if len(reasoning_chain) >= 3:
            base_confidence += 0.1
        
        # Decrease confidence if there are unknowns
        reasoning_text = " ".join([r["reasoning"] for r in reasoning_chain])
        if "未知" in reasoning_text or "不确定" in reasoning_text:
            base_confidence -= 0.2
        
        return max(0.1, min(1.0, base_confidence))
    
    def _suggest_next_actions(self, reasoning_chain: List[Dict], context: Dict[str, Any]) -> List[str]:
        """Suggest next actions based on reasoning"""
        actions = []
        
        # Check if schema extraction is needed
        if "schema" not in context:
            actions.append("提取数据库结构信息")
        
        # Always suggest SQL generation as core action
        actions.append("生成SQL查询")
        
        # Suggest validation
        actions.append("验证SQL正确性")
        
        # Suggest execution
        actions.append("执行SQL查询")
        
        return actions