"""
简化轨迹记录器
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TrajectoryRecorder:
    """简化轨迹记录器"""
    
    def __init__(self, trajectory_path: Optional[str] = None):
        self.trajectory_path = trajectory_path
        self.trajectory_data = {
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "version": "1.0"
            },
            "steps": []
        }
    
    def record_step(self, step_data: Dict[str, Any]) -> None:
        """记录步骤"""
        step_data["timestamp"] = datetime.now().isoformat()
        self.trajectory_data["steps"].append(step_data)
        
        if self.trajectory_path:
            try:
                Path(self.trajectory_path).parent.mkdir(parents=True, exist_ok=True)
                with open(self.trajectory_path, 'w', encoding='utf-8') as f:
                    json.dump(self.trajectory_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error(f"保存轨迹失败: {e}")
    
    def record_query(self, query: str, sql: str, result: Dict[str, Any]) -> None:
        """记录查询"""
        self.record_step({
            "type": "query",
            "query": query,
            "sql": sql,
            "result": result
        })
    
    def get_trajectory(self) -> Dict[str, Any]:
        """获取轨迹数据"""
        return self.trajectory_data