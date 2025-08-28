"""轨迹记录器

参考 TRAEAgent 的 trajectory_recorder.py 实现，记录详细的执行轨迹。
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage

from .agent_basics import (
    AgentStep, AgentExecution, LLMResponse, ToolCall, ToolResult, LLMUsage
)

logger = logging.getLogger(__name__)


class TrajectoryRecorder:
    """轨迹记录器
    
    记录智能体执行的详细轨迹，包括：
    1. LLM 交互历史
    2. 智能体执行步骤
    3. 工具调用和结果
    4. Token 使用统计
    """
    
    def __init__(self, trajectory_path: Optional[str] = None):
        """初始化轨迹记录器
        
        Args:
            trajectory_path: 轨迹文件路径，如果为 None 则自动生成
        """
        if trajectory_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            trajectory_path = f"trajectories/trajectory_{timestamp}.json"
        
        self.trajectory_path = Path(trajectory_path).resolve()
        
        # 确保目录存在
        try:
            self.trajectory_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"创建轨迹目录失败: {e}")
        
        # 轨迹数据结构
        self.trajectory_data: Dict[str, Any] = {
            "task": "",
            "start_time": "",
            "end_time": "",
            "provider": "",
            "model": "",
            "max_steps": 0,
            "llm_interactions": [],
            "agent_steps": [],
            "success": False,
            "final_result": None,
            "execution_time": 0.0,
            "total_tokens": None,
            "metadata": {}
        }
        
        self._start_time: Optional[datetime] = None
    
    def start_recording(
        self, 
        task: str, 
        provider: str, 
        model: str, 
        max_steps: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """开始记录新的轨迹
        
        Args:
            task: 正在执行的任务
            provider: LLM 提供商
            model: 模型名称
            max_steps: 最大步骤数
            metadata: 额外的元数据
        """
        self._start_time = datetime.now()
        self.trajectory_data.update({
            "task": task,
            "start_time": self._start_time.isoformat(),
            "provider": provider,
            "model": model,
            "max_steps": max_steps,
            "llm_interactions": [],
            "agent_steps": [],
            "metadata": metadata or {}
        })
        
        logger.info(f"开始记录轨迹: {self.trajectory_path}")
        self.save_trajectory()
    
    def record_llm_interaction(
        self,
        messages: List[BaseMessage],
        response: LLMResponse,
        provider: str,
        model: str,
        tools: Optional[List[Any]] = None
    ) -> None:
        """记录 LLM 交互
        
        Args:
            messages: 输入消息列表
            response: LLM 响应
            provider: LLM 提供商
            model: 模型名称
            tools: 可用的工具列表
        """
        interaction = {
            "timestamp": datetime.now().isoformat(),
            "provider": provider,
            "model": model,
            "input_messages": [self._serialize_message(msg) for msg in messages],
            "response": {
                "content": response.content,
                "model": response.model,
                "finish_reason": response.finish_reason,
                "usage": self._serialize_usage(response.usage) if response.usage else None,
                "tool_calls": [self._serialize_tool_call(tc) for tc in response.tool_calls]
                    if response.tool_calls else None,
            },
            "tools_available": [tool.name for tool in tools] if tools else None,
        }
        
        self.trajectory_data["llm_interactions"].append(interaction)
        self.save_trajectory()
    
    def record_agent_step(
        self,
        step: AgentStep,
        llm_messages: Optional[List[BaseMessage]] = None
    ) -> None:
        """记录智能体执行步骤
        
        Args:
            step: 智能体步骤
            llm_messages: 本步骤中发送给 LLM 的消息
        """
        step_data = {
            "step_number": step.step_number,
            "state": step.state.value,
            "timestamp": step.timestamp.isoformat(),
            "thought": step.thought,
            "tool_calls": [self._serialize_tool_call(tc) for tc in step.tool_calls]
                if step.tool_calls else None,
            "tool_results": [self._serialize_tool_result(tr) for tr in step.tool_results]
                if step.tool_results else None,
            "reflection": step.reflection,
            "error": step.error,
            "llm_usage": self._serialize_usage(step.llm_usage) if step.llm_usage else None,
            "llm_messages": [self._serialize_message(msg) for msg in llm_messages]
                if llm_messages else None,
            "extra": step.extra
        }
        
        self.trajectory_data["agent_steps"].append(step_data)
        
        # 更新累计 token 使用
        if step.llm_usage:
            self._update_total_tokens(step.llm_usage)
        
        self.save_trajectory()
    
    def end_recording(
        self,
        execution: AgentExecution,
        success: bool,
        final_result: Optional[Any] = None
    ) -> None:
        """结束记录
        
        Args:
            execution: 执行记录
            success: 是否成功
            final_result: 最终结果
        """
        end_time = datetime.now()
        execution_time = (end_time - self._start_time).total_seconds() if self._start_time else 0
        
        self.trajectory_data.update({
            "end_time": end_time.isoformat(),
            "success": success,
            "final_result": str(final_result) if final_result else None,
            "execution_time": execution_time,
            "total_steps": len(execution.steps),
            "agent_state": execution.agent_state.value,
            "error": execution.error
        })
        
        self.save_trajectory()
        logger.info(f"轨迹记录完成: {self.trajectory_path}")
    
    def save_trajectory(self) -> None:
        """保存轨迹到文件"""
        try:
            with open(self.trajectory_path, 'w', encoding='utf-8') as f:
                json.dump(self.trajectory_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存轨迹失败: {e}")
    
    def _serialize_message(self, message: BaseMessage) -> Dict[str, Any]:
        """序列化消息"""
        msg_dict = {
            "type": message.__class__.__name__,
            "content": message.content
        }
        
        # 添加额外字段
        if hasattr(message, 'role'):
            msg_dict["role"] = message.role
        if hasattr(message, 'name'):
            msg_dict["name"] = message.name
        if hasattr(message, 'tool_call_id') and isinstance(message, ToolMessage):
            msg_dict["tool_call_id"] = message.tool_call_id
            
        return msg_dict
    
    def _serialize_tool_call(self, tool_call: ToolCall) -> Dict[str, Any]:
        """序列化工具调用"""
        return {
            "name": tool_call.name,
            "call_id": tool_call.call_id,
            "arguments": tool_call.arguments,
            "id": tool_call.id
        }
    
    def _serialize_tool_result(self, tool_result: ToolResult) -> Dict[str, Any]:
        """序列化工具结果"""
        return {
            "name": tool_result.name,
            "call_id": tool_result.call_id,
            "success": tool_result.success,
            "result": str(tool_result.result) if tool_result.result else None,
            "error": tool_result.error,
            "execution_time": tool_result.execution_time
        }
    
    def _serialize_usage(self, usage: LLMUsage) -> Dict[str, Any]:
        """序列化 token 使用情况"""
        return {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": usage.total_tokens,
            "cache_read_tokens": usage.cache_read_tokens,
            "cache_creation_tokens": usage.cache_creation_tokens
        }
    
    def _update_total_tokens(self, usage: LLMUsage) -> None:
        """更新总 token 使用"""
        if self.trajectory_data["total_tokens"] is None:
            self.trajectory_data["total_tokens"] = {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cache_read_tokens": 0,
                "cache_creation_tokens": 0
            }
        
        totals = self.trajectory_data["total_tokens"]
        totals["input_tokens"] += usage.input_tokens
        totals["output_tokens"] += usage.output_tokens
        totals["total_tokens"] += usage.total_tokens
        if usage.cache_read_tokens:
            totals["cache_read_tokens"] += usage.cache_read_tokens
        if usage.cache_creation_tokens:
            totals["cache_creation_tokens"] += usage.cache_creation_tokens
    
    def load_trajectory(self, path: Optional[str] = None) -> Dict[str, Any]:
        """加载轨迹文件
        
        Args:
            path: 轨迹文件路径，默认使用当前路径
            
        Returns:
            轨迹数据
        """
        load_path = Path(path) if path else self.trajectory_path
        
        try:
            with open(load_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载轨迹失败: {e}")
            return {}
    
    @staticmethod
    def list_trajectories(directory: str = "trajectories") -> List[Path]:
        """列出所有轨迹文件
        
        Args:
            directory: 轨迹目录
            
        Returns:
            轨迹文件路径列表
        """
        trajectory_dir = Path(directory)
        if not trajectory_dir.exists():
            return []
        
        return sorted(
            trajectory_dir.glob("trajectory_*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )