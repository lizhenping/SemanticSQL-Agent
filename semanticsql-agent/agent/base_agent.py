"""基础智能体类

参考 TRAEAgent 的 BaseAgent 设计，保持简洁。
"""

import asyncio
import time
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage

from config import AgentConfig, ModelConfig
from tools.base import BaseSemanticSQLTool
from utils import create_llm_client

from .agent_basics import (
    AgentState, AgentStepState, AgentStep, AgentExecution,
    AgentError, LLMUsage, LLMResponse, ToolCall, ToolResult
)
from utils.trajectory_recorder import TrajectoryRecorder

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """基础智能体类"""
    
    def __init__(self, config: AgentConfig):
        """初始化智能体"""
        self.config = config
        self._model_config = config.model
        self._llm_client = create_llm_client(config.model)
        self._max_steps = config.max_steps
        self._tools: List[BaseSemanticSQLTool] = []
        self._trajectory_recorder = TrajectoryRecorder(config.trajectory_dir)
        
        # 任务相关
        self._task: str = ""
        self._initial_messages: List[BaseMessage] = []
    
    @property
    def llm_client(self) -> BaseChatModel:
        return self._llm_client
    
    @property
    def model_config(self) -> ModelConfig:
        return self._model_config
    
    @property
    def max_steps(self) -> int:
        return self._max_steps
    
    @property
    def tools(self) -> List[BaseSemanticSQLTool]:
        return self._tools
    
    @abstractmethod
    def new_task(self, task: str, extra_args: Optional[Dict[str, Any]] = None) -> None:
        """创建新任务"""
        pass
    
    async def execute_task(self) -> AgentExecution:
        """执行任务 - ReAct 循环"""
        if not self._task:
            raise AgentError("没有创建任务")
        
        start_time = time.time()
        
        # 创建执行记录
        execution = AgentExecution(task=self._task)
        execution.agent_state = AgentState.RUNNING
        
        # 开始轨迹记录
        self._trajectory_recorder.start_recording(
            task=self._task,
            provider=self._model_config.provider,
            model=self._model_config.model,
            max_steps=self._max_steps
        )
        
        try:
            messages = self._initial_messages.copy()
            step_number = 1
            
            while step_number <= self._max_steps:
                step = AgentStep(step_number=step_number, state=AgentStepState.THINKING)
                
                try:
                    # 执行单个步骤
                    messages = await self._run_llm_step(step, messages, execution)
                    
                    # 记录步骤
                    execution.steps.append(step)
                    self._trajectory_recorder.record_agent_step(step, messages[-3:])
                    
                    # 检查是否完成
                    if self._is_task_completed(step, execution):
                        execution.agent_state = AgentState.COMPLETED
                        break
                    
                    step_number += 1
                    
                except Exception as error:
                    execution.agent_state = AgentState.ERROR
                    step.state = AgentStepState.ERROR
                    step.error = str(error)
                    execution.steps.append(step)
                    break
            
            # 超过最大步骤
            if step_number > self._max_steps and execution.agent_state == AgentState.RUNNING:
                execution.agent_state = AgentState.ERROR
                raise AgentError(f"超过最大步骤数 {self._max_steps}")
            
        except Exception as e:
            execution.agent_state = AgentState.ERROR
            execution.final_result = f"执行失败: {str(e)}"
        
        # 完成执行
        execution.execution_time = time.time() - start_time
        execution.success = execution.agent_state == AgentState.COMPLETED
        
        if execution.success:
            execution.final_result = self._extract_final_result(execution)
        
        # 结束轨迹记录
        self._trajectory_recorder.end_recording(
            execution=execution,
            success=execution.success,
            final_result=execution.final_result
        )
        
        return execution
    
    async def _run_llm_step(
        self,
        step: AgentStep,
        messages: List[BaseMessage],
        execution: AgentExecution
    ) -> List[BaseMessage]:
        """执行单个 LLM 步骤"""
        # 1. 思考阶段
        llm_response = await self._llm_client.ainvoke(messages)
        
        # 解析响应
        step.llm_response = self._parse_llm_response(llm_response)
        step.thought = step.llm_response.content
        
        # 记录 LLM 交互
        self._trajectory_recorder.record_llm_interaction(
            messages=messages,
            response=step.llm_response,
            provider=self._model_config.provider,
            model=self._model_config.model,
            tools=self._tools
        )
        
        # 更新消息
        messages.append(AIMessage(content=step.llm_response.content))
        
        # 2. 工具调用阶段
        if step.llm_response.tool_calls:
            step.state = AgentStepState.CALLING_TOOL
            step.tool_calls = step.llm_response.tool_calls
            
            # 执行工具
            tool_results = await self._execute_tool_calls(step.llm_response.tool_calls)
            step.tool_results = tool_results
            
            # 更新消息
            for tool_call, tool_result in zip(step.tool_calls, tool_results):
                content = str(tool_result.result) if tool_result.success else tool_result.error
                messages.append(ToolMessage(content=content, tool_call_id=tool_call.call_id))
            
            # 3. 反思阶段（可选）
            reflection = self.reflect_on_results(tool_results)
            if reflection:
                step.state = AgentStepState.REFLECTING
                step.reflection = reflection
        
        return messages
    
    def _parse_llm_response(self, response: Any) -> LLMResponse:
        """解析 LLM 响应"""
        content = response.content if hasattr(response, 'content') else str(response)
        model = self._model_config.model
        
        # 提取工具调用
        tool_calls = None
        if hasattr(response, 'tool_calls') and response.tool_calls:
            tool_calls = []
            for tc in response.tool_calls:
                tool_call = ToolCall(
                    name=tc.get('name', ''),
                    call_id=tc.get('id', ''),
                    arguments=tc.get('args', {})
                )
                tool_calls.append(tool_call)
        
        return LLMResponse(
            content=content,
            model=model,
            finish_reason='stop',
            tool_calls=tool_calls
        )
    
    async def _execute_tool_calls(self, tool_calls: List[ToolCall]) -> List[ToolResult]:
        """执行工具调用"""
        tasks = []
        for tool_call in tool_calls:
            task = self._execute_single_tool(tool_call)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        tool_results = []
        for tool_call, result in zip(tool_calls, results):
            if isinstance(result, Exception):
                tool_result = ToolResult(
                    call_id=tool_call.call_id,
                    name=tool_call.name,
                    success=False,
                    error=str(result)
                )
            else:
                tool_result = result
            tool_results.append(tool_result)
        
        return tool_results
    
    async def _execute_single_tool(self, tool_call: ToolCall) -> ToolResult:
        """执行单个工具"""
        # 查找工具
        tool = next((t for t in self._tools if t.name == tool_call.name), None)
        if not tool:
            return ToolResult(
                call_id=tool_call.call_id,
                name=tool_call.name,
                success=False,
                error=f"未找到工具: {tool_call.name}"
            )
        
        try:
            result = await tool.arun(**tool_call.arguments)
            return ToolResult(
                call_id=tool_call.call_id,
                name=tool_call.name,
                success=True,
                result=result
            )
        except Exception as e:
            return ToolResult(
                call_id=tool_call.call_id,
                name=tool_call.name,
                success=False,
                error=str(e)
            )
    
    def reflect_on_results(self, tool_results: List[ToolResult]) -> Optional[str]:
        """对结果进行反思（可选）"""
        # 默认不反思，子类可重写
        return None
    
    @abstractmethod
    def _is_task_completed(self, step: AgentStep, execution: AgentExecution) -> bool:
        """判断任务是否完成"""
        pass
    
    @abstractmethod
    def _extract_final_result(self, execution: AgentExecution) -> Any:
        """提取最终结果"""
        pass