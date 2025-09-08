
# =============================================================================
# SemanticSQL ReAct智能体 - 基于LangChain官方API
# =============================================================================

# 1. 核心状态管理 (agent/state.py)
# =============================================================================
```python
from typing import List, Dict, Any, Optional, Union
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """智能体状态 - 极简设计"""
    current_input: str                        # 用户输入
    database_params: Optional[Dict[str, Any]] # 数据库连接参数
```

# =============================================================================
# 2. 业务完成解析器 (agent/parsers.py)
# =============================================================================
```python
import re
from langchain.agents.agent import AgentAction, AgentFinish
from langchain.agents.output_parsers.base import AgentOutputParser
from langchain_core.exceptions import OutputParserException

class SemanticSQLOutputParser(AgentOutputParser):
    """
    SemanticSQL解析器 - 基于官方ReActSingleInputOutputParser逻辑
    专注SQL生成完成检测
    """
    
    def parse(self, llm_output: str) -> Union[AgentAction, AgentFinish]:
        """
        解析LLM输出 - 完全基于官方ReAct格式
        
        官方检测逻辑：
        1. Final Answer: -> AgentFinish (结束)
        2. Action: + Action Input: -> AgentAction (继续)
        3. 解析失败 -> OutputParserException
        """
        
        # 1. 检查是否包含 Final Answer（官方ReAct结束信号）
        if "Final Answer:" in llm_output:
            # 提取 Final Answer 之后的内容
            final_answer = llm_output.split("Final Answer:")[-1].strip()
            return AgentFinish(
                return_values={"output": final_answer},
                log=llm_output
            )
        
        # 2. 检查是否包含 Action 模式（官方逻辑）
        # 使用与官方相同的正则表达式
        if not re.search(r"Action\s*\d*\s*:[\s]*(.*?)", llm_output, re.DOTALL):
            raise OutputParserException(
                f"Could not parse LLM output: `{llm_output}`"
            )
        
        # 3. 提取 Action（官方逻辑）
        action_match = re.search(
            r"Action\s*\d*\s*:(.*?)(?=\n|Action\s*\d*\s*Input\s*\d*\s*:|$)", 
            llm_output, re.DOTALL
        )
        if not action_match:
            raise OutputParserException(f"Could not parse action from: `{llm_output}`")
        
        action = action_match.group(1).strip()
        
        # 4. 提取 Action Input（官方逻辑）
        action_input_match = re.search(
            r"Action\s*\d*\s*Input\s*\d*\s*:(.*?)(?=\n(?:Thought|Action|Final Answer)|$)", 
            llm_output, re.DOTALL
        )
        if not action_input_match:
            raise OutputParserException(f"Could not parse action input from: `{llm_output}`")
        
        action_input = action_input_match.group(1).strip()
        
        # 5. 移除可能的引号（与官方逻辑一致）
        if action_input.startswith('"') and action_input.endswith('"'):
            action_input = action_input[1:-1]
        elif action_input.startswith("'") and action_input.endswith("'"):
            action_input = action_input[1:-1]
        
        return AgentAction(
            tool=action,
            tool_input=action_input,
            log=llm_output
        )
    
    @property
    def _type(self) -> str:
        return "semantic_sql_react_parser"
```
# =============================================================================
# 3. Prompt模板管理 - 基于Jinja2统一管理
# =============================================================================
```python
from langchain_core.prompts import PromptTemplate
from prompts.manager import PromptManager

def create_semantic_sql_prompt():
    """创建SemanticSQL的ReAct格式提示词模板 - 使用PromptManager"""
    prompt_manager = PromptManager()
    return prompt_manager.create_agent_prompt_template(agent_type="semantic_sql_agent")
```

# =============================================================================
# 4. 记忆增强的ReAct Agent创建函数
# =============================================================================
```python
from langchain_core.runnables import RunnablePassthrough
from langchain.agents.format_scratchpad import format_log_to_str
from langchain_core.tools.render import render_text_description

def create_memory_enhanced_react_agent(llm, tools, prompt, output_parser=None):
                                     
    """
    创建支持记忆增强的ReAct Agent - 基于官方create_react_agent逻辑
    
    Args:
        llm: 语言模型
        tools: 工具列表
        prompt: 提示词模板
        output_parser: 输出解析器（可选，默认使用SemanticSQLOutputParser）
        
    Returns:
        Agent实例
    """
    
    # 验证必需变量（官方逻辑）
    missing_vars = {"tools", "tool_names", "agent_scratchpad"}.difference(
        prompt.input_variables + list(prompt.partial_variables)
    )
    if missing_vars:
        raise ValueError(f"Prompt missing required variables: {missing_vars}")

    # 设置工具信息（官方逻辑）
    prompt = prompt.partial(
        tools=render_text_description(list(tools)),
        tool_names=", ".join([t.name for t in tools]),
    )
    
    # 设置停止序列（官方逻辑）
    # llm_with_stop = llm.bind(stop=["\nObservation"])
    
    # 使用自定义输出解析器
    if output_parser is None:
        output_parser = SemanticSQLOutputParser()
    
    def enhanced_agent_scratchpad(x):
        """
        增强版 agent_scratchpad - 支持Neo4J记忆注入
        你可以在这里添加自己的记忆注入逻辑
        """
        # 获取标准推理历史（官方逻辑）
        standard_scratchpad = format_log_to_str(x["intermediate_steps"])

        return standard_scratchpad
    
    # 构建agent（官方RunnablePassthrough.assign模式）
    agent = (
        RunnablePassthrough.assign(
            agent_scratchpad=enhanced_agent_scratchpad,
        )
        | prompt
        | output_parser
    )
    
    return agent
```

