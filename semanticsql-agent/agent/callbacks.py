"""轨迹记录回调"""

from langchain.callbacks.base import BaseCallbackHandler
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


class TrajectoryCallback(BaseCallbackHandler):
    """轨迹记录回调，记录智能体执行过程"""
    
    def __init__(self):
        """初始化轨迹记录器"""
        self.reset()
    
    def reset(self):
        """重置轨迹"""
        self.trajectory = {
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "steps": [],
            "tool_calls": [],
            "thoughts": [],
            "errors": [],
            "final_output": None
        }
        self.current_step = None
        self.step_count = 0
    
    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        **kwargs: Any
    ) -> None:
        """LLM 开始思考时调用"""
        self.step_count += 1
        
        thought = {
            "step": self.step_count,
            "timestamp": datetime.now().isoformat(),
            "type": "thinking",
            "prompt_preview": prompts[0][:500] if prompts else ""
        }
        
        self.trajectory["thoughts"].append(thought)
        logger.debug(f"LLM 思考步骤 {self.step_count} 开始")
    
    def on_llm_end(self, response, **kwargs: Any) -> None:
        """LLM 结束思考时调用"""
        if self.trajectory["thoughts"]:
            last_thought = self.trajectory["thoughts"][-1]
            
            # 添加响应预览
            if hasattr(response, 'generations') and response.generations:
                content = response.generations[0][0].text if response.generations[0] else ""
                last_thought["response_preview"] = content[:500]
            else:
                last_thought["response_preview"] = str(response)[:500]
            
            last_thought["end_time"] = datetime.now().isoformat()
    
    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        **kwargs: Any
    ) -> None:
        """工具开始执行时调用"""
        tool_name = serialized.get("name", "unknown")
        
        tool_call = {
            "timestamp": datetime.now().isoformat(),
            "tool": tool_name,
            "input": input_str[:1000],  # 限制输入长度
            "status": "started"
        }
        
        self.trajectory["tool_calls"].append(tool_call)
        self.current_step = tool_call
        
        logger.info(f"执行工具: {tool_name}")
        logger.debug(f"工具输入: {input_str[:200]}...")
    
    def on_tool_end(
        self,
        output: str,
        **kwargs: Any
    ) -> None:
        """工具执行结束时调用"""
        if self.current_step:
            self.current_step.update({
                "output": output[:2000],  # 限制输出长度
                "status": "completed",
                "end_time": datetime.now().isoformat(),
                "duration": self._calculate_duration(
                    self.current_step["timestamp"],
                    datetime.now().isoformat()
                )
            })
            
            # 添加到步骤记录
            step = {
                "type": "tool_execution",
                "tool": self.current_step["tool"],
                "timestamp": self.current_step["timestamp"],
                "success": True
            }
            self.trajectory["steps"].append(step)
            
            logger.info(f"工具 {self.current_step['tool']} 执行完成")
            self.current_step = None
    
    def on_tool_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        **kwargs: Any
    ) -> None:
        """工具执行错误时调用"""
        error_info = {
            "timestamp": datetime.now().isoformat(),
            "tool": self.current_step["tool"] if self.current_step else "unknown",
            "error": str(error),
            "type": type(error).__name__
        }
        
        self.trajectory["errors"].append(error_info)
        
        if self.current_step:
            self.current_step["status"] = "failed"
            self.current_step["error"] = str(error)
            
            # 添加失败步骤
            step = {
                "type": "tool_execution",
                "tool": self.current_step["tool"],
                "timestamp": self.current_step["timestamp"],
                "success": False,
                "error": str(error)
            }
            self.trajectory["steps"].append(step)
        
        logger.error(f"工具执行错误: {error}")
    
    def on_agent_action(self, action, **kwargs: Any) -> None:
        """智能体执行动作时调用"""
        action_info = {
            "type": "agent_action",
            "timestamp": datetime.now().isoformat(),
            "action": action.tool if hasattr(action, 'tool') else str(action),
            "input": str(action.tool_input)[:500] if hasattr(action, 'tool_input') else "",
            "log": action.log[:500] if hasattr(action, 'log') else ""
        }
        
        self.trajectory["steps"].append(action_info)
        logger.debug(f"智能体动作: {action_info['action']}")
    
    def on_agent_finish(self, finish, **kwargs: Any) -> None:
        """智能体完成时调用"""
        self.trajectory["end_time"] = datetime.now().isoformat()
        self.trajectory["final_output"] = str(finish)[:2000]
        
        # 计算总耗时
        total_duration = self._calculate_duration(
            self.trajectory["start_time"],
            self.trajectory["end_time"]
        )
        self.trajectory["total_duration"] = total_duration
        
        logger.info(f"智能体执行完成，总耗时: {total_duration:.2f} 秒")
    
    def get_trajectory(self) -> Dict[str, Any]:
        """获取完整轨迹"""
        return self.trajectory
    
    def get_summary(self) -> Dict[str, Any]:
        """获取轨迹摘要"""
        return {
            "total_steps": len(self.trajectory["steps"]),
            "tool_calls": len(self.trajectory["tool_calls"]),
            "thoughts": len(self.trajectory["thoughts"]),
            "errors": len(self.trajectory["errors"]),
            "duration": self.trajectory.get("total_duration", 0),
            "tools_used": list(set(
                call["tool"] for call in self.trajectory["tool_calls"]
            ))
        }
    
    def save_trajectory(self, filepath: str):
        """保存轨迹到文件
        
        Args:
            filepath: 保存路径
        """
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.trajectory, f, ensure_ascii=False, indent=2)
            logger.info(f"轨迹已保存到: {filepath}")
        except Exception as e:
            logger.error(f"保存轨迹失败: {e}")
    
    def _calculate_duration(self, start: str, end: str) -> float:
        """计算持续时间（秒）
        
        Args:
            start: 开始时间 ISO 格式
            end: 结束时间 ISO 格式
            
        Returns:
            持续时间（秒）
        """
        try:
            start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
            return (end_dt - start_dt).total_seconds()
        except Exception as e:
            logger.warning(f"计算时间差失败: {e}")
            return 0.0