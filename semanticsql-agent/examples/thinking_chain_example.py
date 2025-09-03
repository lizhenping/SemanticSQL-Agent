"""Thinking Chain 使用示例"""

from langchain_openai import ChatOpenAI
from chains.thinking_chain import (
    create_thinking_chain,
    create_thinking_runnable,
    create_multi_step_thinking_chain
)


def example_basic_thinking_chain():
    """基础思考链示例"""
    # 初始化LLM
    llm = ChatOpenAI(temperature=0)
    
    # 方式1：使用 ThinkingChain 类
    chain = create_thinking_chain(
        llm=llm,
        prompt_template="""
你是一个数据分析专家。

<thinking>
让我分析一下这个问题...
</thinking>

问题：{question}
答案：""",
        input_variables=["question"]
    )
    
    result = chain.invoke({"question": "如何优化SQL查询性能？"})
    
    print("思考过程:", result["thinking"])
    print("最终答案:", result["answer"])
    
    # 方式2：使用 LCEL
    runnable = create_thinking_runnable(llm)
    result2 = runnable.invoke({"input": "解释什么是索引"})
    
    return result, result2


def example_multi_step_thinking():
    """多步思考链示例"""
    llm = ChatOpenAI(temperature=0)
    
    # 创建多步思考链
    multi_chain = create_multi_step_thinking_chain(llm)
    
    # 执行复杂问题
    result = multi_chain.invoke({
        "input": "设计一个电商数据库，需要考虑哪些方面？"
    })
    
    print("=== 完整思考过程 ===")
    print(result["all_thinking"])
    print("\n=== 最终答案 ===")
    print(result["final_answer"])
    
    # 访问各个步骤的结果
    print("\n=== 各步骤详情 ===")
    for step_name, step_result in result["steps"].items():
        print(f"\n{step_name}:")
        print(f"  思考: {step_result['thinking'][:50]}...")
        print(f"  结果: {step_result['answer'][:50]}...")
    
    return result


def example_in_agent_context():
    """在Agent中使用thinking chain的示例"""
    from langchain.agents import Tool
    from utils.thinking_parser import ReActThinkingParser
    
    llm = ChatOpenAI(temperature=0)
    parser = ReActThinkingParser()
    
    # 创建一个带thinking的工具
    def analyze_query(query: str) -> str:
        prompt = f"""<thinking>
分析这个SQL查询的性能问题...
</thinking>

查询: {query}
分析结果:"""
        
        response = llm.invoke(prompt)
        parsed = parser.parse(response.content)
        
        # 记录思考过程
        if parsed["thinking"]:
            print(f"[Tool Thinking]: {parsed['thinking']}")
        
        return parsed["answer"] if parsed["answer"] else "需要更多信息"
    
    # 将其包装为LangChain工具
    tool = Tool(
        name="sql_analyzer",
        func=analyze_query,
        description="分析SQL查询的性能"
    )
    
    return tool


def example_custom_thinking_format():
    """自定义思考格式示例"""
    from langchain.prompts import ChatPromptTemplate
    from utils.thinking_parser import ThinkingOutputParser
    
    llm = ChatOpenAI(temperature=0)
    
    # 自定义提示词，引导特定格式的思考
    prompt = ChatPromptTemplate.from_template("""
你是一个SQL专家。请按以下格式思考：

<thinking>
1. 问题理解：...
2. 方案分析：...
3. 优缺点：...
</thinking>

问题：{question}

基于以上思考，我的建议是：""")
    
    # 构建链
    chain = prompt | llm | ThinkingOutputParser()
    
    result = chain.invoke({
        "question": "应该使用JOIN还是子查询？"
    })
    
    print("结构化思考:")
    print(result["thinking"])
    print("\n建议:")
    print(result["answer"])
    
    return result


if __name__ == "__main__":
    print("=== 基础思考链示例 ===")
    example_basic_thinking_chain()
    
    print("\n=== 多步思考链示例 ===")
    example_multi_step_thinking()
    
    print("\n=== Agent工具示例 ===")
    tool = example_in_agent_context()
    print(f"创建的工具: {tool.name}")
    
    print("\n=== 自定义格式示例 ===")
    example_custom_thinking_format()