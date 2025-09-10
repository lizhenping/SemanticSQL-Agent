"""
BaseAgent - 基于 LangChain 的基础 Agent
优化版本：简化抽象，单一职责，类型安全
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import logging

from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain.tools import BaseTool
from langchain_core.memory import BaseMemory

from config.settings import Settings
from models.agent import AgentExecution, AgentStep
from utils.trajectory import TrajectoryRecorder
from utils.callbacks import TrajectoryCallbackHandler
from prompts.manager import PromptManager


class BaseAgent(ABC):
    """基于 LangChain 的基础 Agent - 简化版本
    
    职责：
    - 提供 ReAct 模式的基础架构
    - 管理 LLM、工具和记忆系统
    - 协调任务执行流程
    
    设计原则：
    - 简化抽象：移除不必要的复杂度
    - 单一职责：专注于 Agent 核心功能
    - 类型安全：明确的接口和数据流
    """
    
    def __init__(self, settings: Settings):
        """初始化 Agent - 统一配置版本
        
        Args:
            settings: 系统配置 (统一配置源)
        """
        self.settings = settings
            
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 初始化核心组件
        self.llm = self._create_llm()
        self.trajectory_recorder = TrajectoryRecorder()
        self.callback_handler = TrajectoryCallbackHandler(self.trajectory_recorder)
        
        # 初始化工具和记忆
        self.tools = self._initialize_tools()
        self.memory = self._initialize_memory()
        self.prompt_manager = PromptManager()
        
        # 设置工具记忆引用
        self._setup_tool_memory()
        
        # Agent执行器（延迟创建）
        self.agent_executor = None
        
        self.logger.info(f"Initialized {self.__class__.__name__} with {len(self.tools)} tools")
    
    # ========== 核心组件创建 ==========
    def _create_llm(self) -> ChatOpenAI:
        """创建LLM实例"""
        return ChatOpenAI(
            model=self.settings.llm_model,
            temperature=self.settings.llm_temperature,
            openai_api_base=self.settings.llm_base_url,
            openai_api_key=self.settings.llm_api_key,
            max_tokens=self.settings.llm_max_tokens
        )
    
    def _setup_tool_memory(self) -> None:
        """为工具设置记忆引用"""
        for tool in self.tools:
            if hasattr(tool, 'set_memory'):
                tool.set_memory(self.memory)
    
    # ========== 抽象方法（子类必须实现）==========
    @abstractmethod
    def _initialize_tools(self) -> List[BaseTool]:
        """初始化工具列表"""
        pass
    
    @abstractmethod
    def _initialize_memory(self) -> BaseMemory:
        """初始化记忆系统"""
        pass
    
    # ========== 任务执行流程 ==========
    def run(self, task: str, **kwargs) -> Dict[str, Any]:
        """执行任务 - 主要接口
        
        Args:
            task: 任务描述
            **kwargs: 额外参数
            
        Returns:
            执行结果
        """
        execution = AgentExecution(
            task=task,
            agent_type=self.__class__.__name__,
            status="running"
        )
        self._prepare_execution(execution)
        
        result = self._execute_task(task, execution, **kwargs)
        self._finalize_execution(execution, result)
        
        return result
    
    def _prepare_execution(self, execution: AgentExecution) -> None:
        """准备执行环境"""
        self.callback_handler.set_execution(execution)
        # 设置记忆引用
        if hasattr(self.callback_handler, '__dict__'):
            object.__setattr__(self.callback_handler, 'memory', self.memory)
    
    def _execute_task(self, task: str, execution: AgentExecution, **kwargs) -> Dict[str, Any]:
        """执行具体任务"""
        self.logger.info(f"Starting task: {task}")
        
        try:
            # 创建执行参数和Agent
            params = self._create_execution_params(task, **kwargs)
            agent_executor = self._get_or_create_agent()
            
            # 执行任务
            result = agent_executor.invoke(params)
            
            # 构建成功结果
            execution.status = "completed"
            execution.final_result = result
            
            return {
                "success": True,
                "result": result.get("output", result),
                "execution_id": execution.task_id,
                "steps": len(execution.steps)
            }
            
        except Exception as e:
            self.logger.error(f"Task execution failed: {e}")
            
            execution.status = "failed"
            execution.error = str(e)
            
            return {
                "success": False,
                "error": str(e),
                "execution_id": execution.task_id,
                "steps": len(execution.steps)
            }
    
    def _finalize_execution(self, execution: AgentExecution, result: Dict[str, Any]) -> None:
        """完成执行收尾工作"""
        if self.trajectory_recorder:
            self.trajectory_recorder.save_execution(execution)
    
    # ========== Agent 和参数创建 ==========
    def _create_execution_params(self, task: str, **kwargs) -> Dict[str, Any]:
        """创建执行参数 - 使用统一Settings配置"""
        # 统一从Settings获取数据库名称
        database_name = self.settings.db_database
            
        params = {
            "input": task,
            "database_name": database_name,
        }
        params.update(kwargs)
        return params
    
    def _get_or_create_agent(self) -> AgentExecutor:
        """获取或创建Agent执行器"""
        if not self.agent_executor:
            self.agent_executor = self._create_agent_executor()
        return self.agent_executor
    
    def _create_agent_executor(self) -> AgentExecutor:
        """创建Agent执行器"""
        prompt = self._create_prompt()
        agent = create_react_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt
        )
        
        callbacks = [self.callback_handler]
        if hasattr(self, 'extra_callbacks'):
            callbacks.extend(self.extra_callbacks)
        
        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            memory=self.memory,
            verbose=True,
            max_iterations=100,
            handle_parsing_errors=True,
            callbacks=callbacks
        )
    
    def _create_prompt(self) -> ChatPromptTemplate:
        """创建提示词模板 - 使用统一的PromptManager"""
        # 统一从Settings获取数据库名称
        database_name = self.settings.db_database
            
        # 构建模板参数
        template_params = {
            'tools': "\n".join([f"- {tool.name}: {tool.description}" for tool in self.tools]),
            'tool_names': ", ".join([tool.name for tool in self.tools]),
            'database_name': database_name,
            'input': '{input}',  # 保留LangChain占位符
        }
        
        # 使用PromptManager的统一接口创建Agent提示词
        return self.prompt_manager.create_agent_prompt(**template_params)
    
    
    
    
    # ========== 工具方法 ==========
    def get_tool_names(self) -> List[str]:
        """获取所有工具名称"""
        return [tool.name for tool in self.tools]