"""
Trajectory recording callbacks for agent execution
Based on the design specification - handles execution tracking
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from models.schemas import AgentExecution, AgentStep, AgentStepType
from utils.trajectory import TrajectoryRecorder


class ExecutionCallback:
    """Base class for execution callbacks"""
    
    def on_execution_start(self, execution: AgentExecution):
        """Called when execution starts"""
        pass
    
    def on_execution_complete(self, execution: AgentExecution):
        """Called when execution completes"""
        pass
    
    def on_step_start(self, execution: AgentExecution, step: AgentStep):
        """Called when a step starts"""
        pass
    
    def on_step_complete(self, execution: AgentExecution, step: AgentStep):
        """Called when a step completes"""
        pass
    
    def on_tool_call(self, execution: AgentExecution, tool_name: str, 
                    tool_input: Dict[str, Any], tool_output: Dict[str, Any]):
        """Called when a tool is called"""
        pass
    
    def on_error(self, execution: AgentExecution, error: Exception):
        """Called when an error occurs"""
        pass


class TrajectoryCallback(ExecutionCallback):
    """Callback for recording execution trajectories"""
    
    def __init__(self, trajectory_recorder: TrajectoryRecorder):
        self.recorder = trajectory_recorder
        self.logger = logging.getLogger(__name__)
    
    def on_execution_start(self, execution: AgentExecution):
        """Record execution start"""
        self.logger.info(f"Starting task: {execution.task}")
    
    def on_execution_complete(self, execution: AgentExecution):
        """Save trajectory when execution completes"""
        try:
            filepath = self.recorder.save_execution(execution)
            self.logger.info(f"Execution completed. Trajectory saved to: {filepath}")
        except Exception as e:
            self.logger.error(f"Failed to save trajectory: {e}")
    
    def on_step_complete(self, execution: AgentExecution, step: AgentStep):
        """Log step completion"""
        self.logger.debug(f"Step completed: {step.step_type.value} - {step.content[:100]}...")
    
    def on_tool_call(self, execution: AgentExecution, tool_name: str,
                    tool_input: Dict[str, Any], tool_output: Dict[str, Any]):
        """Record tool call"""
        success = tool_output.get("success", False)
        status = "✓" if success else "✗"
        self.logger.info(f"{status} Tool: {tool_name}")
        
        if not success and tool_output.get("error"):
            self.logger.warning(f"Tool error: {tool_output['error']}")
    
    def on_error(self, execution: AgentExecution, error: Exception):
        """Record execution error"""
        self.logger.error(f"Execution error: {error}")


class LoggingCallback(ExecutionCallback):
    """Callback for detailed logging"""
    
    def __init__(self, log_level: str = "INFO"):
        self.logger = logging.getLogger(__name__)
        self.log_level = log_level
    
    def on_execution_start(self, execution: AgentExecution):
        """Log execution start with details"""
        self.logger.info(f"🚀 Starting new task: {execution.task}")
        self.logger.info(f"   Task ID: {execution.task_id}")
        self.logger.info(f"   Started at: {execution.started_at}")
    
    def on_execution_complete(self, execution: AgentExecution):
        """Log execution completion with summary"""
        duration = execution.get_duration()
        status_emoji = "✅" if execution.status == "completed" else "❌"
        
        self.logger.info(f"{status_emoji} Task {execution.status}")
        self.logger.info(f"   Duration: {duration:.2f}s" if duration else "   Duration: unknown")
        self.logger.info(f"   Steps: {len(execution.steps)}")
        
        if execution.error:
            self.logger.error(f"   Error: {execution.error}")
    
    def on_step_start(self, execution: AgentExecution, step: AgentStep):
        """Log step start"""
        if self.log_level == "DEBUG":
            self.logger.debug(f"▶️  {step.step_type.value}: {step.content}")
    
    def on_step_complete(self, execution: AgentExecution, step: AgentStep):
        """Log step completion"""
        if step.duration_ms:
            duration_str = f" ({step.duration_ms}ms)"
        else:
            duration_str = ""
        
        if step.error:
            self.logger.warning(f"⚠️  {step.step_type.value} failed: {step.error}")
        elif self.log_level == "DEBUG":
            self.logger.debug(f"✓ {step.step_type.value} completed{duration_str}")
    
    def on_tool_call(self, execution: AgentExecution, tool_name: str,
                    tool_input: Dict[str, Any], tool_output: Dict[str, Any]):
        """Log tool call details"""
        success = tool_output.get("success", False)
        status_emoji = "🔧" if success else "🔴"
        
        self.logger.info(f"{status_emoji} {tool_name}")
        
        if self.log_level == "DEBUG":
            self.logger.debug(f"   Input: {str(tool_input)[:200]}...")
            if success:
                data_size = len(str(tool_output.get("data", "")))
                self.logger.debug(f"   Output size: {data_size} chars")
            else:
                self.logger.debug(f"   Error: {tool_output.get('error', 'Unknown error')}")


class MetricsCallback(ExecutionCallback):
    """Callback for collecting execution metrics"""
    
    def __init__(self):
        self.metrics = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "total_steps": 0,
            "tool_usage": {},
            "average_duration": 0.0,
            "error_types": {}
        }
        self.logger = logging.getLogger(__name__)
    
    def on_execution_start(self, execution: AgentExecution):
        """Start tracking execution"""
        self.metrics["total_executions"] += 1
    
    def on_execution_complete(self, execution: AgentExecution):
        """Update metrics on completion"""
        if execution.status == "completed":
            self.metrics["successful_executions"] += 1
        else:
            self.metrics["failed_executions"] += 1
        
        # Update step count
        self.metrics["total_steps"] += len(execution.steps)
        
        # Update average duration
        duration = execution.get_duration()
        if duration:
            current_avg = self.metrics["average_duration"]
            total = self.metrics["total_executions"]
            self.metrics["average_duration"] = (current_avg * (total - 1) + duration) / total
    
    def on_tool_call(self, execution: AgentExecution, tool_name: str,
                    tool_input: Dict[str, Any], tool_output: Dict[str, Any]):
        """Track tool usage"""
        if tool_name not in self.metrics["tool_usage"]:
            self.metrics["tool_usage"][tool_name] = 0
        self.metrics["tool_usage"][tool_name] += 1
    
    def on_error(self, execution: AgentExecution, error: Exception):
        """Track error types"""
        error_type = type(error).__name__
        if error_type not in self.metrics["error_types"]:
            self.metrics["error_types"][error_type] = 0
        self.metrics["error_types"][error_type] += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        return self.metrics.copy()
    
    def reset_metrics(self):
        """Reset all metrics"""
        self.metrics = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "total_steps": 0,
            "tool_usage": {},
            "average_duration": 0.0,
            "error_types": {}
        }