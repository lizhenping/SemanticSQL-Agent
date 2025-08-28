"""基础智能体类

参考 TRAEAgent 的 BaseAgent 设计，提供智能体的基础功能。
"""

import asyncio
import time
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import BaseTool

from config import AgentConfig, ModelConfig
from tools.base import BaseSemanticSQLTool
from utils import create_llm_client

from .agent_basics import (
    AgentState, AgentStepState, AgentStep, AgentExecution,
    AgentError, MaxStepsExceededError, ToolExecutionError,
    LLMUsage, LLMResponse, ToolCall, ToolResult
)
from .trajectory_recorder import TrajectoryRecorder

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """基础智能体类
    
    提供智能体的核心功能：
    1. ReAct 执行循环
    2. 工具管理和执行
    3. 状态管理
    4. 轨迹记录
    5. 反思机制（可选）
    """
    
    def __init__(self, config: AgentConfig):
        """初始化智能体
        
        Args:
            config: 智能体配置
        """
        self.config = config
        self._model_config = config.model
        self._llm_client = self._init_llm(config.model)
        self._max_steps = config.max_steps
        self._tools: List[BaseSemanticSQLTool] = []
        self._trajectory_recorder = TrajectoryRecorder(config.trajectory_dir)
        
        # 任务相关
        self._task: str = ""
        self._initial_messages: List[BaseMessage] = []
        
        # 执行状态
        self._current_execution: Optional[AgentExecution] = None
        
        logger.info(f"初始化 {self.__class__.__name__}")
    
    def _init_llm(self, model_config: ModelConfig) -> BaseChatModel:
        """初始化语言模型"""
        return create_llm_client(model_config)
    
    @property
    def llm_client(self) -> BaseChatModel:
        """获取 LLM 客户端"""
        return self._llm_client
    
    @property
    def model_config(self) -> ModelConfig:
        """获取模型配置"""
        return self._model_config
    
    @property
    def max_steps(self) -> int:
        """获取最大步骤数"""
        return self._max_steps
    
    @property
    def tools(self) -> List[BaseSemanticSQLTool]:
        """获取工具列表"""
        return self._tools
    
    @abstractmethod
    def new_task(
        self,
        task: str,
        extra_args: Optional[Dict[str, Any]] = None,
        tool_names: Optional[List[str]] = None
    ) -> None:
        """创建新任务
        
        Args:
            task: 任务描述
            extra_args: 额外参数
            tool_names: 指定使用的工具名称
        """
        pass
    
    async def execute_task(self) -> AgentExecution:
        """执行任务
        
        实现 ReAct 循环，支持批量工具调用和可选的反思机制。
        
        Returns:
            AgentExecution: 执行结果
        """
        if not self._task:
            raise AgentError("没有创建任务")
        
        start_time = datetime.now()
        
        # 创建执行记录
        execution = AgentExecution(
            task=self._task,
            provider=self._model_config.provider,
            model=self._model_config.model,
            max_steps=self._max_steps,
            start_time=start_time
        )
        execution.agent_state = AgentState.RUNNING
        self._current_execution = execution
        
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
                    self._finalize_step(step, messages, execution)
                    
                    # 检查是否完成
                    if execution.agent_state == AgentState.COMPLETED:
                        break
                    
                    step_number += 1
                    
                except Exception as error:
                    execution.agent_state = AgentState.ERROR
                    step.state = AgentStepState.ERROR
                    step.error = str(error)
                    self._finalize_step(step, messages, execution)
                    break
            
            # 检查是否超过最大步骤
            if step_number > self._max_steps and execution.agent_state == AgentState.RUNNING:
                execution.final_result = f"任务执行超过最大步骤数 {self._max_steps}"
                execution.agent_state = AgentState.ERROR
                raise MaxStepsExceededError(execution.final_result)
            
        except Exception as e:
            execution.agent_state = AgentState.ERROR
            execution.error = str(e)
            execution.final_result = f"智能体执行失败: {str(e)}"
        
        finally:
            # 完成执行
            execution.end_time = datetime.now()
            execution.execution_time = (execution.end_time - start_time).total_seconds()
            execution.success = execution.agent_state == AgentState.COMPLETED
            
            # 结束轨迹记录
            self._trajectory_recorder.end_recording(
                execution=execution,
                success=execution.success,
                final_result=execution.final_result
            )
            
            self._current_execution = None
        
        return execution
    
    async def _run_llm_step(
        self,
        step: AgentStep,
        messages: List[BaseMessage],
        execution: AgentExecution
    ) -> List[BaseMessage]:
        """执行单个 LLM 步骤
        
        Args:
            step: 当前步骤
            messages: 消息历史
            execution: 执行记录
            
        Returns:
            更新后的消息列表
        """
        # 1. 思考阶段 - 调用 LLM
        step.state = AgentStepState.THINKING
        llm_response = await self._llm_client.ainvoke(messages)
        
        # 解析 LLM 响应
        parsed_response = self._parse_llm_response(llm_response)
        step.llm_response = parsed_response
        step.thought = parsed_response.content
        step.llm_usage = parsed_response.usage
        
        # 记录 LLM 交互
        self._trajectory_recorder.record_llm_interaction(
            messages=messages,
            response=parsed_response,
            provider=self._model_config.provider,
            model=self._model_config.model,
            tools=self._tools
        )
        
        # 更新消息
        messages.append(AIMessage(content=parsed_response.content))
        
        # 2. 检查是否有工具调用
        if parsed_response.tool_calls:
            step.state = AgentStepState.CALLING_TOOL
            step.tool_calls = parsed_response.tool_calls
            
            # 执行工具调用（支持批量）
            tool_results = await self._execute_tool_calls(parsed_response.tool_calls)
            step.tool_results = tool_results
            
            # 更新消息
            for tool_call, tool_result in zip(parsed_response.tool_calls, tool_results):
                tool_message = ToolMessage(
                    content=str(tool_result.result) if tool_result.success else tool_result.error,
                    tool_call_id=tool_call.call_id
                )
                messages.append(tool_message)
            
            # 3. 反思阶段（可选）
            if self._should_reflect(tool_results):
                step.state = AgentStepState.REFLECTING
                reflection = await self._reflect_on_results(tool_results, messages)
                if reflection:
                    step.reflection = reflection
                    messages.append(AIMessage(content=f"反思: {reflection}"))
        
        # 4. 检查任务是否完成
        if self._is_task_completed(step, execution):
            execution.agent_state = AgentState.COMPLETED
            execution.final_result = self._extract_final_result(step, execution)
        
        return messages
    
    def _parse_llm_response(self, response: Any) -> LLMResponse:
        """解析 LLM 响应
        
        Args:
            response: LLM 原始响应
            
        Returns:
            标准化的 LLM 响应
        """
        # 提取基本信息
        content = response.content if hasattr(response, 'content') else str(response)
        model = getattr(response, 'response_metadata', {}).get('model_name', self._model_config.model)
        finish_reason = getattr(response, 'response_metadata', {}).get('finish_reason', 'stop')
        
        # 提取 token 使用情况
        usage = None
        if hasattr(response, 'response_metadata'):
            token_usage = response.response_metadata.get('token_usage', {})
            if token_usage:
                usage = LLMUsage(
                    input_tokens=token_usage.get('prompt_tokens', 0),
                    output_tokens=token_usage.get('completion_tokens', 0),
                    total_tokens=token_usage.get('total_tokens', 0)
                )
        
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
            finish_reason=finish_reason,
            usage=usage,
            tool_calls=tool_calls,
            raw_response=response
        )
    
    async def _execute_tool_calls(self, tool_calls: List[ToolCall]) -> List[ToolResult]:
        """执行工具调用（支持批量）
        
        Args:
            tool_calls: 工具调用列表
            
        Returns:
            工具执行结果列表
        """
        # 并行执行所有工具调用
        tasks = []
        for tool_call in tool_calls:
            task = self._execute_single_tool(tool_call)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
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
        """执行单个工具调用
        
        Args:
            tool_call: 工具调用
            
        Returns:
            工具执行结果
        """
        start_time = time.time()
        
        # 查找工具
        tool = self._find_tool(tool_call.name)
        if not tool:
            return ToolResult(
                call_id=tool_call.call_id,
                name=tool_call.name,
                success=False,
                error=f"未找到工具: {tool_call.name}"
            )
        
        try:
            # 执行工具
            result = await tool.arun(**tool_call.arguments)
            
            return ToolResult(
                call_id=tool_call.call_id,
                name=tool_call.name,
                success=True,
                result=result,
                execution_time=time.time() - start_time
            )
            
        except Exception as e:
            logger.error(f"工具 {tool_call.name} 执行失败: {e}")
            return ToolResult(
                call_id=tool_call.call_id,
                name=tool_call.name,
                success=False,
                error=str(e),
                execution_time=time.time() - start_time
            )
    
    def _find_tool(self, tool_name: str) -> Optional[BaseSemanticSQLTool]:
        """查找工具
        
        Args:
            tool_name: 工具名称
            
        Returns:
            工具实例
        """
        for tool in self._tools:
            if tool.name == tool_name:
                return tool
        return None
    
    def _should_reflect(self, tool_results: List[ToolResult]) -> bool:
        """判断是否需要反思
        
        Args:
            tool_results: 工具执行结果
            
        Returns:
            是否需要反思
        """
        # 默认：如果有工具执行失败则反思
        return any(not result.success for result in tool_results)
    
    async def _reflect_on_results(
        self,
        tool_results: List[ToolResult],
        messages: List[BaseMessage]
    ) -> Optional[str]:
        """对结果进行反思
        
        Args:
            tool_results: 工具执行结果
            messages: 消息历史
            
        Returns:
            反思内容
        """
        # 子类可以重写此方法实现具体的反思逻辑
        # 默认实现：简单的错误总结
        errors = [
            f"{result.name}: {result.error}"
            for result in tool_results
            if not result.success
        ]
        
        if errors:
            return f"工具执行遇到错误: {'; '.join(errors)}"
        
        return None
    
    def _finalize_step(
        self,
        step: AgentStep,
        messages: List[BaseMessage],
        execution: AgentExecution
    ) -> None:
        """完成步骤处理
        
        Args:
            step: 当前步骤
            messages: 消息历史
            execution: 执行记录
        """
        # 标记步骤完成
        if step.state != AgentStepState.ERROR:
            step.state = AgentStepState.COMPLETED
        
        # 添加到执行记录
        execution.add_step(step)
        
        # 记录到轨迹
        self._trajectory_recorder.record_agent_step(step, messages[-3:])  # 记录最近的消息
    
    @abstractmethod
    def _is_task_completed(self, step: AgentStep, execution: AgentExecution) -> bool:
        """判断任务是否完成
        
        Args:
            step: 当前步骤
            execution: 执行记录
            
        Returns:
            是否完成
        """
        pass
    
    @abstractmethod
    def _extract_final_result(self, step: AgentStep, execution: AgentExecution) -> Any:
        """提取最终结果
        
        Args:
            step: 最后的步骤
            execution: 执行记录
            
        Returns:
            最终结果
        """
        pass
    
    def reflect_on_result(self, result: ToolResult) -> Optional[str]:
        """对单个结果进行反思（兼容方法）
        
        参考 TRAEAgent，默认不进行反思。
        
        Args:
            result: 工具执行结果
            
        Returns:
            反思内容
        """
        return None