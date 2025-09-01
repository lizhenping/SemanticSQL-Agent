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
from langchain_core.memory import BaseMemory

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
            # 传递工具名称列表给提示词模板
            tool_names = [tool.name for tool in self.tools]
            return prompt_manager.create_agent_prompt(
                tool_names=", ".join(tool_names),
                tools="\n".join([f"- {tool.name}: {tool.description}" for tool in self.tools])
            )
        except Exception as e:
            self.logger.warning(f"Failed to load prompt template: {e}. Using default.")
            # 使用默认提示词
            return ChatPromptTemplate.from_messages([
                ("system", """你是一个专业的SQL训练数据生成专家。

你拥有以下工具:
{tools}

使用以下格式:
Thought: 思考下一步该做什么
Action: 要使用的工具，应该是以下之一 [{tool_names}]
Action Input: 工具的输入参数
Observation: 工具返回的结果
... (这个过程必须重复，直到完成所有必要的步骤)
Thought: 我现在知道最终答案了
Final Answer: 最终结果

重要提醒：
1. 你必须按照任务要求的步骤顺序执行所有工具
2. 每个工具执行后，分析其输出并继续执行下一个工具
3. 不要跳过任何步骤
4. 只有在完成所有步骤后才能给出 Final Answer

开始!"""),
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
        callbacks = [self.callback_handler]
        # 添加额外的回调（如果子类提供）
        if hasattr(self, 'extra_callbacks'):
            callbacks.extend(self.extra_callbacks)
        
        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            memory=self.memory,
            verbose=True,
            max_iterations=self.settings.max_steps,
            handle_parsing_errors=True,
            callbacks=callbacks
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
            execution.final_result = result
            
            # 保存轨迹
            if self.trajectory_recorder:
                self.trajectory_recorder.save_execution(execution)
            
            return {
                "success": True,
                "result": result.get("output", result),
                "execution_id": execution.task_id,
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
                "execution_id": execution.task_id,
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