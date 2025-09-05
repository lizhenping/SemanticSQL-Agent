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
from utils.database_config import DatabaseConfig
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
        
        # 不在初始化时创建Agent，而是在执行时动态创建
        self.agent_executor = None
        
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
    
    
    def _create_execution_params(self, task: str, **kwargs) -> Dict[str, Any]:
        """创建执行参数（简化版）
        
        Args:
            task: 任务描述
            **kwargs: 额外参数
            
        Returns:
            执行参数字典
        """
        # 极简参数（Agent完全自主）
        params = {
            "input": task,
            "database_name": getattr(self.db_config, 'database', 'unknown'),
        }
        
        # 添加其他kwargs
        for key, value in kwargs.items():
            params[key] = value
        
        return params
    
    
    def _create_prompt(self, **runtime_params) -> ChatPromptTemplate:
        """创建统一的Agent提示词模板（简化版）"""
        try:
            from prompts.manager import PromptManager
            prompt_manager = PromptManager()
            
            # 准备模板参数
            tool_descriptions = "\n".join([f"- {tool.name}: {tool.description}" for tool in self.tools])
            tool_names = ", ".join([tool.name for tool in self.tools])
            
            template_params = {
                'tools': tool_descriptions,
                'tool_names': tool_names,
                'database_name': getattr(self.db_config, 'database', 'unknown'),
                **runtime_params
            }
            
            # 加载系统提示词模板
            try:
                system_prompt = prompt_manager.render_template('system/main.j2', **template_params)
                return ChatPromptTemplate.from_messages([
                    ("system", system_prompt),
                    ("human", "{input}"),
                    ("assistant", "{agent_scratchpad}")
                ])
            except Exception as e:
                self.logger.error(f"Failed to load system template: {e}")
                # 使用简化的默认提示词
                return self._get_default_prompt(tool_descriptions, tool_names)
                
        except Exception as e:
            self.logger.warning(f"Failed to create prompt: {e}")
            return self._get_default_prompt("", "")
    
    def _get_default_prompt(self, tool_descriptions: str, tool_names: str) -> ChatPromptTemplate:
        """获取默认提示词"""
        return ChatPromptTemplate.from_messages([
            ("system", f"""你是专业的NL2SQL训练数据生成专家，基于ReAct模式工作。

可用工具:
{tool_descriptions}

使用ReAct格式:
Thought: 分析当前情况，决定下一步
Action: 工具名称 [{tool_names}]
Action Input: 工具参数
Observation: 工具结果
...
Final Answer: 最终结果

请根据任务需求，完全自主地选择和使用工具。"""),
            ("human", "{input}"),
            ("assistant", "{agent_scratchpad}")
        ])
    
    
    def _create_agent(self) -> AgentExecutor:
        """创建统一的Agent（简化版）"""
        # 创建提示词模板
        prompt = self._create_prompt()
        
        # 创建ReAct agent（使用所有工具）
        agent = create_react_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt
        )
        
        # 创建执行器
        callbacks = [self.callback_handler]
        if hasattr(self, 'extra_callbacks'):
            callbacks.extend(self.extra_callbacks)
        
        return AgentExecutor(
            agent=agent,
            tools=self.tools,  # 所有工具，无过滤
            memory=self.memory,
            verbose=True,
            max_iterations=100,  # 足够处理所有场景组合
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
            
            # 创建执行参数
            execution_params = self._create_execution_params(task, **kwargs)
            
            # 创建或使用已有的Agent执行器
            if not self.agent_executor:
                self.agent_executor = self._create_agent()
            
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
        """获取记忆状态摘要（简化版）"""
        try:
            if hasattr(self.memory, 'get_summary'):
                return self.memory.get_summary()
            else:
                return "记忆系统可用"
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