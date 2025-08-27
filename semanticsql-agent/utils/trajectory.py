"""轨迹分析工具"""

from typing import Dict, Any, List
from datetime import datetime
import json
from pathlib import Path


class TrajectoryAnalyzer:
    """轨迹分析器"""
    
    def __init__(self, trajectory: Dict[str, Any]):
        """初始化轨迹分析器
        
        Args:
            trajectory: 轨迹数据
        """
        self.trajectory = trajectory
    
    @classmethod
    def from_file(cls, filepath: str) -> "TrajectoryAnalyzer":
        """从文件加载轨迹
        
        Args:
            filepath: 轨迹文件路径
            
        Returns:
            TrajectoryAnalyzer 实例
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            trajectory = json.load(f)
        return cls(trajectory)
    
    def get_summary(self) -> Dict[str, Any]:
        """获取轨迹摘要"""
        return {
            "start_time": self.trajectory.get("start_time"),
            "end_time": self.trajectory.get("end_time"),
            "duration": self.trajectory.get("total_duration", 0),
            "total_steps": len(self.trajectory.get("steps", [])),
            "tool_calls": len(self.trajectory.get("tool_calls", [])),
            "errors": len(self.trajectory.get("errors", [])),
            "tools_used": self.get_tools_used()
        }
    
    def get_tools_used(self) -> List[str]:
        """获取使用的工具列表"""
        tools = set()
        for call in self.trajectory.get("tool_calls", []):
            tools.add(call.get("tool", "unknown"))
        return sorted(list(tools))
    
    def get_tool_statistics(self) -> Dict[str, Dict[str, Any]]:
        """获取工具使用统计"""
        stats = {}
        
        for call in self.trajectory.get("tool_calls", []):
            tool = call.get("tool", "unknown")
            
            if tool not in stats:
                stats[tool] = {
                    "count": 0,
                    "total_duration": 0,
                    "success_count": 0,
                    "error_count": 0
                }
            
            stats[tool]["count"] += 1
            
            # 计算持续时间
            if "duration" in call:
                stats[tool]["total_duration"] += call["duration"]
            
            # 统计成功/失败
            if call.get("status") == "completed":
                stats[tool]["success_count"] += 1
            elif call.get("status") == "failed":
                stats[tool]["error_count"] += 1
        
        # 计算平均时间
        for tool_stats in stats.values():
            if tool_stats["count"] > 0:
                tool_stats["avg_duration"] = (
                    tool_stats["total_duration"] / tool_stats["count"]
                )
        
        return stats
    
    def get_errors(self) -> List[Dict[str, Any]]:
        """获取所有错误"""
        return self.trajectory.get("errors", [])
    
    def get_timeline(self) -> List[Dict[str, Any]]:
        """获取时间线视图"""
        timeline = []
        
        # 添加思考步骤
        for thought in self.trajectory.get("thoughts", []):
            timeline.append({
                "timestamp": thought.get("timestamp"),
                "type": "thinking",
                "step": thought.get("step"),
                "preview": thought.get("prompt_preview", "")[:100]
            })
        
        # 添加工具调用
        for call in self.trajectory.get("tool_calls", []):
            timeline.append({
                "timestamp": call.get("timestamp"),
                "type": "tool_call",
                "tool": call.get("tool"),
                "status": call.get("status"),
                "duration": call.get("duration", 0)
            })
        
        # 添加错误
        for error in self.trajectory.get("errors", []):
            timeline.append({
                "timestamp": error.get("timestamp"),
                "type": "error",
                "error": error.get("error"),
                "tool": error.get("tool")
            })
        
        # 按时间排序
        timeline.sort(key=lambda x: x.get("timestamp", ""))
        
        return timeline
    
    def print_summary(self):
        """打印轨迹摘要"""
        summary = self.get_summary()
        
        print("\n=== 轨迹摘要 ===")
        print(f"开始时间: {summary['start_time']}")
        print(f"结束时间: {summary['end_time']}")
        print(f"总耗时: {summary['duration']:.2f} 秒")
        print(f"总步骤数: {summary['total_steps']}")
        print(f"工具调用次数: {summary['tool_calls']}")
        print(f"错误数: {summary['errors']}")
        print(f"使用的工具: {', '.join(summary['tools_used'])}")
        
        # 打印工具统计
        print("\n=== 工具使用统计 ===")
        tool_stats = self.get_tool_statistics()
        for tool, stats in tool_stats.items():
            print(f"\n{tool}:")
            print(f"  调用次数: {stats['count']}")
            print(f"  成功: {stats['success_count']}")
            print(f"  失败: {stats['error_count']}")
            if stats.get('avg_duration'):
                print(f"  平均耗时: {stats['avg_duration']:.2f} 秒")
        
        # 打印错误
        errors = self.get_errors()
        if errors:
            print("\n=== 错误信息 ===")
            for i, error in enumerate(errors, 1):
                print(f"\n错误 {i}:")
                print(f"  时间: {error.get('timestamp')}")
                print(f"  工具: {error.get('tool')}")
                print(f"  类型: {error.get('type')}")
                print(f"  信息: {error.get('error')}")
    
    def export_timeline(self, filepath: str):
        """导出时间线到文件
        
        Args:
            filepath: 导出文件路径
        """
        timeline = self.get_timeline()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            for event in timeline:
                timestamp = event.get("timestamp", "")
                event_type = event.get("type", "")
                
                if event_type == "thinking":
                    f.write(f"[{timestamp}] 思考步骤 {event.get('step')}\n")
                elif event_type == "tool_call":
                    f.write(
                        f"[{timestamp}] 调用工具: {event.get('tool')} "
                        f"(状态: {event.get('status')}, 耗时: {event.get('duration', 0):.2f}s)\n"
                    )
                elif event_type == "error":
                    f.write(
                        f"[{timestamp}] 错误: {event.get('tool')} - "
                        f"{event.get('error')}\n"
                    )
        
        print(f"时间线已导出到: {filepath}")