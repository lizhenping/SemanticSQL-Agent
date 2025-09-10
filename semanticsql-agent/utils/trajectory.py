"""
Trajectory recording and management
Based on the design specification - simplified trajectory handling
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from agent.models import AgentExecution, AgentStep


class TrajectoryRecorder:
    """Trajectory recording system"""
    
    def __init__(self, output_dir: str = "trajectories", max_trajectories: int = 100):
        self.output_dir = Path(output_dir)
        self.max_trajectories = max_trajectories
        self.logger = logging.getLogger(__name__)
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def save_execution(self, execution: AgentExecution) -> str:
        """Save execution trajectory to file"""
        try:
            # Generate filename with timestamp
            timestamp = execution.started_at.strftime("%Y%m%d_%H%M%S")
            filename = f"execution_{timestamp}_{execution.task_id[:8]}.json"
            filepath = self.output_dir / filename
            
            # Convert to serializable format with enhanced serialization
            trajectory_data = {
                "task_id": execution.task_id,
                "task": execution.task,
                "started_at": execution.started_at.isoformat(),
                "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                "status": execution.status,
                "final_result": self._serialize_tool_output(execution.final_result),
                "error": execution.error,
                "metadata": self._serialize_tool_output(execution.metadata),
                "steps": [
                    {
                        "step_type": step.step_type.value,
                        "content": step.content,
                        "timestamp": step.timestamp.isoformat(),
                        "tool_name": step.tool_name,
                        "tool_input": self._serialize_tool_output(step.tool_input),
                        "tool_output": self._serialize_tool_output(step.tool_output),
                        "error": step.error,
                        "duration_ms": step.duration_ms
                    }
                    for step in execution.steps
                ],
                "summary": self._serialize_tool_output(execution.get_summary()) if hasattr(execution, 'get_summary') else {}
            }
            
            # Save to file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(trajectory_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Trajectory saved: {filepath}")
            
            # Clean up old trajectories if needed
            self._cleanup_old_trajectories()
            
            return str(filepath)
            
        except Exception as e:
            self.logger.error(f"Failed to save trajectory: {e}")
            return ""
    
    def load_execution(self, filepath: str) -> Optional[AgentExecution]:
        """Load execution trajectory from file"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Convert back to AgentExecution
            execution = AgentExecution(
                task_id=data["task_id"],
                task=data["task"],
                started_at=datetime.fromisoformat(data["started_at"]),
                completed_at=datetime.fromisoformat(data["completed_at"]) if data["completed_at"] else None,
                status=data["status"],
                final_result=data["final_result"],
                error=data["error"],
                metadata=data["metadata"]
            )
            
            # Convert steps
            for step_data in data["steps"]:
                step = AgentStep(
                    step_type=step_data["step_type"],
                    content=step_data["content"],
                    timestamp=datetime.fromisoformat(step_data["timestamp"]),
                    tool_name=step_data["tool_name"],
                    tool_input=step_data["tool_input"],
                    tool_output=step_data["tool_output"],
                    error=step_data["error"],
                    duration_ms=step_data["duration_ms"]
                )
                execution.add_step(step)
            
            return execution
            
        except Exception as e:
            self.logger.error(f"Failed to load trajectory from {filepath}: {e}")
            return None
    
    def get_trajectories(self, limit: Optional[int] = None) -> List[str]:
        """Get list of trajectory files"""
        try:
            pattern = "execution_*.json"
            trajectories = list(self.output_dir.glob(pattern))
            
            # Sort by modification time (newest first)
            trajectories.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # Apply limit if specified
            if limit:
                trajectories = trajectories[:limit]
            
            return [str(f) for f in trajectories]
            
        except Exception as e:
            self.logger.error(f"Failed to get trajectories: {e}")
            return []
    
    def get_trajectory_summary(self, filepath: str) -> Optional[Dict[str, Any]]:
        """Get trajectory summary without loading full data"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return data.get("summary", {})
            
        except Exception as e:
            self.logger.error(f"Failed to get trajectory summary from {filepath}: {e}")
            return None
    
    def _cleanup_old_trajectories(self):
        """Clean up old trajectory files if exceeding max count"""
        try:
            trajectories = self.get_trajectories()
            
            if len(trajectories) > self.max_trajectories:
                # Remove oldest trajectories
                to_remove = trajectories[self.max_trajectories:]
                for filepath in to_remove:
                    Path(filepath).unlink()
                    self.logger.debug(f"Removed old trajectory: {filepath}")
                
                self.logger.info(f"Cleaned up {len(to_remove)} old trajectories")
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup old trajectories: {e}")
    
    def export_trajectories(self, output_file: str, format: str = "json") -> bool:
        """Export all trajectories to a single file"""
        try:
            trajectories = self.get_trajectories()
            exported_data = []
            
            for filepath in trajectories:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    exported_data.append(data)
            
            # Save exported data
            if format.lower() == "json":
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(exported_data, f, indent=2, ensure_ascii=False)
            else:
                raise ValueError(f"Unsupported export format: {format}")
            
            self.logger.info(f"Exported {len(exported_data)} trajectories to {output_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to export trajectories: {e}")
            return False
    
    def _serialize_tool_output(self, output: Any) -> Any:
        """序列化工具输出为JSON兼容格式"""
        if output is None:
            return None
        
        try:
            # 特殊处理Pydantic FieldInfo对象
            from pydantic.fields import FieldInfo
            if isinstance(output, FieldInfo):
                return {
                    "type": "FieldInfo",
                    "description": getattr(output, 'description', None),
                    "default": str(getattr(output, 'default', None))
                }
            
            # 如果是Pydantic模型，使用model_dump
            if hasattr(output, 'model_dump'):
                return output.model_dump()
            # 如果是字典，递归处理
            elif isinstance(output, dict):
                return {k: self._serialize_tool_output(v) for k, v in output.items()}
            # 如果是列表，递归处理
            elif isinstance(output, list):
                return [self._serialize_tool_output(item) for item in output]
            # 如果是复杂对象类型，转换为字符串
            elif hasattr(output, '__dict__') and not isinstance(output, (str, int, float, bool)):
                return str(output)
            # 测试是否可以JSON序列化
            json.dumps(output)
            return output
        except (TypeError, ValueError):
            # 无法序列化时，转换为字符串表示
            return str(output)