"""轨迹记录器

参考 TRAEAgent 的 TrajectoryRecorder，记录智能体的执行轨迹。
"""

import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from .agent_state import AgentExecution, AgentStep

logger = logging.getLogger(__name__)


class TrajectoryRecorder:
    """轨迹记录器
    
    记录智能体的执行轨迹，用于调试、分析和改进。
    """
    
    def __init__(self, output_dir: Optional[str] = None):
        """初始化轨迹记录器
        
        Args:
            output_dir: 输出目录，如果为 None 则使用默认目录
        """
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path("trajectories")
        
        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 当前记录
        self.current_execution: Optional[AgentExecution] = None
        self.trajectory_file: Optional[Path] = None
    
    def start_recording(self, execution: AgentExecution) -> None:
        """开始记录新的执行轨迹
        
        Args:
            execution: 智能体执行对象
        """
        self.current_execution = execution
        
        # 生成轨迹文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        task_slug = self._slugify(execution.task)[:50]
        filename = f"trajectory_{timestamp}_{task_slug}.json"
        self.trajectory_file = self.output_dir / filename
        
        logger.info(f"开始记录轨迹: {self.trajectory_file}")
        
        # 写入初始信息
        self._save_trajectory()
    
    def record_step(self, step: AgentStep) -> None:
        """记录执行步骤
        
        Args:
            step: 执行步骤
        """
        if not self.current_execution:
            logger.warning("没有活动的执行记录")
            return
        
        # 步骤已经添加到 execution.steps 中
        # 这里只需要保存轨迹
        self._save_trajectory()
        
        logger.debug(f"记录步骤 {step.step_number}: {step.state.value}")
    
    def end_recording(self) -> None:
        """结束记录"""
        if not self.current_execution:
            return
        
        # 最终保存
        self._save_trajectory()
        
        logger.info(f"轨迹记录完成: {self.trajectory_file}")
        
        # 清理
        self.current_execution = None
        self.trajectory_file = None
    
    def _save_trajectory(self) -> None:
        """保存轨迹到文件"""
        if not self.current_execution or not self.trajectory_file:
            return
        
        try:
            trajectory_data = {
                "task": self.current_execution.task,
                "state": self.current_execution.state.value,
                "created_at": self.current_execution.created_at.isoformat(),
                "completed_at": self.current_execution.completed_at.isoformat() if self.current_execution.completed_at else None,
                "execution_time": self.current_execution.execution_time,
                "total_steps": self.current_execution.total_steps,
                "success": self.current_execution.success,
                "final_sql": self.current_execution.final_sql,
                "error": self.current_execution.error,
                "steps": [self._format_step(step) for step in self.current_execution.steps],
                "context": self._format_context(self.current_execution.context)
            }
            
            with open(self.trajectory_file, 'w', encoding='utf-8') as f:
                json.dump(trajectory_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"保存轨迹失败: {e}")
    
    def _format_step(self, step: AgentStep) -> Dict[str, Any]:
        """格式化步骤信息"""
        return {
            "step_number": step.step_number,
            "state": step.state.value,
            "timestamp": step.timestamp.isoformat(),
            "thought": step.thought,
            "action": self._format_action(step.action) if step.action else None,
            "observation": self._format_observation(step.observation) if step.observation else None,
            "error": step.error
        }
    
    def _format_action(self, action: Any) -> Dict[str, Any]:
        """格式化动作信息"""
        if hasattr(action, 'dict'):
            return action.dict()
        elif hasattr(action, '__dict__'):
            return {
                "tool": getattr(action, 'tool', 'unknown'),
                "args": getattr(action, 'args', {})
            }
        else:
            return {"raw": str(action)}
    
    def _format_observation(self, observation: Any) -> Dict[str, Any]:
        """格式化观察结果"""
        if hasattr(observation, 'dict'):
            return observation.dict()
        elif hasattr(observation, '__dict__'):
            return {
                "success": getattr(observation, 'success', False),
                "result": str(getattr(observation, 'result', '')),
                "error": getattr(observation, 'error', None)
            }
        else:
            return {"raw": str(observation)}
    
    def _format_context(self, context: Any) -> Dict[str, Any]:
        """格式化上下文信息"""
        if hasattr(context, '__dict__'):
            result = {}
            for key, value in context.__dict__.items():
                if value is not None:
                    # 只记录关键信息，避免过大
                    if key in ['generated_sql', 'validation_result']:
                        result[key] = str(value)
                    elif key == 'schema_info' and value:
                        result[key] = {
                            "tables_count": getattr(value, 'tables_count', 0),
                            "database_name": getattr(value, 'database_name', 'unknown')
                        }
                    elif key == 'domain_analysis' and value:
                        result[key] = {
                            "domain": getattr(value, 'domain', 'unknown'),
                            "success": getattr(value, 'success', False)
                        }
            return result
        return {}
    
    def _slugify(self, text: str) -> str:
        """将文本转换为文件名友好的格式"""
        import re
        # 移除特殊字符
        text = re.sub(r'[^\w\s-]', '', text)
        # 替换空格为下划线
        text = re.sub(r'[-\s]+', '_', text)
        return text.strip('_')
    
    def get_recent_trajectories(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的轨迹记录
        
        Args:
            limit: 返回的最大数量
            
        Returns:
            轨迹记录列表
        """
        trajectories = []
        
        # 获取所有轨迹文件
        trajectory_files = sorted(
            self.output_dir.glob("trajectory_*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )[:limit]
        
        for file in trajectory_files:
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    data['filename'] = file.name
                    trajectories.append(data)
            except Exception as e:
                logger.error(f"读取轨迹文件 {file} 失败: {e}")
        
        return trajectories