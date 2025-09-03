"""LangChain Thinking Chain 实现"""

from typing import Dict, Any, Optional, List

from langchain.chains.base import Chain
from langchain.prompts import ChatPromptTemplate
from langchain.schema import BaseOutputParser
from langchain.schema.language_model import BaseLanguageModel
from langchain.schema.runnable import RunnablePassthrough, RunnableLambda
from langchain.callbacks.manager import CallbackManagerForChainRun

from utils.thinking_parser import ThinkingOutputParser


class ThinkingChain(Chain):
    """带有思考过程的LangChain链"""
    
    llm: BaseLanguageModel
    prompt: ChatPromptTemplate
    parser: BaseOutputParser = ThinkingOutputParser()
    
    @property
    def input_keys(self) -> List[str]:
        """输入键"""
        return self.prompt.input_variables
    
    @property
    def output_keys(self) -> List[str]:
        """输出键"""
        return ["thinking", "answer", "has_thinking"]
    
    def _call(
        self,
        inputs: Dict[str, Any],
        run_manager: Optional[CallbackManagerForChainRun] = None,
    ) -> Dict[str, Any]:
        """执行链"""
        # 构建可运行链
        chain = self.prompt | self.llm | self.parser
        
        # 执行并返回结果
        result = chain.invoke(inputs, config={"callbacks": run_manager.get_child() if run_manager else None})
        
        # 记录思考过程到日志
        if result.get("has_thinking") and run_manager:
            run_manager.on_text(f"[Thinking]: {result['thinking'][:200]}...", verbose=self.verbose)
        
        return result
    
    @property
    def _chain_type(self) -> str:
        """链类型"""
        return "thinking_chain"


def create_thinking_chain(
    llm: BaseLanguageModel,
    prompt_template: str,
    input_variables: List[str]
) -> ThinkingChain:
    """
    创建一个思考链
    
    Args:
        llm: 语言模型
        prompt_template: 提示词模板
        input_variables: 输入变量列表
        
    Returns:
        ThinkingChain实例
    """
    prompt = ChatPromptTemplate.from_template(prompt_template)
    prompt.input_variables = input_variables
    
    return ThinkingChain(
        llm=llm,
        prompt=prompt,
        parser=ThinkingOutputParser()
    )


# 使用 LCEL (LangChain Expression Language) 构建链
def create_thinking_runnable(llm: BaseLanguageModel):
    """使用LCEL创建可运行的思考链"""
    
    # 定义提示词
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是一个善于思考的助手。请使用<thinking>标签记录你的思考过程。"),
        ("human", "{input}")
    ])
    
    # 定义解析器
    parser = ThinkingOutputParser()
    
    # 构建链
    chain = prompt | llm | parser
    
    # 添加日志处理
    def log_thinking(x: Dict[str, Any]) -> Dict[str, Any]:
        if x.get("has_thinking"):
            print(f"[Thinking Process]: {x['thinking'][:100]}...")
        return x
    
    # 完整的链
    return chain | RunnableLambda(log_thinking)


# 多步思考链
def create_multi_step_thinking_chain(llm: BaseLanguageModel):
    """创建多步思考链"""
    
    # 步骤1：分析问题
    analysis_prompt = ChatPromptTemplate.from_template("""
<thinking>
分析问题的关键要素...
</thinking>

问题：{input}
分析：""")
    
    # 步骤2：制定计划
    planning_prompt = ChatPromptTemplate.from_template("""
基于分析：{analysis}

<thinking>
制定解决方案...
</thinking>

计划：""")
    
    # 步骤3：执行
    execution_prompt = ChatPromptTemplate.from_template("""
基于计划：{plan}

<thinking>
执行具体步骤...
</thinking>

执行结果：""")
    
    # 步骤4：反思
    reflection_prompt = ChatPromptTemplate.from_template("""
执行结果：{result}

<thinking>
反思和改进...
</thinking>

最终结论：""")
    
    # 解析器
    parser = ThinkingOutputParser()
    
    # 构建多步链
    analysis_chain = analysis_prompt | llm | parser
    planning_chain = planning_prompt | llm | parser
    execution_chain = execution_prompt | llm | parser
    reflection_chain = reflection_prompt | llm | parser
    
    # 组合链
    def run_multi_step(inputs: Dict[str, Any]) -> Dict[str, Any]:
        # 步骤1
        analysis_result = analysis_chain.invoke({"input": inputs["input"]})
        
        # 步骤2
        planning_result = planning_chain.invoke({"analysis": analysis_result["answer"]})
        
        # 步骤3
        execution_result = execution_chain.invoke({"plan": planning_result["answer"]})
        
        # 步骤4
        reflection_result = reflection_chain.invoke({"result": execution_result["answer"]})
        
        # 汇总所有思考过程
        all_thinking = "\n\n".join([
            f"[分析思考]: {analysis_result['thinking']}",
            f"[计划思考]: {planning_result['thinking']}",
            f"[执行思考]: {execution_result['thinking']}",
            f"[反思思考]: {reflection_result['thinking']}"
        ])
        
        return {
            "all_thinking": all_thinking,
            "final_answer": reflection_result["answer"],
            "steps": {
                "analysis": analysis_result,
                "planning": planning_result,
                "execution": execution_result,
                "reflection": reflection_result
            }
        }
    
    return RunnableLambda(run_multi_step)