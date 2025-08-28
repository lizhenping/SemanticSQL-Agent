"""基础智能体类（支持 Tool Calling 的 ReAct 模式）"""

import logging
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

from .agent_basics import (
    AgentState, 
    AgentStepState, 
    AgentStep, 
    AgentExecution,
    AgentError
)
from ..utils.llm_clients import LLMClient, LLMMessage, LLMResponse, ToolCall, ToolResult as LLMToolResult
from ..utils.trajectory_recorder import TrajectoryRecorder
from ..tools.base import Tool

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """基础智能体 - 实现 ReAct 模式的 Tool Calling"""
    
    def __init__(
        self,
        llm_client: LLMClient,
        tools: List[Tool],
        max_steps: int = 10,
        verbose: bool = True
    ):
        self._llm_client = llm_client
        self._tools = {tool.name: tool for tool in tools}
        self._max_steps = max_steps
        self._verbose = verbose
        self._trajectory_recorder = TrajectoryRecorder()
        
        # 获取工具 schemas
        self._tool_schemas = [tool.get_schema() for tool in tools]
    
    def execute_task(self, task: str) -> AgentExecution:
        """执行任务 - ReAct 主循环"""
        # 初始化执行
        execution = AgentExecution(
            task=task,
            agent_state=AgentState.RUNNING
        )
        
        # 开始记录轨迹
        self._trajectory_recorder.start_recording(task=task)
        
        # 构建初始消息
        messages = [
            LLMMessage(role="system", content=self._get_system_prompt()),
            LLMMessage(role="user", content=task)
        ]
        
        # 重置 LLM 消息历史
        self._llm_client.set_message_history([])
        
        start_time = time.time()
        
        try:
            step_number = 1
            
            while step_number <= self._max_steps and execution.agent_state == AgentState.RUNNING:
                # 创建新步骤
                step = AgentStep(
                    step_number=step_number,
                    state=AgentStepState.THINKING
                )
                
                if self._verbose:
                    logger.info(f"\n=== Step {step_number} ===")
                
                try:
                    # 执行 ReAct 循环的一步
                    self._run_react_step(step, messages, execution)
                    
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
                    logger.error(f"步骤执行失败: {error}")
                    break
            
            # 超过最大步骤
            if step_number > self._max_steps and execution.agent_state == AgentState.RUNNING:
                execution.agent_state = AgentState.ERROR
                raise AgentError(f"超过最大步骤数 {self._max_steps}")
            
        except Exception as e:
            execution.agent_state = AgentState.ERROR
            execution.final_result = f"执行失败: {str(e)}"
            logger.error(f"任务执行失败: {e}")
        
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
    
    def _run_react_step(
        self,
        step: AgentStep,
        messages: List[LLMMessage],
        execution: AgentExecution
    ):
        """执行 ReAct 循环的一步"""
        
        # 1. Thought: LLM 思考下一步
        step.state = AgentStepState.THINKING
        if self._verbose:
            logger.info("🤔 Thinking...")
        
        # 调用 LLM（可能返回 tool calls）
        response = self._llm_client.chat(
            messages=messages,
            tools=self._tool_schemas,
            reuse_history=True
        )
        
        step.llm_response = response
        step.thought = response.content
        
        if self._verbose:
            logger.info(f"💭 Thought: {response.content}")
        
        # 记录 LLM 交互
        self._trajectory_recorder.record_llm_interaction(
            messages=messages,
            response=response,
            provider="qwen",
            model=self._llm_client.model,
            tools=self._tool_schemas
        )
        
        # 2. Action: 如果 LLM 决定调用工具
        if response.tool_calls:
            step.state = AgentStepState.CALLING_TOOL
            step.tool_calls = response.tool_calls
            
            if self._verbose:
                logger.info(f"🔧 Calling tools: {[tc.name for tc in response.tool_calls]}")
            
            # 执行所有工具调用
            tool_results = []
            for tool_call in response.tool_calls:
                tool_result = self._execute_tool_call(tool_call)
                tool_results.append(tool_result)
                
                # 3. Observation: 将工具结果添加到消息
                result_message = LLMMessage(
                    role="tool",
                    tool_result=LLMToolResult(
                        call_id=tool_call.call_id,
                        name=tool_call.name,
                        success=tool_result.error is None,
                        result=tool_result.output,
                        error=tool_result.error
                    )
                )
                messages.append(result_message)
                
                if self._verbose:
                    if tool_result.error:
                        logger.info(f"❌ Tool error: {tool_result.error}")
                    else:
                        logger.info(f"✅ Tool result: {tool_result.output[:200]}...")
            
            step.tool_results = tool_results
            
            # 4. Reflection: 反思工具执行结果（可选）
            reflection = self.reflect_on_results(tool_results)
            if reflection:
                step.state = AgentStepState.REFLECTING
                step.reflection = reflection
                if self._verbose:
                    logger.info(f"💭 Reflection: {reflection}")
        
        # 记录步骤
        self._trajectory_recorder.record_agent_step(step)
        execution.steps.append(step)
        
        # 完成步骤
        step.state = AgentStepState.COMPLETED
    
    def _execute_tool_call(self, tool_call: ToolCall):
        """执行单个工具调用"""
        tool = self._tools.get(tool_call.name)
        if not tool:
            logger.error(f"工具不存在: {tool_call.name}")
            return type('ToolResult', (), {
                'output': '',
                'error': f"工具不存在: {tool_call.name}",
                'metadata': None,
                'execution_time': 0.0
            })()
        
        try:
            # 执行工具
            result = tool.run(**tool_call.arguments)
            return result
        except Exception as e:
            logger.error(f"工具执行失败: {e}")
            return type('ToolResult', (), {
                'output': '',
                'error': str(e),
                'metadata': None,
                'execution_time': 0.0
            })()
    
    @abstractmethod
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        pass
    
    @abstractmethod
    def _is_task_completed(self, step: AgentStep, execution: AgentExecution) -> bool:
        """判断任务是否完成"""
        pass
    
    @abstractmethod
    def _extract_final_result(self, execution: AgentExecution) -> str:
        """提取最终结果"""
        pass
    
    def reflect_on_results(self, tool_results: List[Any]) -> Optional[str]:
        """反思工具执行结果（可被子类重写）"""
        # 默认实现：如果有错误，返回简单反思
        errors = [r for r in tool_results if hasattr(r, 'error') and r.error]
        if errors:
            return f"工具执行遇到 {len(errors)} 个错误，需要调整策略"
        return None