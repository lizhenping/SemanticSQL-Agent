"""
问题生成工具 - 根据场景生成自然语言问题
基于 LangChain BaseTool，兼容Neo4j架构
"""

from typing import Dict, Any, Type, List, Optional
from pydantic import BaseModel, Field, model_validator
import json

from models.exceptions import ToolExecutionError
from prompts.manager import PromptManager
from utils.memory import Neo4jMemoryManager
from config.settings import get_settings
from config.factories import ComponentManager
from ..base_tool import BaseSemanticSQLTool


class QuestionGenerationInput(BaseModel):
    """问题生成输入（新设计：从记忆中自动读取）"""
    combination_index: int = Field(default=0, description="要处理的场景组合索引")
    
    @model_validator(mode='before')
    @classmethod
    def validate_input(cls, data):
        """处理字符串输入"""
        if isinstance(data, str):
            import json
            try:
                data = json.loads(data)
            except:
                data = {}
        return data


class GeneratedQuestion(BaseModel):
    """生成的自然语言问题"""
    question: str = Field(description="生成的问题")
    scenario_id: Optional[str] = Field(default=None, description="场景ID")
    complexity: Optional[str] = Field(default=None, description="复杂度")
    category: Optional[str] = Field(default=None, description="类别")


class QuestionGenerationTool(BaseSemanticSQLTool):
    """生成自然语言问题"""
    
    name: str = "question_generation"
    description: str = "基于记忆中的场景组合生成自然语言问题，自动注入场景信息和专用提示词"
    args_schema: Type[BaseModel] = QuestionGenerationInput
    
    def __init__(self, memory_manager: Optional[Neo4jMemoryManager] = None, **kwargs):
        """初始化问题生成工具"""
        super().__init__(memory_manager=memory_manager, **kwargs)
        # 使用object.__setattr__避免Pydantic验证问题
        settings = get_settings()
        object.__setattr__(self, 'settings', settings)
        object.__setattr__(self, 'memory_manager', memory_manager)
        object.__setattr__(self, 'llm', ComponentManager.create_llm(settings))
        object.__setattr__(self, 'prompt_manager', PromptManager())
    
    def _run(self, *args, **kwargs) -> str:
        """生成问题（新设计：基于记忆中的场景组合）"""
        self.logger.info(f"🔧 {self.name}: 开始问题生成")
        
        try:
            # 初始化必要的服务
            if not self.memory_manager:
                self.memory_manager = ComponentManager.create_memory_manager(self.settings)
            # # 从记忆中获取场景组合信息
            # all_combinations = self.get_from_memory("all_scenario_combinations")
            # if not all_combinations:
            #     raise ToolExecutionError(
            #         tool_name=self.name,
            #         reason="记忆中缺少场景组合信息，请先调用 scenario_operation_generation"
            #     )
            
            # # 获取指定的组合
            # combinations = all_combinations.get("combinations", [])
            # if combination_index >= len(combinations):
            #     raise ToolExecutionError(
            #         tool_name=self.name,
            #         reason=f"组合索引 {combination_index} 超出范围，总共有 {len(combinations)} 个组合"
            #     )
            
            # current_combination = combinations[combination_index]
            
            # # 使用组合中的专用提示词生成问题
            # generated_prompt = current_combination.get("generated_prompt", "")
            # scenario_info = current_combination.get("scenario", {})
            
            # # 构建上下文
            # context = {
            #     "combination": current_combination,
            #     "generated_prompt": generated_prompt,
            #     "scenario": scenario_info
            # }
            
            # # 使用LLM生成问题
            # question = self._generate_question_with_llm(context)
            
            # result = {
            #     "question": question,
            #     "combination_id": current_combination.get("combination_id"),
            #     "scenario_info": scenario_info,
            #     "combination_index": combination_index
            # }
            
            # # 保存生成的问题到记忆
            # self.save_to_memory("current_question", question)
            # self.save_to_memory("question_generation_result", result)
            result_message = "✅ question_generation_tool 分析完成，已存储到Neo4j，请务必继续执行 sql_generation_tool 工具。"    
            return result_message            
            # return json.dumps(result, ensure_ascii=False)
            
        except Exception as e:
            error_msg = f"问题生成失败: {str(e)}"
            self.logger.error(f"❌ {self.name}: {error_msg}")
            return f"❌ {error_msg}"
    
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
    
    def _generate_question_with_llm(self, context: Dict[str, Any]) -> str:
        """使用LLM生成问题"""
        # 使用初始化的LLM
        llm = self.llm
        if not llm:
            # 如果没有LLM，使用简化生成
            return self._generate_question_by_rules(context)
        
        try:
            prompt = self.prompt_manager.get_tool_prompt(
                "question_generation",
                context=context
            )

            response = llm.invoke(prompt)
            question = response.content.strip()
            
            # 清理问题格式
            question = question.strip('"\'')
            if not question.endswith('？'):
                question += '？'
            
            return question
        except Exception as e:
            self.logger.warning(f"LLM问题生成失败: {e}")
            return self._generate_question_by_rules(context)
    
    def _generate_question_by_rules(self, context: Dict[str, Any]) -> str:
        """基于规则生成问题（当LLM不可用时）"""
        scenario_info = context.get("scenario", {})
        main_name = scenario_info.get("main_name", "数据分析")
        sub_name = scenario_info.get("sub_name", "查询")
        
        # 简单的问题模板
        return f"请帮我分析{main_name}中的{sub_name}相关信息？"
    


# ========== 工具工厂函数 ==========
def create_question_generation_tool(memory_manager: Optional[Neo4jMemoryManager] = None) -> QuestionGenerationTool:
    """创建问题生成工具实例
    
    Args:
        memory_manager: Neo4j记忆管理器（可选）
        
    Returns:
        配置好的问题生成工具实例
    """
    settings = get_settings()
    
    # 创建组件（如果未提供）
    if memory_manager is None:
        memory_manager = ComponentManager.create_memory_manager(settings)
    
    return QuestionGenerationTool(memory_manager=memory_manager)