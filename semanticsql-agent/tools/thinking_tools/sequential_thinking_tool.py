"""
顺序思考工具 - 使用 LangChain 的链式推理
基于 LangChain 的标准组件实现
"""

from typing import Dict, Any, Type, Optional, List
from langchain.tools import BaseTool
from langchain_openai import ChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate, ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langchain.schema.runnable import RunnableSequence
from pydantic import BaseModel, Field, ConfigDict

from models.exceptions import ToolExecutionError


class ThinkingStrategy(BaseModel):
    """思考策略输出格式"""
    analysis: str = Field(description="问题分析")
    root_cause: str = Field(description="根本原因")
    next_action: str = Field(description="建议的下一步行动")
    reasoning: str = Field(description="推理过程")
    confidence: float = Field(description="信心度", ge=0, le=1)


class SequentialThinkingInput(BaseModel):
    """顺序思考输入"""
    problem_description: str = Field(description="问题描述")
    context: Dict[str, Any] = Field(default_factory=dict, description="上下文信息")
    memory: Dict[str, Any] = Field(default_factory=dict, description="包含数据库分析结果的记忆")


class SequentialThinkingTool(BaseTool):
    """使用 LangChain 链式推理的深度思考工具"""
    
    name: str = "sequential_thinking"
    description: str = "进行链式推理分析，制定问题解决策略"
    args_schema: Type[BaseModel] = SequentialThinkingInput
    
    # 定义必需的字段
    llm: Optional[ChatOpenAI] = Field(default=None, exclude=True)
    thinking_chain: Optional[RunnableSequence] = Field(default=None, exclude=True)
    
    # Pydantic v2配置
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    def __init__(self, llm: ChatOpenAI):
        super().__init__()
        self.llm = llm
        self.thinking_chain = self._create_thinking_chain()
    
    def _create_thinking_chain(self) -> RunnableSequence:
        """创建 LangChain 的思考链"""
        # 输出解析器
        parser = PydanticOutputParser(pydantic_object=ThinkingStrategy)
        
        # 定义多步推理的提示词
        thinking_prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个专业的问题分析专家。
请对给定的问题进行深入分析，并提供解决策略。

{format_instructions}"""),
            ("human", """问题描述：{problem_description}

上下文信息：
{context}

数据库分析记忆：
{memory}

请进行以下步骤的分析：
1. 理解问题的本质
2. 分析可能的原因
3. 推理最佳解决方案
4. 确定下一步行动

注意：next_action 应该是以下之一：
- schema_extraction: 重新分析数据库结构
- domain_analysis: 重新分析业务领域
- field_classification: 重新分类字段
- column_meaning_analysis: 重新分析列含义
- table_meaning_analysis: 重新分析表含义
- er_analysis: 重新分析实体关系
- question_generation: 重新生成问题
- sql_generation: 重新生成SQL
- manual_intervention: 需要人工介入""")
        ])
        
        # 添加格式说明
        thinking_prompt = thinking_prompt.partial(
            format_instructions=parser.get_format_instructions()
        )
        
        # 构建链
        return thinking_prompt | self.llm | parser
    
    def _run(
        self,
        problem_description: str,
        context: Dict[str, Any] = None,
        memory: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """执行链式思考"""
        try:
            # 准备输入
            if context is None:
                context = {}
            if memory is None:
                memory = {}
            
            # 将字典转换为字符串以便在提示词中使用
            context_str = self._format_dict(context)
            memory_str = self._format_dict(memory)
            
            # 执行思考链
            result = self.thinking_chain.invoke({
                "problem_description": problem_description,
                "context": context_str,
                "memory": memory_str
            })
            
            # 返回结构化结果
            return {
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
            
        except Exception as e:
            # 如果解析失败，尝试简单分析
            self.logger.warning(f"Structured parsing failed: {e}")
            return self._fallback_analysis(problem_description, str(e))
    
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
        # 使用简单的 LLMChain 进行分析
        simple_prompt = PromptTemplate(
            input_variables=["problem", "error"],
            template="""问题：{problem}
错误：{error}

请简要分析这个问题并建议下一步行动。"""
        )
        
        chain = LLMChain(llm=self.llm, prompt=simple_prompt)
        analysis = chain.run(problem=problem, error=error)
        
        return {
            "analysis": analysis,
            "strategy": {
                "next_action": "manual_intervention",
                "reasoning": "需要进一步分析"
            },
            "next_action": "manual_intervention",
            "reasoning": analysis[:200]
        }
    
    async def _arun(self, *args, **kwargs) -> Dict[str, Any]:
        """异步执行"""
        # LangChain 的链支持异步
        return await self.thinking_chain.ainvoke(*args, **kwargs)