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
    
    def _determine_execution_stage(self) -> str:
        """根据Memory状态智能判断当前执行阶段
        
        Returns:
            'analysis' 或 'generation'
        """
        try:
            memory_state = self.get_memory_state()
            
            # 检查分析阶段的关键要素是否完成
            analysis_indicators = [
                'schema_info', 'domain_info', 'field_classification', 
                'column_meanings', 'table_meanings', 'er_relationships'
            ]
            
            # 统计已完成的分析项目
            completed_analysis = sum(
                1 for key in analysis_indicators 
                if memory_state.get(key) and len(str(memory_state[key])) > 10
            )
            
            # 如果完成了大部分分析（至少4项），则进入生成阶段
            if completed_analysis >= 4:
                return 'generation'
            else:
                return 'analysis'
                
        except Exception as e:
            self.logger.warning(f"Failed to determine stage, defaulting to analysis: {e}")
            return 'analysis'
    
    def _create_execution_params(self, task: str, **kwargs) -> Dict[str, Any]:
        """根据当前阶段智能创建执行参数
        
        Args:
            task: 任务描述
            **kwargs: 额外参数
            
        Returns:
            阶段特定的执行参数字典
        """
        # 判断当前执行阶段
        current_stage = self._determine_execution_stage()
        
        # 基础参数（所有阶段都需要）
        params = {
            "input": task,
            "database_name": getattr(self.db_config, 'database', 'unknown'),
            "memory_summary": self._get_memory_summary(),
        }
        
        # 根据阶段添加特定参数
        if current_stage == 'generation':
            # 生成阶段需要iteration参数
            iteration = kwargs.get('iteration', 0)
            params["iteration"] = iteration
            self.logger.info(f"Generation stage - iteration: {iteration}")
        else:
            # 分析阶段不需要iteration参数，确保不传入
            self.logger.info("Analysis stage - no iteration parameter needed")
        
        # 添加其他kwargs（除了iteration，因为已经处理过了）
        for key, value in kwargs.items():
            if key != 'iteration':  # iteration已经根据阶段处理过了
                params[key] = value
        
        return params
    
    def _get_stage_relevant_tools(self, stage: str, iteration: int = 0) -> List[BaseTool]:
        """根据阶段和iteration获取相关工具
        
        Args:
            stage: 当前阶段 ('analysis' 或 'generation')
            iteration: 当前iteration（仅生成阶段使用）
            
        Returns:
            当前阶段相关的工具列表
        """
        if stage == 'analysis':
            # 分析阶段：只返回分析相关工具
            return [tool for tool in self.tools if self._is_analysis_tool(tool)]
        
        elif stage == 'generation':
            # 生成阶段：根据iteration返回相应工具
            return [tool for tool in self.tools if self._is_generation_relevant_tool(tool, iteration)]
        
        else:
            # 默认返回所有工具
            return self.tools
    
    def _is_analysis_tool(self, tool: BaseTool) -> bool:
        """判断是否为分析阶段工具"""
        analysis_tool_names = {
            'schema_extraction', 'domain_analysis', 'field_classification',
            'column_meaning_analysis', 'table_meaning_analysis', 'er_analysis',
            'sequential_thinking'  # 分析阶段也可能需要深度思考
        }
        return tool.name in analysis_tool_names
    
    def _is_generation_relevant_tool(self, tool: BaseTool, iteration: int) -> bool:
        """判断工具是否与当前生成iteration相关"""
        # 始终可用的工具
        always_available = {
            'sequential_thinking', 'sql_reflection', 
            'sql_validation', 'sql_execution'
        }
        
        if tool.name in always_available:
            return True
        
        # 根据您描述的动态注入逻辑
        # 这里可以根据具体需求进一步细化
        generation_tools = {
            'scenario_tool', 'operation_selection', 
            'question_generation', 'sql_generation'
        }
        
        return tool.name in generation_tools
    
    def _create_prompt(self, **runtime_params) -> ChatPromptTemplate:
        """创建统一的Agent提示词模板
        
        Args:
            **runtime_params: 运行时参数，包含iteration等信息
            
        Returns:
            统一的ChatPromptTemplate，支持智能阶段感知
        """
        try:
            from prompts.manager import PromptManager
            prompt_manager = PromptManager()
            
            # 判断当前阶段
            current_stage = self._determine_execution_stage()
            iteration = runtime_params.get('iteration', 0)
            
            # 获取阶段相关的工具
            relevant_tools = self._get_stage_relevant_tools(current_stage, iteration)
            
            # 准备模板参数
            tool_descriptions = "\n".join([f"- {tool.name}: {tool.description}" for tool in relevant_tools])
            tool_names = ", ".join([tool.name for tool in relevant_tools])
            
            # 基础参数（所有阶段都需要）
            template_params = {
                'tools': tool_descriptions,
                'tool_names': tool_names,
                'database_name': getattr(self.db_config, 'database', 'unknown'),
                'memory_summary': self._get_memory_summary()
            }
            
            # 如果是生成阶段且有iteration，添加到模板参数中
            if current_stage == 'generation' and iteration is not None:
                template_params['iteration'] = iteration
            
            # 加载统一的智能模板
            try:
                system_prompt = prompt_manager.render_template('system/main.j2', **template_params)
            except Exception as e:
                self.logger.error(f"Failed to load main.j2 template: {e}")
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
... (这个过程可以重复多次)
Thought: 我现在知道最终答案了
Final Answer: 最终结果

请根据任务需求，灵活选择和使用工具。"""),
                ("human", "{input}"),
                ("assistant", "{agent_scratchpad}")
            ])
    
    def _create_stage_aware_agent(self, execution_params: Dict[str, Any]) -> AgentExecutor:
        """根据执行参数动态创建阶段感知的Agent
        
        Args:
            execution_params: 执行参数，包含阶段和iteration信息
            
        Returns:
            配置了正确工具集合的AgentExecutor
        """
        # 从执行参数中提取阶段信息
        current_stage = self._determine_execution_stage()
        iteration = execution_params.get('iteration', 0)
        
        # 获取当前阶段相关的工具
        relevant_tools = self._get_stage_relevant_tools(current_stage, iteration)
        
        self.logger.info(
            f"Creating {current_stage} stage agent with {len(relevant_tools)} tools"
            f"{f' (iteration {iteration})' if current_stage == 'generation' else ''}"
        )
        
        # 创建提示词模板（传入iteration信息）
        prompt = self._create_prompt(iteration=iteration)
        
        # 创建 ReAct agent（使用过滤后的工具）
        agent = create_react_agent(
            llm=self.llm,
            tools=relevant_tools,
            prompt=prompt
        )
        
        # 创建执行器
        callbacks = [self.callback_handler]
        if hasattr(self, 'extra_callbacks'):
            callbacks.extend(self.extra_callbacks)
        
        return AgentExecutor(
            agent=agent,
            tools=relevant_tools,  # 使用过滤后的工具
            memory=self.memory,
            verbose=True,
            max_iterations=self.settings.max_steps,
            handle_parsing_errors=True,
            callbacks=callbacks
        )
    
    def _create_agent(self) -> AgentExecutor:
        """创建 LangChain Agent（兼容性方法，建议使用_create_stage_aware_agent）"""
        # 创建统一的提示词模板
        prompt = self._create_prompt(iteration=0)
        
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
            
            # 智能创建阶段感知的执行参数
            execution_params = self._create_execution_params(task, **kwargs)
            
            # 动态创建阶段相关的Agent执行器
            agent_executor = self._create_stage_aware_agent(execution_params)
            
            result = agent_executor.invoke(execution_params)
            
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