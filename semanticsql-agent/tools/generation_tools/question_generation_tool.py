"""
问题生成工具 - 根据场景生成自然语言问题
基于 LangChain BaseTool
"""

from typing import Dict, Any, Type, List
from langchain.tools import BaseTool
from langchain_community.chat_models import ChatOpenAI
from pydantic import BaseModel, Field

from models.exceptions import ToolExecutionError


class QuestionGenerationInput(BaseModel):
    """问题生成输入"""
    scenario: Dict[str, Any] = Field(description="场景信息")
    operations: List[str] = Field(description="SQL操作列表")
    memory: Dict[str, Any] = Field(description="包含数据库分析结果的记忆")


class QuestionGenerationTool(BaseTool):
    """生成自然语言问题"""
    
    name: str = "question_generation"
    description: str = "根据场景和数据库结构生成自然语言问题"
    args_schema: Type[BaseModel] = QuestionGenerationInput
    
    def __init__(self, llm: ChatOpenAI):
        super().__init__()
        self.llm = llm
    
    def _run(
        self,
        scenario: Dict[str, Any],
        operations: List[str],
        memory: Dict[str, Any]
    ) -> Dict[str, Any]:
        """生成问题"""
        try:
            # 从记忆中获取必要信息
            db_analysis = memory.get("db_analysis", {})
            schema_info = db_analysis.get("schema_info", {})
            domain_info = db_analysis.get("domain_info", {})
            
            if not schema_info:
                raise ToolExecutionError(
                    tool_name=self.name,
                    reason="未找到数据库结构信息"
                )
            
            # 构建上下文
            context = self._build_context(scenario, operations, schema_info, domain_info)
            
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
        operations: List[str],
        schema_info: Dict[str, Any],
        domain_info: Dict[str, Any]
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
        
        # 添加相关表信息
        applicable_tables = scenario.get("applicable_tables", [])
        if applicable_tables:
            context_parts.append(f"\n相关表：")
            tables = schema_info.get("tables", {})
            
            for table_name in applicable_tables[:5]:  # 限制表数量
                if table_name in tables:
                    table_info = tables[table_name]
                    context_parts.append(f"\n表：{table_name}")
                    
                    # 添加部分列信息
                    columns = table_info.get("columns", [])
                    col_names = [col["name"] for col in columns[:10]]
                    context_parts.append(f"  主要列：{', '.join(col_names)}")
        
        return "\n".join(context_parts)
    
    def _generate_question_with_llm(self, context: str) -> str:
        """使用LLM生成问题"""
        prompt = f"""基于以下场景信息，生成一个自然、清晰的中文问题：

{context}

要求：
1. 问题要自然、符合实际业务场景
2. 问题要清晰、无歧义
3. 问题要能够通过SQL查询来回答
4. 使用中文，表达流畅
5. 不要包含具体的数值或日期（使用"最近"、"去年"等相对表述）

生成的问题："""

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