"""
BaseAgent - 基于 LangChain 的基础 Agent
实现 ReAct 模式的智能体基类
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import logging

from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain.tools import BaseTool
from langchain.memory import BaseMemory

from config.settings import Settings
from config.database import DatabaseConfig
from models.schemas import AgentExecution, AgentStep
from utils.trajectory import TrajectoryRecorder
from utils.callbacks import TrajectoryCallbackHandler


class BaseAgent(ABC):
    """基于 LangChain 的基础 Agent"""
    
    def __init__(self, settings: Settings, db_config: DatabaseConfig):
        """初始化 Agent"""
        self.settings = settings
        self.db_config = db_config
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 初始化 LLM
        self.llm = ChatOpenAI(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            openai_api_base=settings.llm_base_url,
            openai_api_key=settings.llm_api_key,
            max_tokens=settings.llm_max_tokens
        )
        
        # 初始化轨迹记录
        self.trajectory_recorder = TrajectoryRecorder()
        self.callback_handler = TrajectoryCallbackHandler(self.trajectory_recorder)
        
        # 初始化工具
        self.tools = self._initialize_tools()
        
        # 初始化记忆
        self.memory = self._initialize_memory()
        
        # 创建 Agent
        self.agent_executor = self._create_agent()
        
        self.logger.info(f"Initialized {self.__class__.__name__} with {len(self.tools)} tools")
    
    @abstractmethod
    def _initialize_tools(self) -> List[BaseTool]:
        """初始化工具列表"""
        pass
    
    @abstractmethod
    def _initialize_memory(self) -> BaseMemory:
        """初始化记忆系统"""
        pass
    
    def _create_prompt(self) -> ChatPromptTemplate:
        """创建Agent提示词"""
        try:
            from prompts.manager import PromptManager
            prompt_manager = PromptManager()
            return prompt_manager.create_agent_prompt()
        except Exception as e:
            self.logger.warning(f"Failed to load prompt template: {e}. Using default.")
            # 使用默认提示词
            return ChatPromptTemplate.from_messages([
                ("system", """You are a helpful AI assistant that uses tools to complete tasks.

You have access to the following tools:
{tools}

Use the following format:
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!"""),
                ("human", "{input}"),
                ("assistant", "{agent_scratchpad}")
            ])
    
    def _create_agent(self) -> AgentExecutor:
        """创建 LangChain Agent"""
        # 创建提示词模板
        prompt = self._create_prompt()
        
        # 创建 ReAct agent
        agent = create_react_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt
        )
        
        # 创建执行器
        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            memory=self.memory,
            verbose=True,
            max_iterations=self.settings.max_steps,
            handle_parsing_errors=True,
            callbacks=[self.callback_handler]
        )
    
    def run(self, task: str, **kwargs) -> Dict[str, Any]:
        """执行任务"""
        # 创建执行记录
        execution = AgentExecution(
            task=task,
            agent_type=self.__class__.__name__,
            status="running"
        )
        
        # 设置到回调处理器
        self.callback_handler.set_execution(execution)
        
        try:
            # 执行任务
            self.logger.info(f"Starting task: {task}")
            result = self.agent_executor.invoke({
                "input": task,
                **kwargs
            })
            
            # 更新执行状态
            execution.status = "completed"
            execution.result = result
            
            # 保存轨迹
            if self.trajectory_recorder:
                self.trajectory_recorder.save_execution(execution)
            
            return {
                "success": True,
                "result": result.get("output", result),
                "execution_id": execution.execution_id,
                "steps": len(execution.steps)
            }
            
        except Exception as e:
            self.logger.error(f"Task execution failed: {e}", exc_info=True)
            
            # 更新执行状态
            execution.status = "failed"
            execution.error = str(e)
            
            # 保存轨迹
            if self.trajectory_recorder:
                self.trajectory_recorder.save_execution(execution)
            
            return {
                "success": False,
                "error": str(e),
                "execution_id": execution.execution_id,
                "steps": len(execution.steps)
            }
    
    def get_tool_names(self) -> List[str]:
        """获取所有工具名称"""
        return [tool.name for tool in self.tools]
    
    def get_memory_state(self) -> Dict[str, Any]:
        """获取当前记忆状态"""
        return self.memory.load_memory_variables({})
    
    def clear_memory(self):
        """清空记忆"""
        if hasattr(self.memory, 'clear'):
            self.memory.clear()
    
    def save_trajectory(self, filepath: str):
        """保存执行轨迹"""
        if self.trajectory_recorder:
            self.trajectory_recorder.save_to_file(filepath)