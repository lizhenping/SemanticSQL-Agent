"""
执行轨迹记录器 - 记录智能体的完整执行过程
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
import uuid

from core.models import AgentStep, AgentStepType, AgentExecution
from core.constants import DEFAULT_LOG_DIR


class ExecutionTracker:
    """执行轨迹记录器"""
    
    def __init__(self, task: str = "", save_to_file: bool = False, log_dir: str = DEFAULT_LOG_DIR):
        """
        初始化执行追踪器
        
        Args:
            task: 任务描述
            save_to_file: 是否保存到文件
            log_dir: 日志目录
        """
        self.execution = AgentExecution(task=task)
        self.save_to_file = save_to_file
        self.log_dir = Path(log_dir)
        self.logger = logging.getLogger("ExecutionTracker")
        
        if save_to_file:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            self.log_file = self.log_dir / f"execution_{self.execution.task_id}.json"
    
    def start(self, task: str = None):
        """开始执行追踪"""
        if task:
            self.execution.task = task
        self.execution.started_at = datetime.now()
        self.execution.status = "running"
        self.logger.info(f"Started tracking execution: {self.execution.task_id}")
    
    def record_thought(self, content: str, **kwargs):
        """记录思考步骤"""
        step = AgentStep(
            step_type=AgentStepType.THOUGHT,
            content=content,
            **kwargs
        )
        self.execution.add_step(step)
        self.logger.debug(f"Thought: {content[:100]}...")
        self._save_if_enabled()
    
    def record_action(self, tool_name: str, tool_input: Dict[str, Any], content: str = None, **kwargs):
        """记录行动步骤"""
        if not content:
            content = f"Calling tool: {tool_name}"
        
        step = AgentStep(
            step_type=AgentStepType.ACTION,
            content=content,
            tool_name=tool_name,
            tool_input=tool_input,
            **kwargs
        )
        self.execution.add_step(step)
        self.logger.debug(f"Action: {tool_name} with input: {tool_input}")
        self._save_if_enabled()
    
    def record_observation(self, tool_output: Any, content: str = None, error: str = None, **kwargs):
        """记录观察结果"""
        if not content:
            if error:
                content = f"Tool execution failed: {error}"
            else:
                content = f"Tool returned: {str(tool_output)[:200]}..."
        
        step = AgentStep(
            step_type=AgentStepType.OBSERVATION,
            content=content,
            tool_output=tool_output,
            error=error,
            **kwargs
        )
        self.execution.add_step(step)
        
        if error:
            self.logger.warning(f"Observation (error): {error}")
        else:
            self.logger.debug(f"Observation: {content[:100]}...")
        
        self._save_if_enabled()
    
    def record_reflection(self, content: str, **kwargs):
        """记录反思步骤"""
        step = AgentStep(
            step_type=AgentStepType.REFLECTION,
            content=content,
            **kwargs
        )
        self.execution.add_step(step)
        self.logger.debug(f"Reflection: {content[:100]}...")
        self._save_if_enabled()
    
    def record_step(self, step_type: AgentStepType, content: str, **kwargs):
        """通用的步骤记录方法"""
        step = AgentStep(
            step_type=step_type,
            content=content,
            **kwargs
        )
        self.execution.add_step(step)
        self.logger.debug(f"{step_type.value}: {content[:100]}...")
        self._save_if_enabled()
    
    def complete(self, result: Any = None, error: str = None):
        """标记执行完成"""
        self.execution.complete(result=result, error=error)
        
        if error:
            self.logger.error(f"Execution failed: {error}")
        else:
            self.logger.info(f"Execution completed successfully")
        
        self._save_if_enabled()
        
        # 打印执行摘要
        summary = self.get_execution_summary()
        self.logger.info(f"Execution summary: {json.dumps(summary, indent=2)}")
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """获取执行摘要"""
        summary = self.execution.get_summary()
        
        # 添加更多统计信息
        step_counts = self._count_steps_by_type()
        tool_usage = self._analyze_tool_usage()
        error_rate = self._calculate_error_rate()
        
        summary.update({
            "step_counts": step_counts,
            "tool_usage": tool_usage,
            "error_rate": error_rate,
            "execution_id": self.execution.task_id
        })
        
        return summary
    
    def get_execution_trace(self) -> Dict[str, Any]:
        """获取完整的执行轨迹"""
        return {
            "task_id": self.execution.task_id,
            "task": self.execution.task,
            "started_at": self.execution.started_at.isoformat() if self.execution.started_at else None,
            "completed_at": self.execution.completed_at.isoformat() if self.execution.completed_at else None,
            "status": self.execution.status,
            "steps": [step.to_dict() for step in self.execution.steps],
            "final_result": self.execution.final_result,
            "error": self.execution.error,
            "metadata": self.execution.metadata
        }
    
    def get_last_steps(self, n: int = 5) -> List[AgentStep]:
        """获取最近的n个步骤"""
        return self.execution.steps[-n:] if self.execution.steps else []
    
    def get_tools_used(self) -> List[str]:
        """获取使用过的工具列表"""
        return list(set(
            step.tool_name 
            for step in self.execution.steps 
            if step.tool_name
        ))
    
    def _count_steps_by_type(self) -> Dict[str, int]:
        """统计各类型步骤的数量"""
        counts = {}
        for step in self.execution.steps:
            step_type = step.step_type.value
            counts[step_type] = counts.get(step_type, 0) + 1
        return counts
    
    def _analyze_tool_usage(self) -> Dict[str, Dict[str, Any]]:
        """分析工具使用情况"""
        tool_stats = {}
        
        for step in self.execution.steps:
            if step.tool_name:
                if step.tool_name not in tool_stats:
                    tool_stats[step.tool_name] = {
                        "call_count": 0,
                        "success_count": 0,
                        "error_count": 0,
                        "total_duration_ms": 0
                    }
                
                tool_stats[step.tool_name]["call_count"] += 1
                
                if step.error:
                    tool_stats[step.tool_name]["error_count"] += 1
                else:
                    tool_stats[step.tool_name]["success_count"] += 1
                
                if step.duration_ms:
                    tool_stats[step.tool_name]["total_duration_ms"] += step.duration_ms
        
        return tool_stats
    
    def _calculate_error_rate(self) -> float:
        """计算错误率"""
        total_steps = len(self.execution.steps)
        if total_steps == 0:
            return 0.0
        
        error_steps = sum(1 for step in self.execution.steps if step.error)
        return error_steps / total_steps
    
    def _save_if_enabled(self):
        """如果启用了文件保存，则保存执行轨迹"""
        if self.save_to_file and hasattr(self, 'log_file'):
            try:
                with open(self.log_file, 'w', encoding='utf-8') as f:
                    json.dump(self.get_execution_trace(), f, indent=2, ensure_ascii=False)
            except Exception as e:
                self.logger.error(f"Failed to save execution trace: {e}")
    
    def export_to_markdown(self) -> str:
        """导出为Markdown格式"""
        lines = [
            f"# Execution Report",
            f"\n## Task Information",
            f"- **Task ID**: {self.execution.task_id}",
            f"- **Task**: {self.execution.task}",
            f"- **Status**: {self.execution.status}",
            f"- **Started**: {self.execution.started_at.isoformat() if self.execution.started_at else 'N/A'}",
            f"- **Completed**: {self.execution.completed_at.isoformat() if self.execution.completed_at else 'N/A'}",
            f"- **Duration**: {self.execution.get_duration():.2f}s" if self.execution.get_duration() else "- **Duration**: N/A",
            f"\n## Execution Steps\n"
        ]
        
        for i, step in enumerate(self.execution.steps, 1):
            emoji = {
                AgentStepType.THOUGHT: "💭",
                AgentStepType.ACTION: "⚡",
                AgentStepType.OBSERVATION: "👁️",
                AgentStepType.REFLECTION: "🔍"
            }.get(step.step_type, "📝")
            
            lines.append(f"### {i}. {emoji} {step.step_type.value.title()}")
            lines.append(f"**Time**: {step.timestamp.isoformat()}")
            
            if step.tool_name:
                lines.append(f"**Tool**: {step.tool_name}")
            
            lines.append(f"**Content**: {step.content}")
            
            if step.error:
                lines.append(f"**Error**: ❌ {step.error}")
            
            lines.append("")
        
        if self.execution.final_result:
            lines.append(f"\n## Final Result")
            lines.append(f"```json")
            lines.append(json.dumps(self.execution.final_result, indent=2, ensure_ascii=False))
            lines.append(f"```")
        
        return "\n".join(lines)
    
    def __enter__(self):
        """上下文管理器入口"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        if exc_val:
            self.complete(error=str(exc_val))
        else:
            self.complete()
        return False