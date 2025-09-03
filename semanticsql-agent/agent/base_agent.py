"""
BaseAgent - 基于 LangChain 的基础 Agent
实现 ReAct 模式的智能体基类
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import logging
import json

from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain.tools import BaseTool
from langchain_core.memory import BaseMemory

from config.settings import Settings
from config.database import DatabaseConfig
from models.agent import AgentExecution, AgentStep
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
        
        # 为分析工具设置memory引用
        self._setup_tool_memory_references()
        
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
    
    def _setup_tool_memory_references(self):
        """为分析工具设置memory引用"""
        for tool in self.tools:
            # 检查是否有set_memory方法
            if hasattr(tool, 'set_memory'):
                tool.set_memory(self.memory)
    
    def _create_prompt(self) -> ChatPromptTemplate:
        """创建Agent提示词"""
        try:
            from prompts.manager import PromptManager
            prompt_manager = PromptManager()
            
            # 尝试使用灵活的提示词模板
            try:
                # 不传递工具信息，让模板保留占位符
                system_prompt = prompt_manager.render_template(
                    'system/main_flexible.j2'
                )
            except Exception as template_error:
                self.logger.warning(f"Failed to load flexible template: {template_error}")
                # 如果灵活模板不存在，使用原有模板
                try:
                    system_prompt = prompt_manager.render_template(
                        'system/main.j2'
                    )
                except Exception as main_error:
                    self.logger.warning(f"Failed to load main template: {main_error}")
                    # 如果都失败，使用默认模板
                    system_prompt = None
            
            if system_prompt:
                return ChatPromptTemplate.from_messages([
                    ("system", system_prompt),
                    ("human", "{input}"),
                    ("assistant", "{agent_scratchpad}")
                ])
            else:
                raise Exception("No prompt template available")
                
        except Exception as e:
            self.logger.warning(f"Failed to load prompt template: {e}. Using default.")
            # 使用默认提示词 - 保留LangChain需要的占位符
            return ChatPromptTemplate.from_messages([
                ("system", """你是一个专业的SQL训练数据生成专家。

你拥有以下工具:
{tools}

使用以下格式:
Thought: 思考下一步该做什么
Action: 要使用的工具，应该是以下之一 [{tool_names}]
Action Input: 工具的输入参数
Observation: 工具返回的结果
... (这个过程可以重复多次)
Thought: 我现在知道最终答案了
Final Answer: 最终结果

请根据任务需求，灵活选择和使用工具。

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
        # 设置内存引用以便保存工具结果 - 使用object.__setattr__避免Pydantic验证
        if hasattr(self.callback_handler, '__dict__'):
            object.__setattr__(self.callback_handler, 'memory', self.memory)
        else:
            # 如果无法设置，记录警告但继续执行
            self.logger.warning("Unable to set memory reference to callback handler")
        
        try:
            # 执行任务
            self.logger.info(f"Starting task: {task}")
            
            # 准备执行参数，包含模板需要的变量
            execution_params = {
                "input": task,
                "database_name": getattr(self.db_config, 'database', 'unknown'),
                "memory_summary": self._get_memory_summary(),
                **kwargs
            }
            
            # 如果kwargs中有count参数，使用它，否则默认为1
            if 'count' not in execution_params:
                execution_params['count'] = kwargs.get('target_count', 1)
            
            result = self.agent_executor.invoke(execution_params)
            
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
    
    def _get_memory_summary(self) -> str:
        """获取记忆状态摘要"""
        try:
            memory_state = self.get_memory_state()
            if not memory_state:
                return "初始状态"
            
            # 统计已有的分析结果
            analysis_count = 0
            if memory_state.get("schema_info"):
                analysis_count += 1
            if memory_state.get("domain_info"):
                analysis_count += 1
            if memory_state.get("field_classification"):
                analysis_count += 1
                
            return f"已完成 {analysis_count} 项分析"
        except:
            return "记忆状态未知"
    
    def clear_memory(self):
        """清空记忆"""
        if hasattr(self.memory, 'clear'):
            self.memory.clear()
    
    def save_trajectory(self, filepath: str):
        """保存执行轨迹"""
        if self.trajectory_recorder:
            self.trajectory_recorder.save_to_file(filepath)