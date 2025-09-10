"""
SemanticSQL ReAct Agent - 基于LangChain官方API的极简重构
完全重构：去除复杂继承，基于设计文档的革命性简化
"""

from typing import List, Dict, Any, Optional
import logging

from langchain.agents import AgentExecutor
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain.agents.format_scratchpad import format_log_to_str
from langchain_core.tools.render import render_text_description
from langchain_openai import ChatOpenAI

from agent.state import  create_agent_state, extract_database_info
from agent.parsers import SemanticSQLOutputParser

from models.exceptions import AgentExecutionError, AgentInitializationError
from prompts.manager import PromptManager


# 新工具系统导入 - 基于BaseSemanticSQLTool
from tools.analysis_tools.schema_extraction_tool import create_schema_extraction_tool
from tools.analysis_tools.domain_analysis_tool import create_domain_analysis_tool
from tools.analysis_tools.field_analysis_tool import create_field_analysis_tool
from tools.analysis_tools.column_analysis_tool import create_column_analysis_tool
from tools.analysis_tools.table_analysis_tool import create_table_analysis_tool
from tools.analysis_tools.er_analysis_tool import create_er_analysis_tool


class SemanticSQLReActAgent:
    """SQL生成智能体 - 基于官方API，专注业务完成逻辑
    
    设计原则：
    - 极简架构：去除复杂继承，直接使用LangChain官方API
    - 2字段状态：只有current_input和database_params
    - 工具自主：所有业务逻辑在工具的_run()方法中完成
    - 记忆驱动：工具间通过Neo4j记忆系统协作
    
    核心职责：
    - 创建和管理AgentExecutor
    - 提供标准invoke接口
    - 管理工具集和记忆系统
    """
    
    def __init__(self, 
                 settings: Optional['Settings'] = None,
                 tools: Optional[List] = None,
                 max_iterations: int = 15,
                 verbose: bool = True,
                 use_database: bool = True,
                 use_memory: bool = True):
        """初始化SemanticSQL智能体 - 按需创建版本"""
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 基础配置
        from config.settings import get_settings
        self.settings = settings or get_settings()
        self.max_iterations = max_iterations
        self.verbose = verbose
        
        # 初始化组件
        self._init_components(use_database, use_memory)
        
        # 初始化工具和执行器
        self.tools = tools or self._create_available_tools()
        self.agent_executor = self._create_agent_executor()
        
        self.logger.info(f"✅ SemanticSQL Agent初始化完成 - {len(self.tools)}个工具")
    
    def _init_components(self, use_database: bool, use_memory: bool):
        """初始化组件：LLM、数据库、记忆系统"""
        from config.factories import ComponentManager
        
        # LLM是必需的
        self.llm = ComponentManager.create_llm(self.settings)
        
        # 数据库是可选的
        self.database_manager = None
        if use_database:
            self.database_manager = ComponentManager.create_database_manager(self.settings)
            self._log_component_status("Database", self.database_manager)
        
        # 记忆系统是可选的
        self.memory_manager = None
        if use_memory:
            self.memory_manager = ComponentManager.create_memory_manager(self.settings)
            self._log_component_status("Memory", self.memory_manager)
    
    def _log_component_status(self, component_name: str, component):
        """记录组件状态"""
        if component:
            self.logger.info(f"✅ {component_name} manager created")
        else:
            self.logger.warning(f"⚠️ {component_name} manager not available")
    

    
    def _create_available_tools(self) -> List:
        """根据可用组件创建工具集"""
        tools = []
        
        # 需要数据库的工具
        if self.database_manager:
            try:
                tools.append(create_schema_extraction_tool(
                    memory_manager=self.memory_manager,  # 可以是None
                    database_manager=self.database_manager
                ))
                self.logger.info("Added schema extraction tool")
            except Exception as e:
                self.logger.warning(f"Failed to create schema extraction tool: {e}")
        
        # 只需要记忆的工具
        if self.memory_manager:
            try:
                tools.extend([
                    create_field_analysis_tool(memory_manager=self.memory_manager),
                    # create_domain_analysis_tool(memory_manager=self.memory_manager),
                    create_column_analysis_tool(memory_manager=self.memory_manager),
                    create_table_analysis_tool(memory_manager=self.memory_manager),
                    create_er_analysis_tool(memory_manager=self.memory_manager)
                ])
                self.logger.info("Added memory-based analysis tools")
            except Exception as e:
                self.logger.warning(f"Failed to create memory-based tools: {e}")
        
        # 如果没有任何工具，至少添加一个基础工具
        if not tools:
            self.logger.warning("No specialized tools available, agent will use LLM only")
        
        return tools
    
    
    def _create_agent_executor(self) -> AgentExecutor:
        """创建AgentExecutor - 使用官方API和自定义解析器"""
        
        # 1. 创建提示词模板
        prompt = self._create_semantic_sql_prompt()
        
        # 2. 创建标准ReAct Agent
        agent = self._create_react_agent(
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
    
    def _create_react_agent(self, llm, tools, prompt, output_parser=None):
        """创建标准ReAct Agent - 基于官方create_react_agent逻辑
        
        Args:
            llm: 语言模型
            tools: 工具列表
            prompt: 提示词模板
            output_parser: 输出解析器
            
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
        
        # 使用自定义输出解析器
        if output_parser is None:
            output_parser = SemanticSQLOutputParser()
        
        def agent_scratchpad(x):
            """标准 agent_scratchpad - 格式化推理历史
            Neo4j记忆管理在各个工具内部进行
            """
            return format_log_to_str(x["intermediate_steps"])
        
        
        # 构建agent（官方RunnablePassthrough.assign模式）
        # 绑定停止序列确保LLM在正确位置停止
        llm_with_stop = llm.bind(stop=["\nObservation:", "\nObservation"])
        
        agent = (
            RunnablePassthrough.assign(
                agent_scratchpad=agent_scratchpad,
            )
            | prompt
            | llm  # 使用原始LLM，不带停止序列
            | output_parser  # 解析器内部会过滤think内容
        )
        
        return agent
    
    def _create_semantic_sql_prompt(self):
        """创建SemanticSQL的ReAct格式提示词模板"""
        prompt_manager = PromptManager()
        return prompt_manager.create_agent_prompt_template(agent_type="semantic_sql_agent")
    
    def invoke(self, user_input: str) -> Dict[str, Any]:
        """标准invoke接口
        
        Args:
            user_input: 用户输入
            
        Returns:
            执行结果字典
        """
        try:
            # 创建Agent状态
            state = create_agent_state(user_input, None)
            
            # 构建执行参数
            params = {
                "input": user_input,
                **extract_database_info(state)
            }
            
            self.logger.info(f"🚀 开始执行任务: {user_input[:100]}...")
            
            # 执行Agent
            result = self.agent_executor.invoke(params)
            
            self.logger.info(f"✅ 任务执行完成")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 任务执行失败: {e}")
            raise AgentExecutionError("invoke", str(e))
    
    # ========== 便利方法 ==========
    def get_tool_names(self) -> List[str]:
        """获取所有工具名称"""
        return [tool.name for tool in self.tools]
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """获取记忆系统统计信息"""
        if not self.memory_manager:
            return {"status": "no_memory", "total_triples": 0}
        
        try:
            stats = self.memory_manager.get_memory_statistics()
            return stats
        except:
            return {"status": "error", "total_triples": 0}


# ========== 工厂函数 ==========

def create_semantic_sql_agent(
    settings: Optional['Settings'] = None,
    tools: Optional[List] = None,
    **agent_kwargs
) -> SemanticSQLReActAgent:
    """创建SemanticSQL智能体 - 简化版本
    
    Args:
        settings: 配置实例（可选，默认使用全局配置）
        tools: 工具列表（可选，默认使用完整SemanticSQL工具集）
        **agent_kwargs: 智能体其他参数
        
    Returns:
        配置完整的SemanticSQL智能体实例
        
    Example:
        from config.settings import get_settings
        settings = get_settings()
        agent = create_semantic_sql_agent(
            settings=settings,
            max_iterations=15,
            verbose=True
        )
    """
    return SemanticSQLReActAgent(
        settings=settings,
        tools=tools,
        **agent_kwargs
    )


