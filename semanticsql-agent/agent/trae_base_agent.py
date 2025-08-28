"""
trae_agent风格的BaseAgent - 抽象ReAct模式实现
"""

import json
import logging
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum

from utils.llm_clients.llm_client import LLMClient
from utils.trajectory_recorder import TrajectoryRecorder


class AgentState(Enum):
    """Agent执行状态"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


class StepState(Enum):
    """步骤执行状态"""
    PENDING = "pending"
    THINKING = "thinking"
    CALLING_TOOL = "calling_tool"
    TOOL_EXECUTED = "tool_executed"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class ToolCall:
    """工具调用信息"""
    id: str
    name: str
    arguments: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)


@dataclass
class ToolResult:
    """工具执行结果"""
    call_id: str
    name: str
    success: bool
    output: Any = None
    error: str = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentStep:
    """Agent执行步骤"""
    step_id: int
    state: StepState
    thought: Optional[str] = None
    tool_calls: List[ToolCall] = field(default_factory=list)
    tool_results: List[ToolResult] = field(default_factory=list)
    error: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentExecution:
    """Agent执行结果"""
    task: str
    state: AgentState
    steps: List[AgentStep] = field(default_factory=list)
    final_result: Any = None
    error: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def execution_time(self) -> float:
        """执行时间"""
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time
    
    @property
    def success(self) -> bool:
        """是否成功"""
        return self.state == AgentState.COMPLETED


class BaseTool(ABC):
    """trae_agent风格的工具基类"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """获取OpenAI函数调用schema"""
        pass
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """执行工具"""
        pass
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """验证参数（可选实现）"""
        return True, None


class BaseAgent(ABC):
    """trae_agent风格的BaseAgent - 抽象ReAct模式"""
    
    def __init__(
        self,
        name: str,
        llm_client: LLMClient,
        tools: List[BaseTool],
        max_steps: int = 10,
        verbose: bool = False,
        enable_trajectory: bool = True
    ):
        self.name = name
        self.llm_client = llm_client
        self.tools = {tool.name: tool for tool in tools}
        self.max_steps = max_steps
        self.verbose = verbose
        self.enable_trajectory = enable_trajectory
        
        self.logger = logging.getLogger(f"{__name__}.{name}")
        self.trajectory_recorder = TrajectoryRecorder() if enable_trajectory else None
        
    async def execute_task(self, task: str, context: Optional[Dict[str, Any]] = None) -> AgentExecution:
        """执行任务 - ReAct主循环"""
        execution = AgentExecution(
            task=task,
            state=AgentState.RUNNING,
            metadata={"context": context or {}}
        )
        
        if self.verbose:
            self.logger.info(f"开始执行任务: {task}")
        
        # 开始记录轨迹
        if self.trajectory_recorder:
            self.trajectory_recorder.start_recording(task=task)
        
        try:
            # 构建系统消息
            system_message = self._build_system_message()
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": task}
            ]
            
            # ReAct循环
            for step_id in range(1, self.max_steps + 1):
                if execution.state != AgentState.RUNNING:
                    break
                
                step = await self._execute_react_step(
                    step_id=step_id,
                    messages=messages,
                    context=context or {}
                )
                execution.steps.append(step)
                
                # 检查是否完成
                if self._is_task_complete(step, execution):
                    execution.state = AgentState.COMPLETED
                    break
            
            # 检查最大步骤数
            if execution.state == AgentState.RUNNING and len(execution.steps) >= self.max_steps:
                execution.state = AgentState.ERROR
                execution.error = f"达到最大步骤数: {self.max_steps}"
            
        except Exception as e:
            execution.state = AgentState.ERROR
            execution.error = str(e)
            self.logger.error(f"任务执行失败: {e}")
        
        finally:
            execution.end_time = time.time()
            
            # 提取最终结果
            if execution.state == AgentState.COMPLETED:
                execution.final_result = self._extract_final_result(execution)
            
            # 记录轨迹
            if self.trajectory_recorder:
                self.trajectory_recorder.end_recording(
                    execution=execution,
                    success=execution.success,
                    final_result=execution.final_result
                )
        
        return execution
    
    async def _execute_react_step(
        self,
        step_id: int,
        messages: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> AgentStep:
        """执行ReAct单步"""
        step = AgentStep(
            step_id=step_id,
            state=StepState.THINKING
        )
        
        try:
            # 1. Thought: LLM思考
            if self.verbose:
                self.logger.info(f"步骤 {step_id}: 思考中...")
            
            # 构建工具schema
            tool_schemas = [tool.get_schema() for tool in self.tools.values()]
            
            # 调用LLM
            llm_response = await self.llm_client.acreate_chat_completion(
                messages=messages,
                tools=tool_schemas if tool_schemas else None
            )
            
            step.thought = llm_response.get("content", "")
            
            # 记录LLM交互
            if self.trajectory_recorder:
                self.trajectory_recorder.record_llm_interaction(
                    messages=messages,
                    response=llm_response
                )
            
            # 2. Action: 处理工具调用
            tool_calls = llm_response.get("tool_calls", [])
            if tool_calls:
                step.state = StepState.CALLING_TOOL
                
                for tool_call_data in tool_calls:
                    tool_call = ToolCall(
                        id=tool_call_data.get("id", ""),
                        name=tool_call_data.get("function", {}).get("name", ""),
                        arguments=json.loads(tool_call_data.get("function", {}).get("arguments", "{}"))
                    )
                    step.tool_calls.append(tool_call)
                    
                    # 执行工具
                    tool_result = await self._execute_tool(tool_call)
                    step.tool_results.append(tool_result)
                    
                    # 添加观察结果到消息
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result.output) if tool_result.success else tool_result.error
                    })
                
                step.state = StepState.TOOL_EXECUTED
            
            # 3. 完成步骤
            step.state = StepState.COMPLETED
            step.end_time = time.time()
            
        except Exception as e:
            step.state = StepState.ERROR
            step.error = str(e)
            self.logger.error(f"步骤 {step_id} 执行失败: {e}")
            step.end_time = time.time()
        
        return step
    
    async def _execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """执行工具调用"""
        tool = self.tools.get(tool_call.name)
        if not tool:
            return ToolResult(
                call_id=tool_call.id,
                name=tool_call.name,
                success=False,
                error=f"工具不存在: {tool_call.name}"
            )
        
        try:
            # 验证参数
            valid, error_msg = tool.validate_parameters(tool_call.arguments)
            if not valid:
                return ToolResult(
                    call_id=tool_call.id,
                    name=tool_call.name,
                    success=False,
                    error=error_msg
                )
            
            # 执行工具
            start_time = time.time()
            result = await tool.execute(**tool_call.arguments)
            execution_time = time.time() - start_time
            
            return ToolResult(
                call_id=tool_call.id,
                name=tool_call.name,
                success=True,
                output=result,
                execution_time=execution_time
            )
            
        except Exception as e:
            return ToolResult(
                call_id=tool_call.id,
                name=tool_call.name,
                success=False,
                error=str(e)
            )
    
    def _build_system_message(self) -> str:
        """构建系统消息"""
        tools_info = []
        for name, tool in self.tools.items():
            schema = tool.get_schema()
            tools_info.append(f"- {name}: {tool.description}")
        
        return f"""你是一个专业的AI助手，具备以下工具可以使用：

{chr(10).join(tools_info)}

请使用ReAct模式解决问题：
1. 思考当前情况和下一步行动
2. 如果需要使用工具，请调用适当的工具
3. 根据工具结果继续思考
4. 重复直到完成任务

始终以中文进行思考和回答。"""
    
    @abstractmethod
    def _is_task_complete(self, step: AgentStep, execution: AgentExecution) -> bool:
        """判断任务是否完成"""
        pass
    
    @abstractmethod
    def _extract_final_result(self, execution: AgentExecution) -> Any:
        """提取最终结果"""
        pass
    
    def get_trajectory(self) -> Optional[Dict[str, Any]]:
        """获取执行轨迹"""
        if self.trajectory_recorder:
            return self.trajectory_recorder.get_trajectory()
        return None