# =============================================================================
# 5. 主智能体实现 (agent/sql_agent.py)
# =============================================================================

```python
from langchain.agents import AgentExecutor
from typing import List

class SemanticSQLReActAgent:
    """
    SQL生成智能体 - 基于官方API，专注业务完成逻辑
    """
    
    def __init__(self, 
                 llm,
                 tools: List,
                 max_iterations: int = 10,
                 verbose: bool = True):
        """
        初始化智能体
        
        Args:
            llm: 语言模型实例
            tools: 工具列表
            max_iterations: 最大迭代次数
            verbose: 是否显示详细执行过程
        """
        self.llm = llm
        self.tools = tools
        self.max_iterations = max_iterations
        self.verbose = verbose
        
        # 创建智能体执行器
        self.agent_executor = self._create_agent_executor()
    
    def _create_agent_executor(self) -> AgentExecutor:
        """
        创建AgentExecutor - 使用官方API
        """
        
        # 1. 创建提示词模板
        prompt = create_semantic_sql_prompt()
        
        # 2. 创建记忆增强的ReAct Agent
        agent = create_memory_enhanced_react_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt,
            output_parser=SemanticSQLOutputParser()
        )
        
        # 3. 创建AgentExecutor（官方API）
        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=self.verbose,
            max_iterations=self.max_iterations,
            handle_parsing_errors=True,
            return_intermediate_steps=True
        )
    
    def invoke(self, user_input: str) -> Dict[str, Any]:
        """
        标准invoke接口 - 兼容官方API
        
        Args:
            user_input: 用户输入
            
        Returns:
            执行结果字典
        """
        return self.agent_executor.invoke({"input": user_input})
```
# =============================================================================
# 6. 工具集成和LLM配置
# =============================================================================

```python
from langchain_openai import ChatOpenAI
from langchain_community.llms.tongyi import Tongyi

# 6.1 SemanticSQL 专用工具集成
def get_semantic_sql_tools():
    """
    获取完整的SemanticSQL工具集 - 直接集成到智能体
    
    Returns:
        List: 所有可用的SemanticSQL工具实例列表
    """
    from tools import (
        # 分析工具组
        SchemaExtractionTool,
        DomainAnalysisTool, 
        FieldAnalysisTool,
        ColumnAnalysisTool,
        TableAnalysisTool,
        ERAnalysisTool,
        # 生成工具组
        ScenarioOperationTool,
        QuestionGenerationTool,
        SQLGenerationTool,
        # 验证工具组
        SQLValidationTool,
        SQLExecutionTool,
        # 反思工具组
        SQLReflectionTool,
        # 思考工具组
        SequentialThinkingTool
    )
    
    # 创建工具实例
    tools = [
        # 核心分析工具（优先级高）
        SchemaExtractionTool(),
        DomainAnalysisTool(),
        FieldAnalysisTool(),
        ColumnAnalysisTool(),
        TableAnalysisTool(),
        ERAnalysisTool(),
        
        # 生成工具（核心业务）
        ScenarioOperationTool(),
        QuestionGenerationTool(), 
        SQLGenerationTool(),
        
        # 验证工具（质量保证）
        SQLValidationTool(),
        SQLExecutionTool(),
        
        # 反思和思考工具（深度分析）
        SQLReflectionTool(),
        SequentialThinkingTool()
    ]
    
    return tools

# 6.2 LLM配置和创建函数
def create_llm(config_type="openai", **kwargs):
    """
    创建语言模型实例 - 支持多种LLM
    
    Args:
        config_type: LLM类型 ("openai", "custom")
        **kwargs: LLM配置参数
        
    Returns:
        语言模型实例
    """
    
    if config_type == "openai":
        return ChatOpenAI(
            model=kwargs.get("model", "gpt-4"),
            api_key=kwargs.get("api_key"),
            base_url=kwargs.get("base_url"),
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 2000)
        )
    else:
        # 支持自定义LLM
        return kwargs.get("custom_llm")

# 6.3 完整的智能体工厂函数
def create_semantic_sql_agent(
    config_type="openai", 
    llm_config=None, 
    tools=None,
    **agent_kwargs
) -> SemanticSQLReActAgent:
    """
    创建完整配置的SemanticSQL智能体 - 集成LLM和工具
    
    Args:
        config_type: LLM类型 ("openai")
        llm_config: LLM配置字典
        tools: 工具列表（可选，默认使用完整SemanticSQL工具集）
        **agent_kwargs: 智能体其他参数
        
    Returns:
        配置完整的SemanticSQL智能体实例
        
    Example:
        # OpenAI配置
        agent = create_semantic_sql_agent(
            config_type="openai",
            llm_config={
                "model": "gpt-4",
                "api_key": "your-openai-key",
                "temperature": 0.7
            },
            max_iterations=15,
            verbose=True
        )
        
        # 通义千问配置
        agent = create_semantic_sql_agent(
            config_type="tongyi",
            llm_config={
                "model": "qwen-turbo",
                "api_key": "your-dashscope-key"
            }
        )
    """
    
    # 1. 创建LLM实例
    if llm_config is None:
        llm_config = {}
        
    llm = create_llm(config_type=config_type, **llm_config)
    
    # 2. 获取工具集（默认使用完整SemanticSQL工具集）
    if tools is None:
        tools = get_semantic_sql_tools()
    
    # 3. 创建智能体实例
    return SemanticSQLReActAgent(
        llm=llm,
        tools=tools,
        **agent_kwargs
    )
```