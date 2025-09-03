"""
问题生成工具 - 根据场景生成自然语言问题
基于 LangChain BaseTool
"""

from typing import Dict, Any, Type, List, Optional
from langchain.tools import BaseTool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, ConfigDict
import json

from models.exceptions import ToolExecutionError
from prompts.manager import PromptManager


class QuestionGenerationInput(BaseModel):
    """问题生成输入"""
    scenario_id: str = Field(default="", description="场景ID")
    operations: List[str] = Field(default_factory=list, description="SQL操作列表")
    scenario: Optional[Dict[str, Any]] = Field(default=None, description="完整场景信息")
    memory: Optional[Dict[str, Any]] = Field(default=None, description="包含数据库分析结果的记忆")


class GeneratedQuestion(BaseModel):
    """生成的自然语言问题"""
    question: str = Field(description="生成的问题")
    scenario_id: Optional[str] = Field(default=None, description="场景ID")
    complexity: Optional[str] = Field(default=None, description="复杂度")
    category: Optional[str] = Field(default=None, description="类别")


class QuestionGenerationTool(BaseTool):
    """生成自然语言问题"""
    
    name: str = "question_generation"
    description: str = "根据场景和数据库结构生成自然语言问题"
    args_schema: Type[BaseModel] = QuestionGenerationInput
    
    # 定义必需的字段
    llm: Optional[ChatOpenAI] = Field(default=None, exclude=True)
    prompt_manager: Optional[PromptManager] = Field(default=None, exclude=True)
    
    # Pydantic v2配置
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    def __init__(self, llm: ChatOpenAI):
        super().__init__()
        self.llm = llm
        self.prompt_manager = PromptManager()
    
    def _run(
        self,
        scenario_id: str = "",
        operations: List[str] = None,
        scenario: Optional[Dict[str, Any]] = None,
        memory: Optional[Dict[str, Any]] = None
    ,
        **kwargs  # 接受额外的参数如 verbose
    ) -> Dict[str, Any]:
        """生成问题"""
        try:
            # 处理默认值
            if operations is None:
                operations = []
            if scenario is None:
                scenario = {}
            if memory is None:
                memory = {}
            
            # QuestionGenerationTool基于场景和操作生成问题，不强制依赖数据库分析
            category = scenario.get("category", "通用查询")
            business_purpose = scenario.get("business_purpose", "数据查询")
            complexity = scenario.get("complexity", "easy")
            
            # 构建简化的上下文（不依赖数据库分析）
            context = self._build_context(scenario, operations)
            
            # 使用LLM生成问题
            question = self._generate_question_with_llm(context)
            
            return {
                "question": question,
                "scenario_id": scenario.get("scenario_id"),
                "complexity": scenario.get("complexity"),
                "category": scenario.get("category")
            }
            
        except Exception as e:
            raise ToolExecutionError(
                tool_name=self.name,
                reason=f"问题生成失败: {str(e)}"
            )
    
    def _build_context(
        self,
        scenario: Dict[str, Any],
        operations: List[str]
    ) -> str:
        """构建生成问题的上下文"""
        context_parts = []
        
        # 添加场景信息
        context_parts.append(f"场景类别：{scenario.get('category', '')}")
        context_parts.append(f"业务目的：{scenario.get('business_purpose', '')}")
        context_parts.append(f"场景描述：{scenario.get('description', '')}")
        
        # 添加操作信息
        if operations:
            context_parts.append(f"需要使用的SQL操作：{', '.join(operations)}")
        
        # 添加操作说明
        if operations:
            context_parts.append(f"\n需要的操作类型：{', '.join(operations)}")
        
        return "\n".join(context_parts)
    
    def _generate_question_with_llm(self, context: str) -> str:
        """使用LLM生成问题"""
        prompt = self.prompt_manager.get_tool_prompt(
            "question_generation",
            context=context
        )

        response = self.llm.invoke(prompt)
        question = response.content.strip()
        
        # 清理问题格式
        question = question.strip('"\'')
        if not question.endswith('？'):
            question += '？'
        
        return question
    
    async def _arun(
        self,
        scenario: Dict[str, Any],
        operations: List[str],
        memory: Dict[str, Any]
    ) -> Dict[str, Any]:
        """异步执行（当前实现为同步）"""
        return self._run(scenario, operations, memory)