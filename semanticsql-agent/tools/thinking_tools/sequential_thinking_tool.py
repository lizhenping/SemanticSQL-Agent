"""
顺序思考工具 - 使用 LangChain 的链式推理
基于 LangChain 的标准组件实现
"""

from typing import Dict, Any, Type, Optional, List
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate, ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langchain.schema.runnable import RunnableSequence
from pydantic import BaseModel, Field
import json

from models.exceptions import ToolExecutionError
from prompts.manager import PromptManager
from ..base_tool import BaseSemanticSQLTool


class ThinkingStrategy(BaseModel):
    """思考策略输出格式"""
    analysis: str = Field(description="问题分析")
    root_cause: str = Field(description="根本原因")
    next_action: str = Field(description="建议的下一步行动")
    reasoning: str = Field(description="推理过程")
    confidence: float = Field(description="信心度", ge=0, le=1)


class SequentialThinkingInput(BaseModel):
    """顺序思考输入 - 从记忆中自动获取上下文"""
    problem_description: str = Field(description="问题描述")


class SequentialThinkingTool(BaseSemanticSQLTool):
    """使用 LangChain 链式推理的深度思考工具"""
    
    name: str = "sequential_thinking"
    description: str = "进行链式推理分析，制定问题解决策略。自动从记忆中获取上下文信息"
    args_schema: Type[BaseModel] = SequentialThinkingInput
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, 'thinking_chain', None)
        object.__setattr__(self, 'prompt_manager', PromptManager())
    
    def _create_thinking_chain(self, llm) -> RunnableSequence:
        """创建 LangChain 的思考链"""
        # 输出解析器
        parser = PydanticOutputParser(pydantic_object=ThinkingStrategy)
        
        # 使用统一的提示词管理
        try:
            prompt_content = self.prompt_manager.get_thinking_prompt("sequential_thinking_main")
            if not prompt_content:
                # 如果模板不存在，使用简化版本
                prompt_content = "分析问题：{problem_description}。请提供解决策略。"
            
            # 创建提示词模板
            thinking_prompt = PromptTemplate(
                input_variables=["problem_description", "context", "memory", "format_instructions"],
                template=prompt_content
            )
            
            # 添加格式说明
            thinking_prompt = thinking_prompt.partial(
                format_instructions=parser.get_format_instructions()
            )
            
            # 构建链
            return thinking_prompt | llm | parser
            
        except Exception as e:
            self.logger.warning(f"Failed to create thinking chain with template: {e}")
            # 后备方案：使用简化的提示词
            simple_prompt = PromptTemplate(
                input_variables=["problem_description"],
                template="请分析这个问题并提供解决建议：{problem_description}"
            )
            return simple_prompt | llm | parser
    
    def _run(self, problem_description: str, **kwargs) -> str:
        """执行链式思考"""
        try:
            # 从记忆中获取上下文信息
            context = self._gather_context_from_memory()
            
            # 从记忆中获取LLM
            llm = self.get_from_memory("llm")
            if not llm:
                # 如果没有LLM，使用简化分析
                return self._simple_analysis(problem_description, context)
            
            # 创建思考链（懒加载）
            if not self.thinking_chain:
                object.__setattr__(self, 'thinking_chain', self._create_thinking_chain(llm))
            
            # 执行思考链
            result = self.thinking_chain.invoke({
                "problem_description": problem_description,
                "context": self._format_dict(context.get("context", {})),
                "memory": self._format_dict(context.get("memory", {}))
            })
            
            # 构建结果
            thinking_result = {
                "analysis": result.analysis,
                "strategy": {
                    "next_action": result.next_action,
                    "reasoning": result.reasoning,
                    "root_cause": result.root_cause,
                    "confidence": result.confidence
                },
                "next_action": result.next_action,
                "reasoning": result.reasoning
            }
            
            # 保存思考结果到记忆
            self.save_to_memory("thinking_result", thinking_result)
            
            return json.dumps(thinking_result, ensure_ascii=False)
            
        except Exception as e:
            # 如果解析失败，尝试简单分析
            self.logger.warning(f"Structured parsing failed: {e}")
            fallback_result = self._fallback_analysis(problem_description, str(e))
            self.save_to_memory("thinking_result", fallback_result)
            return json.dumps(fallback_result, ensure_ascii=False)
    
    def _gather_context_from_memory(self) -> Dict[str, Any]:
        """从记忆中收集上下文信息"""
        context = {}
        memory = {}
        
        # 收集所有分析结果
        analysis_keys = [
            "schema_extraction", "domain_analysis", "field_analysis", 
            "table_meaning_analysis", "column_meaning_analysis", "er_analysis"
        ]
        
        for key in analysis_keys:
            data = self.get_from_memory(key)
            if data:
                memory[key] = data
        
        # 收集当前状态
        current_keys = [
            "current_question", "current_sql", "execution_result", "sql_reflection"
        ]
        
        for key in current_keys:
            data = self.get_from_memory(key)
            if data:
                context[key] = data
        
        return {"context": context, "memory": memory}
    
    def _simple_analysis(self, problem_description: str, context: Dict[str, Any]) -> str:
        """简化分析（当LLM不可用时）"""
        # 基于规则的简单分析
        problem_lower = problem_description.lower()
        
        if "sql" in problem_lower and "error" in problem_lower:
            next_action = "sql_generation"
            analysis = "SQL生成或执行出现错误，建议重新生成SQL"
        elif "schema" in problem_lower or "database" in problem_lower:
            next_action = "schema_extraction"
            analysis = "数据库结构相关问题，建议重新提取schema"
        elif "question" in problem_lower:
            next_action = "question_generation"
            analysis = "问题生成相关，建议重新生成问题"
        else:
            next_action = "manual_intervention"
            analysis = "无法自动分析，需要人工介入"
        
        result = {
            "analysis": analysis,
            "strategy": {
                "next_action": next_action,
                "reasoning": f"基于关键词分析：{problem_lower[:50]}...",
                "root_cause": "未知原因，需要更详细分析",
                "confidence": 0.3
            },
            "next_action": next_action,
            "reasoning": analysis
        }
        
        return json.dumps(result, ensure_ascii=False)
    
    def _format_dict(self, d: Dict[str, Any]) -> str:
        """格式化字典为可读字符串"""
        if not d:
            return "无"
        
        lines = []
        for key, value in d.items():
            if isinstance(value, dict):
                lines.append(f"{key}: {len(value)} 项")
            elif isinstance(value, list):
                lines.append(f"{key}: {len(value)} 个元素")
            else:
                lines.append(f"{key}: {str(value)[:100]}")
        
        return "\n".join(lines)
    
    def _fallback_analysis(self, problem: str, error: str) -> Dict[str, Any]:
        """后备分析方法"""
        # 尝试从记忆中获取LLM进行分析
        llm = self.get_from_memory("llm")
        
        if llm:
            try:
                # 使用统一的提示词管理
                prompt_content = self.prompt_manager.get_thinking_prompt("fallback_analysis")
                
                if prompt_content:
                    simple_prompt = PromptTemplate(
                        input_variables=["problem", "error"],
                        template=prompt_content
                    )
                else:
                    # 后备提示词
                    simple_prompt = PromptTemplate(
                        input_variables=["problem", "error"],
                        template="问题：{problem}\n错误：{error}\n\n请简要分析这个问题并建议下一步行动。"
                    )
                
                chain = LLMChain(llm=llm, prompt=simple_prompt)
                analysis = chain.run(problem=problem, error=error)
                
                return {
                    "analysis": analysis,
                    "strategy": {
                        "next_action": "manual_intervention",
                        "reasoning": "需要进一步分析",
                        "root_cause": "解析失败，需要人工检查",
                        "confidence": 0.5
                    },
                    "next_action": "manual_intervention",
                    "reasoning": analysis[:200]
                }
            except Exception as e:
                self.logger.warning(f"LLM fallback analysis failed: {e}")
        
        # 如果LLM不可用或失败，使用规则分析
        return self._simple_analysis(problem, {"context": {}, "memory": {}})
    
    async def _arun(self, problem_description: str, **kwargs) -> str:
        """异步执行"""
        # 当前实现为同步调用，可以在未来添加真正的异步支持
        return self._run(problem_description, **kwargs)