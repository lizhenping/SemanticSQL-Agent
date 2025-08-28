"""深度思考工具（可选）"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import logging

from .base import BaseSemanticSQLTool

logger = logging.getLogger(__name__)


@dataclass
class ThinkingStep:
    """思考步骤"""
    step_number: int
    thought: str
    insights: List[str]
    next_action: Optional[str] = None


class SequentialThinkingTool(BaseSemanticSQLTool):
    """深度思考工具"""
    
    name = "deep_thinking"
    description = (
        "对复杂问题进行深度思考和分析。"
        "适用于需要多步推理、复杂逻辑分析或不确定如何处理的查询。"
        "会逐步分解问题并给出详细的思考过程。"
    )
    
    def execute(
        self,
        problem: str,
        context: Optional[Dict[str, Any]] = None,
        max_steps: int = 3
    ) -> Dict[str, Any]:
        """执行深度思考"""
        thoughts = []
        current_understanding = {
            "problem": problem,
            "key_points": [],
            "approach": None,
            "challenges": []
        }
        
        for step in range(max_steps):
            # 构建思考提示词
            prompt = self._build_thinking_prompt(
                problem,
                current_understanding,
                thoughts,
                context,
                step + 1
            )
            
            # 调用 LLM
            response = self.llm.invoke(prompt)
            
            # 解析思考结果
            step_result = self._parse_thinking_step(response.content, step + 1)
            thoughts.append(step_result)
            
            # 更新当前理解
            self._update_understanding(current_understanding, step_result)
            
            # 如果找到了清晰的解决方案，提前结束
            if self._has_clear_solution(step_result):
                break
        
        # 生成最终输出
        output = {
            "problem": problem,
            "thinking_steps": [
                {
                    "step": t.step_number,
                    "thought": t.thought,
                    "insights": t.insights,
                    "next_action": t.next_action
                }
                for t in thoughts
            ],
            "final_understanding": current_understanding,
            "recommendation": self._generate_recommendation(thoughts, current_understanding)
        }
        
        return output
    
    def _build_thinking_prompt(
        self,
        problem: str,
        understanding: Dict[str, Any],
        previous_thoughts: List[ThinkingStep],
        context: Optional[Dict[str, Any]],
        step_number: int
    ) -> str:
        """构建思考提示词"""
        prompt_parts = [
            f"请对以下问题进行第 {step_number} 步深度思考：\n",
            f"问题：{problem}\n"
        ]
        
        # 添加上下文
        if context:
            prompt_parts.append("\n相关上下文：")
            if context.get("schema_info"):
                prompt_parts.append("- 已获取数据库结构信息")
            if context.get("domain_analysis"):
                prompt_parts.append("- 已完成业务领域分析")
            if context.get("previous_queries"):
                prompt_parts.append(f"- 有 {len(context['previous_queries'])} 个相关历史查询")
        
        # 添加之前的思考
        if previous_thoughts:
            prompt_parts.append("\n之前的思考：")
            for thought in previous_thoughts:
                prompt_parts.append(f"- 步骤 {thought.step_number}: {thought.thought[:100]}...")
        
        # 添加当前理解
        if understanding["key_points"]:
            prompt_parts.append("\n当前理解的关键点：")
            for point in understanding["key_points"]:
                prompt_parts.append(f"- {point}")
        
        # 思考指导
        prompt_parts.extend([
            "\n请进行思考并提供：",
            "1. 对问题的深入分析",
            "2. 识别出的关键洞察",
            "3. 建议的下一步行动（如果有）",
            "\n注意：保持思考的连贯性，每一步都要有新的进展。"
        ])
        
        return "\n".join(prompt_parts)
    
    def _parse_thinking_step(self, content: str, step_number: int) -> ThinkingStep:
        """解析思考步骤"""
        # 简单的文本解析
        lines = content.strip().split('\n')
        
        # 提取主要思考
        thought = ""
        insights = []
        next_action = None
        
        current_section = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 识别段落标题
            if "分析" in line or "思考" in line:
                current_section = "thought"
            elif "洞察" in line or "发现" in line or "关键" in line:
                current_section = "insights"
            elif "建议" in line or "下一步" in line or "行动" in line:
                current_section = "next_action"
            elif line.startswith("-") or line.startswith("•") or line.startswith("*"):
                # 列表项
                clean_line = line.lstrip("-•* ").strip()
                if current_section == "insights":
                    insights.append(clean_line)
                elif current_section == "next_action" and not next_action:
                    next_action = clean_line
            else:
                # 普通文本
                if current_section == "thought" or not thought:
                    thought += line + " "
        
        # 如果没有解析出内容，使用整个响应作为思考
        if not thought:
            thought = content.strip()
        
        return ThinkingStep(
            step_number=step_number,
            thought=thought.strip(),
            insights=insights,
            next_action=next_action
        )
    
    def _update_understanding(
        self,
        understanding: Dict[str, Any],
        step_result: ThinkingStep
    ) -> None:
        """更新当前理解"""
        # 添加新的关键点
        for insight in step_result.insights:
            if insight not in understanding["key_points"]:
                understanding["key_points"].append(insight)
        
        # 更新方法
        if step_result.next_action and not understanding["approach"]:
            understanding["approach"] = step_result.next_action
        
        # 识别挑战
        if "困难" in step_result.thought or "挑战" in step_result.thought:
            challenge = f"步骤 {step_result.step_number} 识别的挑战"
            understanding["challenges"].append(challenge)
    
    def _has_clear_solution(self, step_result: ThinkingStep) -> bool:
        """判断是否已经有清晰的解决方案"""
        # 简单判断：如果有明确的下一步行动，且思考中包含解决方案相关词汇
        if not step_result.next_action:
            return False
            
        solution_keywords = ["解决", "方案", "可以", "应该", "建议执行", "明确"]
        thought_lower = step_result.thought.lower()
        
        return any(keyword in thought_lower for keyword in solution_keywords)
    
    def _generate_recommendation(
        self,
        thoughts: List[ThinkingStep],
        understanding: Dict[str, Any]
    ) -> str:
        """生成最终建议"""
        if not thoughts:
            return "需要更多信息来分析这个问题。"
        
        # 基于最后的思考步骤生成建议
        last_thought = thoughts[-1]
        
        if last_thought.next_action:
            recommendation = f"建议：{last_thought.next_action}"
        elif understanding["approach"]:
            recommendation = f"建议采用以下方法：{understanding['approach']}"
        else:
            # 基于洞察生成建议
            if understanding["key_points"]:
                recommendation = "基于分析，建议关注以下要点：\n"
                for i, point in enumerate(understanding["key_points"][:3], 1):
                    recommendation += f"{i}. {point}\n"
            else:
                recommendation = "这个问题需要进一步分析，建议先明确具体需求。"
        
        return recommendation.strip()