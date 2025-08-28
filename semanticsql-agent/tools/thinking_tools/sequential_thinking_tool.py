"""深度思考工具（可选）"""

from tools.base import BaseSemanticSQLTool
from typing import Dict, Any, List, Optional
from models.generation_models import (
    ThinkingInput,
    ThinkingOutput,
    ThinkingStep
)
import logging

logger = logging.getLogger(__name__)


class SequentialThinkingTool(BaseSemanticSQLTool):
    """深度思考工具"""
    
    name = "deep_thinking"
    description = (
        "对复杂问题进行深度思考和分析。"
        "适用于需要多步推理、复杂逻辑分析或不确定如何处理的查询。"
        "会逐步分解问题并给出详细的思考过程。"
    )
    args_schema = ThinkingInput
    
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
            
            # 获取思考结果
            response = self.llm.invoke(prompt)
            thought_content = response.content
            
            # 记录思考步骤
            thought_step = {
                "step": step + 1,
                "thought": thought_content,
                "focus": self._extract_focus(thought_content)
            }
            thoughts.append(thought_step)
            
            # 更新理解
            current_understanding = self._update_understanding(
                current_understanding,
                thought_content
            )
            
            # 检查是否得出结论
            if self._has_conclusion(thought_content):
                logger.info(f"在第 {step + 1} 步得出结论")
                break
        
        # 生成最终分析
        final_analysis = self._generate_final_analysis(
            problem,
            thoughts,
            current_understanding
        )
        
        return {
            "problem": problem,
            "thinking_steps": thoughts,
            "understanding": current_understanding,
            "conclusion": final_analysis,
            "total_steps": len(thoughts)
        }
    
    def _build_thinking_prompt(
        self,
        problem: str,
        current_understanding: Dict[str, Any],
        previous_thoughts: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]],
        step_number: int
    ) -> str:
        """构建思考提示词"""
        prompt_parts = [
            f"问题：{problem}",
            f"\n当前是第 {step_number} 步思考。"
        ]
        
        # 添加之前的思考
        if previous_thoughts:
            prompt_parts.append("\n之前的思考：")
            for thought in previous_thoughts:
                prompt_parts.append(f"步骤 {thought['step']}: {thought['focus']}")
        
        # 添加当前理解
        if current_understanding["key_points"]:
            prompt_parts.append(f"\n已识别的关键点：")
            for point in current_understanding["key_points"]:
                prompt_parts.append(f"- {point}")
        
        if current_understanding["challenges"]:
            prompt_parts.append(f"\n识别的挑战：")
            for challenge in current_understanding["challenges"]:
                prompt_parts.append(f"- {challenge}")
        
        # 添加上下文
        if context:
            prompt_parts.append(f"\n相关上下文：")
            for key, value in context.items():
                if isinstance(value, (str, int, float)):
                    prompt_parts.append(f"- {key}: {value}")
        
        # 添加思考指导
        prompt_parts.extend([
            "\n请进行深入分析，考虑：",
            "1. 问题的核心需求是什么？",
            "2. 解决这个问题需要哪些步骤？",
            "3. 可能遇到的困难和解决方案？",
            "4. 是否有更好的方法？",
            "\n如果已经有明确的解决方案，请说明'结论：'并给出具体方案。"
        ])
        
        return "\n".join(prompt_parts)
    
    def _extract_focus(self, thought: str) -> str:
        """提取思考的焦点"""
        # 简单提取：取第一句或前100个字符
        lines = thought.split('\n')
        for line in lines:
            line = line.strip()
            if line and not line.startswith('步骤'):
                return line[:100] + "..." if len(line) > 100 else line
        
        return thought[:100] + "..." if len(thought) > 100 else thought
    
    def _update_understanding(
        self,
        current: Dict[str, Any],
        new_thought: str
    ) -> Dict[str, Any]:
        """更新理解"""
        updated = current.copy()
        
        # 提取关键点
        if "关键" in new_thought or "重要" in new_thought:
            lines = new_thought.split('\n')
            for line in lines:
                if any(keyword in line for keyword in ["关键", "重要", "核心"]):
                    point = line.strip().lstrip('-•*').strip()
                    if point and point not in updated["key_points"]:
                        updated["key_points"].append(point)
        
        # 提取挑战
        if "困难" in new_thought or "挑战" in new_thought or "问题" in new_thought:
            lines = new_thought.split('\n')
            for line in lines:
                if any(keyword in line for keyword in ["困难", "挑战", "问题"]):
                    challenge = line.strip().lstrip('-•*').strip()
                    if challenge and len(challenge) > 10 and challenge not in updated["challenges"]:
                        updated["challenges"].append(challenge)
        
        # 提取方法
        if "方法" in new_thought or "方案" in new_thought or "步骤" in new_thought:
            if not updated["approach"]:
                # 简单提取包含这些关键词的段落
                for line in new_thought.split('\n'):
                    if any(keyword in line for keyword in ["方法", "方案", "步骤"]):
                        updated["approach"] = line.strip()
                        break
        
        return updated
    
    def _has_conclusion(self, thought: str) -> bool:
        """检查是否得出结论"""
        conclusion_indicators = [
            "结论：", "结论是", "最终方案", "综上所述",
            "因此，", "所以，", "建议：", "解决方案："
        ]
        
        return any(indicator in thought for indicator in conclusion_indicators)
    
    def _generate_final_analysis(
        self,
        problem: str,
        thoughts: List[Dict[str, Any]],
        understanding: Dict[str, Any]
    ) -> str:
        """生成最终分析"""
        # 查找结论
        conclusion = None
        for thought in reversed(thoughts):
            if self._has_conclusion(thought["thought"]):
                # 提取结论部分
                content = thought["thought"]
                for indicator in ["结论：", "结论是", "最终方案", "解决方案："]:
                    if indicator in content:
                        idx = content.find(indicator)
                        conclusion = content[idx:].strip()
                        break
                if conclusion:
                    break
        
        if conclusion:
            return conclusion
        
        # 如果没有明确结论，生成总结
        summary_parts = [f"对于问题：{problem}"]
        
        if understanding["key_points"]:
            summary_parts.append(f"\n关键点：")
            for point in understanding["key_points"][:3]:
                summary_parts.append(f"- {point}")
        
        if understanding["approach"]:
            summary_parts.append(f"\n建议方法：{understanding['approach']}")
        
        if understanding["challenges"]:
            summary_parts.append(f"\n需要注意：")
            for challenge in understanding["challenges"][:2]:
                summary_parts.append(f"- {challenge}")
        
        summary_parts.append(f"\n经过 {len(thoughts)} 步思考，建议进一步分析具体需求后制定详细方案。")
        
        return "\n".join(summary_parts)