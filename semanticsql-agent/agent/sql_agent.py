"""
SemanticSQL ReAct Agent - 基于LangChain官方API的极简重构
完全重构：去除复杂继承，基于设计文档的革命性简化
"""

from typing import List, Dict, Any, Optional
import logging

from langchain.agents import AgentExecutor
from langchain_core.runnables import RunnablePassthrough
from langchain.agents.format_scratchpad import format_log_to_str
from langchain_core.tools.render import render_text_description
from langchain_openai import ChatOpenAI

from agent.state import AgentState, create_agent_state, extract_database_info
from agent.parsers import SemanticSQLOutputParser
from utils.memory import Neo4jMemoryManager
from utils.database import DatabaseManager
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
                 llm: Optional[ChatOpenAI] = None,
                 tools: Optional[List] = None,
                 memory_manager: Optional[Neo4jMemoryManager] = None,
                 database_manager: Optional[DatabaseManager] = None,
                 max_iterations: int = 15,
                 verbose: bool = True):
        """初始化SemanticSQL智能体
        
        Args:
            llm: 语言模型实例
            tools: 工具列表（可选，默认使用完整SemanticSQL工具集）
            memory_manager: Neo4j记忆管理器（可选）
            database_manager: 数据库管理器（可选）
            max_iterations: 最大迭代次数
            verbose: 是否显示详细执行过程
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 核心组件初始化
        self.llm = llm or self._create_default_llm()
        self.memory_manager = memory_manager or Neo4jMemoryManager()
        self.database_manager = database_manager
        self.max_iterations = max_iterations
        self.verbose = verbose
        
        # 工具系统初始化
        self.tools = tools or self._create_semantic_sql_tools()
        
        # 创建智能体执行器
        self.agent_executor = self._create_agent_executor()
        
        self.logger.info(f"✅ SemanticSQL Agent初始化完成 - {len(self.tools)}个工具")
    
    def _create_default_llm(self) -> ChatOpenAI:
        """创建默认LLM实例"""
        return ChatOpenAI(
            model="gpt-4",
            temperature=0.7,
            max_tokens=2000
        )
    
    def _create_semantic_sql_tools(self) -> List:
        """创建完整的SemanticSQL工具集 - 基于新的BaseSemanticSQLTool"""
        tools = []
        
        try:
            # 分析工具组 - 基于新架构的完全自主工具
            analysis_tools = [
                create_schema_extraction_tool(
                    memory_manager=self.memory_manager,
                    database_manager=self.database_manager
                ),
                create_domain_analysis_tool(memory_manager=self.memory_manager),
                create_field_analysis_tool(memory_manager=self.memory_manager),
                create_column_analysis_tool(memory_manager=self.memory_manager),
                create_table_analysis_tool(memory_manager=self.memory_manager),
                create_er_analysis_tool(memory_manager=self.memory_manager)
            ]
            tools.extend(analysis_tools)
            
            self.logger.info(f"📊 创建了 {len(analysis_tools)} 个分析工具")
            
            # TODO: 后续在Phase 2中会添加其他工具组
            # generation_tools = self._create_generation_tools()
            # validation_tools = self._create_validation_tools() 
            # reflection_tools = self._create_reflection_tools()
            
        except Exception as e:
            self.logger.error(f"❌ 工具创建失败: {e}")
            raise AgentInitializationError("SemanticSQLAgent", f"工具创建失败: {e}")
        
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
            | llm_with_stop  # 使用带停止序列的LLM
            | output_parser
        )
        
        return agent
    
    def _create_semantic_sql_prompt(self):
        """创建SemanticSQL的ReAct格式提示词模板"""
        prompt_manager = PromptManager()
        return prompt_manager.create_agent_prompt_template(agent_type="semantic_sql_agent")
    
    def invoke(self, user_input: str, database_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """标准invoke接口 - 兼容官方API
        
        Args:
            user_input: 用户输入
            database_params: 数据库参数（可选）
            
        Returns:
            执行结果字典
        """
        try:
            # 创建Agent状态
            state = create_agent_state(user_input, database_params)
            
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
        """获取记忆系统统计"""
        if not self.memory_manager:
            return {"status": "no_memory_manager"}
        
        return {
            "total_triples": getattr(self.memory_manager, 'count_triples', lambda: 0)(),
            "sources": getattr(self.memory_manager, 'get_source_tools', lambda: [])(),
            "status": "active"
        }
    
    def clear_memory(self) -> bool:
        """清空记忆系统"""
        if not self.memory_manager:
            return False
        
        return self.memory_manager.clear_all()


# ========== 工厂函数 ==========

def create_llm(config_type="openai", **kwargs) -> ChatOpenAI:
    """创建语言模型实例 - 支持多种LLM
    
    Args:
        config_type: LLM类型 ("openai")
        **kwargs: LLM配置参数
        
    Returns:
        语言模型实例
    """
    
    if config_type == "openai":
        return ChatOpenAI(
            model=kwargs.get("model", "Qwen3-14B"),
            api_key=kwargs.get("api_key"),
            base_url=kwargs.get("base_url"),
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 2000)
        )
    else:
        # 支持自定义LLM
        return kwargs.get("custom_llm")


def create_semantic_sql_agent(
    config_type="openai", 
    llm_config: Optional[Dict[str, Any]] = None, 
    database_config: Optional[Dict[str, Any]] = None,
    tools: Optional[List] = None,
    **agent_kwargs
) -> SemanticSQLReActAgent:
    """创建完整配置的SemanticSQL智能体 - 集成LLM和工具
    
    Args:
        config_type: LLM类型 ("openai")
        llm_config: LLM配置字典
        database_config: 数据库配置字典
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
            database_config={
                "host": "localhost",
                "port": 3306,
                "database": "test_db",
                "user": "root",
                "password": "password"
            },
            max_iterations=15,
            verbose=True
        )
    """
    
    # 1. 创建LLM实例
    if llm_config is None:
        llm_config = {}
        
    llm = create_llm(config_type=config_type, **llm_config)
    
    # 2. 创建数据库管理器（如果提供了配置）
    database_manager = None
    if database_config:
        from utils.database_config import DatabaseConfig
        db_config = DatabaseConfig(**database_config)
        
        # 将DatabaseConfig转换为DatabaseManager所需的字典格式
        db_params = {
            "host": db_config.host,
            "port": db_config.port,
            "database": db_config.database,
            "username": db_config.username,
            "password": db_config.password,
            "type": db_config.type.value,
            "charset": db_config.charset
        }
        
        database_manager = DatabaseManager(db_params)
        if not database_manager.initialize():
            raise AgentInitializationError("DatabaseManager", "数据库连接失败")
    
    # 3. 创建记忆管理器
    memory_manager = Neo4jMemoryManager()
    
    # 4. 创建智能体实例
    return SemanticSQLReActAgent(
        llm=llm,
        tools=tools,
        memory_manager=memory_manager,
        database_manager=database_manager,
        **agent_kwargs
    )


# ========== 向后兼容性包装 ==========

class SQLAgent:
    """向后兼容的SQLAgent包装器"""
    
    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger(__name__)
        self.logger.warning("🔄 SQLAgent已重构为SemanticSQLReActAgent，建议使用新接口")
        
        # 创建新的智能体实例
        self.react_agent = create_semantic_sql_agent(**kwargs)
    
    def run(self, task: str, **kwargs) -> Dict[str, Any]:
        """兼容旧接口的run方法"""
        result = self.react_agent.invoke(task, **kwargs)
        
        # 转换为旧格式
        return {
            "success": True,
            "result": result.get("output", result),
            "agent_type": "SemanticSQLReActAgent"
        }
    
    def generate_training_data(self, output_file: str = "training_data.jsonl") -> List[Dict[str, Any]]:
        """兼容的训练数据生成方法"""
        self.logger.warning("训练数据生成功能需要在新架构中重新实现")
        return []