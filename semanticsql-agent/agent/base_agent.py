"""基础智能体类

参考 TRAEAgent 的 BaseAgent 设计，提供智能体的基础功能。
"""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Union

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import BaseTool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.prebuilt import create_react_agent

from models import QueryResult
from config import AgentConfig, ModelConfig
from tools.base import BaseSemanticSQLTool, ToolCall, ToolResult
from utils import create_llm_client

from .agent_state import (
    AgentState, StepState, AgentStep, AgentExecution, 
    AgentContext, AgentError, MaxStepsExceededError
)
from .trajectory import TrajectoryRecorder


class BaseAgent(ABC):
    """基础智能体类
    
    提供智能体的核心功能：
    1. ReAct 执行循环
    2. 工具管理
    3. 状态管理
    4. 轨迹记录
    """
    
    def __init__(self, config: AgentConfig):
        """初始化智能体
        
        Args:
            config: 智能体配置
        """
        self.config = config
        self.llm = self._init_llm(config.model)
        self.max_steps = config.max_steps
        self.tools: List[BaseSemanticSQLTool] = []
        self.trajectory_recorder = TrajectoryRecorder(config.trajectory_dir)
        
        # 当前任务相关
        self._task: str = ""
        self._context: AgentContext = AgentContext()
        self._messages: List[BaseMessage] = []
        
        # ReAct 智能体（延迟初始化）
        self._react_agent = None
    
    def _init_llm(self, model_config: ModelConfig) -> BaseChatModel:
        """初始化语言模型"""
        return create_llm_client(model_config)
    
    @property
    def task(self) -> str:
        """当前任务"""
        return self._task
    
    @property
    def context(self) -> AgentContext:
        """当前上下文"""
        return self._context
    
    @abstractmethod
    def create_task(self, query: str, context: Optional[Dict[str, Any]] = None) -> None:
        """创建新任务
        
        Args:
            query: 用户查询
            context: 额外的上下文信息
        """
        pass
    
    @abstractmethod
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        pass
    
    @abstractmethod
    def _create_tools(self) -> List[BaseSemanticSQLTool]:
        """创建工具集"""
        pass
    
    def _create_react_agent(self):
        """创建 ReAct 智能体"""
        if not self.tools:
            self.tools = self._create_tools()
        
        # 获取系统提示词
        system_prompt = self._get_system_prompt()
        
        # 创建 ReAct 智能体
        return create_react_agent(
            model=self.llm,
            tools=self.tools,
            state_modifier=system_prompt
        )
    
    async def execute_task(self) -> AgentExecution:
        """执行任务
        
        实现 ReAct (Thought-Action-Observation) 循环。
        
        Returns:
            AgentExecution: 执行结果
        """
        if not self._task:
            raise AgentError("没有创建任务")
        
        # 创建执行记录
        execution = AgentExecution(task=self._task)
        execution.state = AgentState.RUNNING
        
        # 开始记录轨迹
        self.trajectory_recorder.start_recording(execution)
        
        # 记录开始时间
        start_time = time.time()
        
        try:
            # 初始化 ReAct 智能体
            if not self._react_agent:
                self._react_agent = self._create_react_agent()
            
            # 执行 ReAct 循环
            step_number = 1
            
            while step_number <= self.max_steps:
                # 创建新步骤
                step = AgentStep(step_number=step_number)
                execution.add_step(step)
                
                try:
                    # 执行单个步骤
                    await self._run_step(step, execution)
                    
                    # 记录步骤
                    self.trajectory_recorder.record_step(step)
                    
                    # 检查是否完成
                    if self._is_task_completed(step, execution):
                        execution.state = AgentState.COMPLETED
                        break
                    
                    step_number += 1
                    
                except Exception as e:
                    step.state = StepState.ERROR
                    step.error = str(e)
                    execution.state = AgentState.ERROR
                    execution.error = str(e)
                    self.trajectory_recorder.record_step(step)
                    break
            
            # 检查是否超过最大步骤
            if step_number > self.max_steps and execution.state == AgentState.RUNNING:
                execution.state = AgentState.ERROR
                execution.error = f"超过最大步骤数 {self.max_steps}"
                raise MaxStepsExceededError(execution.error)
            
        except Exception as e:
            execution.state = AgentState.ERROR
            execution.error = str(e)
            
        finally:
            # 记录执行时间
            execution.execution_time = time.time() - start_time
            execution.completed_at = time.time()
            
            # 设置最终结果
            if execution.state == AgentState.COMPLETED:
                execution.final_result = self._extract_final_result(execution)
                execution.final_sql = self._context.generated_sql
            
            # 结束轨迹记录
            self.trajectory_recorder.end_recording()
        
        return execution
    
    async def _run_step(self, step: AgentStep, execution: AgentExecution) -> None:
        """执行单个步骤
        
        实现 Thought -> Action -> Observation 循环。
        
        Args:
            step: 当前步骤
            execution: 执行记录
        """
        # 1. Thought - 思考阶段
        step.state = StepState.THINKING
        thought_response = await self._think(execution)
        step.thought = thought_response
        
        # 2. Action - 行动阶段
        if tool_call := self._parse_tool_call(thought_response):
            step.state = StepState.ACTING
            step.action = tool_call
            
            # 执行工具
            tool_result = await self._execute_tool(tool_call)
            
            # 3. Observation - 观察阶段
            step.state = StepState.OBSERVING
            step.observation = tool_result
            
            # 更新上下文
            self._update_context(tool_call, tool_result)
            
            # 更新消息历史
            self._update_messages(step)
        
        # 完成步骤
        step.state = StepState.COMPLETED
    
    async def _think(self, execution: AgentExecution) -> str:
        """思考阶段 - 让 LLM 决定下一步行动
        
        Args:
            execution: 执行记录
            
        Returns:
            思考结果
        """
        # 构建消息
        messages = self._build_messages(execution)
        
        # 调用 LLM
        response = await self.llm.ainvoke(messages)
        
        return response.content
    
    def _parse_tool_call(self, thought: str) -> Optional[ToolCall]:
        """解析工具调用
        
        Args:
            thought: LLM 的思考结果
            
        Returns:
            工具调用信息，如果没有则返回 None
        """
        # 这里应该解析 LLM 输出中的工具调用
        # 简化实现，实际应该使用更复杂的解析逻辑
        import re
        
        # 查找工具调用模式
        tool_pattern = r'Tool:\s*(\w+)\s*\nInput:\s*({.*?})'
        match = re.search(tool_pattern, thought, re.DOTALL)
        
        if match:
            tool_name = match.group(1)
            try:
                import json
                tool_args = json.loads(match.group(2))
                return ToolCall(tool=tool_name, args=tool_args)
            except:
                pass
        
        return None
    
    async def _execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """执行工具
        
        Args:
            tool_call: 工具调用信息
            
        Returns:
            工具执行结果
        """
        # 查找工具
        tool = next((t for t in self.tools if t.name == tool_call.tool), None)
        
        if not tool:
            return ToolResult(
                success=False,
                error=f"未找到工具: {tool_call.tool}"
            )
        
        try:
            # 执行工具
            result = await tool.arun(**tool_call.args)
            return ToolResult(success=True, result=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    def _update_context(self, tool_call: ToolCall, tool_result: ToolResult) -> None:
        """更新上下文
        
        Args:
            tool_call: 工具调用
            tool_result: 工具结果
        """
        if not tool_result.success:
            return
        
        # 根据工具类型更新上下文
        if tool_call.tool == "extract_database_schema":
            self._context.schema_info = tool_result.result
        elif tool_call.tool == "analyze_business_domain":
            self._context.domain_analysis = tool_result.result
        elif tool_call.tool == "classify_table_fields":
            self._context.field_classifications = tool_result.result
        elif tool_call.tool == "analyze_entity_relationships":
            self._context.relationships = tool_result.result
        elif tool_call.tool == "generate_sql":
            self._context.generated_sql = tool_result.result
        elif tool_call.tool == "validate_sql":
            self._context.validation_result = tool_result.result
        elif tool_call.tool == "execute_sql":
            self._context.execution_result = tool_result.result
    
    def _update_messages(self, step: AgentStep) -> None:
        """更新消息历史"""
        # 添加 AI 的思考
        if step.thought:
            self._messages.append(AIMessage(content=step.thought))
        
        # 添加工具调用和结果
        if step.action and step.observation:
            tool_message = f"Tool: {step.action.tool}\nResult: {step.observation.result if step.observation.success else step.observation.error}"
            self._messages.append(ToolMessage(content=tool_message, tool_call_id=str(step.step_number)))
    
    def _build_messages(self, execution: AgentExecution) -> List[BaseMessage]:
        """构建消息列表"""
        messages = []
        
        # 添加系统消息（通过 ChatPromptTemplate）
        system_prompt = self._get_system_prompt()
        
        # 添加用户查询
        messages.append(HumanMessage(content=self._task))
        
        # 添加历史消息
        messages.extend(self._messages)
        
        return messages
    
    @abstractmethod
    def _is_task_completed(self, step: AgentStep, execution: AgentExecution) -> bool:
        """判断任务是否完成"""
        pass
    
    @abstractmethod
    def _extract_final_result(self, execution: AgentExecution) -> Any:
        """提取最终结果"""
        pass
    
    def reflect_on_result(self, result: ToolResult) -> Optional[str]:
        """对结果进行反思
        
        参考 TRAEAgent，默认不进行反思，子类可以覆盖。
        
        Args:
            result: 工具执行结果
            
        Returns:
            反思内容，如果不需要反思则返回 None
        """
        return None