"""
顺序思考工具 - 深度分析和制定修正策略
基于 LangChain BaseTool
"""

from typing import Dict, Any, Type, Optional
from langchain.tools import BaseTool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, field_validator, ConfigDict

from models.exceptions import ToolExecutionError
from prompts.manager import PromptManager


class SequentialThinkingInput(BaseModel):
    """顺序思考输入"""
    problem_description: str = Field(description="问题描述")
    context: Dict[str, Any] = Field(default_factory=dict, description="上下文信息")
    memory: Dict[str, Any] = Field(default_factory=dict, description="包含数据库分析结果的记忆")
    
    @field_validator('context', 'memory', mode='before')
    @classmethod
    def parse_json_fields(cls, v):
        """解析JSON字符串字段"""
        if isinstance(v, str):
            try:
                import json
                parsed = json.loads(v)
                if isinstance(parsed, dict):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass
        return v if v is not None else {}


class SequentialThinkingTool(BaseTool):
    """深度思考和分析工具"""
    
    name: str = "sequential_thinking"
    description: str = "进行深度分析，制定问题解决策略"
    args_schema: Type[BaseModel] = SequentialThinkingInput
    
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
        problem_description: str,
        context: Dict[str, Any],
        memory: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行深度思考"""
        try:
            # 构建分析提示词
            prompt = self._build_analysis_prompt(
                problem_description, context, memory
            )
            
            # 使用LLM进行分析
            response = self.llm.invoke(prompt)
            analysis = response.content.strip()
            
            # 解析分析结果
            strategy = self._parse_strategy(analysis)
            
            return {
                "analysis": analysis,
                "strategy": strategy,
                "next_action": strategy.get("next_action"),
                "reasoning": strategy.get("reasoning")
            }
            
        except Exception as e:
            raise ToolExecutionError(
                tool_name=self.name,
                reason=f"深度思考失败: {str(e)}"
            )
    
    def _build_analysis_prompt(
        self,
        problem_description: str,
        context: Dict[str, Any],
        memory: Dict[str, Any]
    ) -> str:
        """构建分析提示词"""
        return self.prompt_manager.render_template(
            "thinking/sequential_thinking.j2",
            problem_description=problem_description,
            context=context
        )
    
    def _parse_strategy(self, analysis: str) -> Dict[str, Any]:
        """解析策略"""
        # 简单的策略提取
        strategy = {
            "next_action": "sql_generation",  # 默认
            "reasoning": analysis[:200]
        }
        
        # 根据分析内容判断下一步
        if "数据库结构" in analysis or "schema" in analysis.lower():
            strategy["next_action"] = "schema_extraction"
        elif "问题生成" in analysis or "问题不合理" in analysis:
            strategy["next_action"] = "question_generation"
        elif "SQL" in analysis:
            strategy["next_action"] = "sql_generation"
        
        return strategy
    
    async def _arun(
        self,
        problem_description: str,
        context: Dict[str, Any],
        memory: Dict[str, Any]
    ) -> Dict[str, Any]:
        """异步执行（当前实现为同步）"""
        return self._run(problem_description, context, memory)