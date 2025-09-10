"""
回调处理和轨迹记录 - SemanticSQL Agent执行监控
基于架构设计的标准回调系统，支持ReAct执行轨迹记录
"""

import logging
import json
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from pathlib import Path
from uuid import UUID

from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import AgentAction, AgentFinish, LLMResult
from langchain_core.outputs import LLMResult

from models.training import TrainingExample
from models.exceptions import raise_tool_error


class SemanticSQLCallbackHandler(BaseCallbackHandler):
    """SemanticSQL Agent专用回调处理器
    
    职责：
    - 记录ReAct执行轨迹
    - 收集训练数据生成所需信息
    - 监控工具执行和LLM调用
    - 支持执行过程的实时监控和调试
    
    设计原则：
    - 轻量级：最小化性能开销
    - 结构化：标准化的轨迹数据格式
    - 可扩展：支持不同类型的轨迹记录需求
    """
    
    def __init__(self, 
                 enable_trajectory: bool = True,
                 enable_llm_tracking: bool = True,
                 enable_tool_tracking: bool = True,
                 output_directory: str = "./trajectories"):
        """
        初始化回调处理器
        
        Args:
            enable_trajectory: 是否启用轨迹记录
            enable_llm_tracking: 是否跟踪LLM调用
            enable_tool_tracking: 是否跟踪工具调用
            output_directory: 轨迹输出目录
        """
        super().__init__()
        
        self.enable_trajectory = enable_trajectory
        self.enable_llm_tracking = enable_llm_tracking
        self.enable_tool_tracking = enable_tool_tracking
        self.output_directory = Path(output_directory)
        
        # 确保输出目录存在
        self.output_directory.mkdir(parents=True, exist_ok=True)
        
        # 轨迹数据存储
        self.trajectories: List[Dict[str, Any]] = []
        self.current_session_id: str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.step_counter: int = 0
        
        # LLM调用统计
        self.llm_calls: List[Dict[str, Any]] = []
        self.tool_calls: List[Dict[str, Any]] = []
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"🎯 回调处理器初始化 - 会话ID: {self.current_session_id}")
    
    # ========== LangChain回调接口实现 ==========
    def on_agent_action(self, action: AgentAction, **kwargs: Any) -> None:
        """Agent执行动作时调用"""
        if not self.enable_trajectory:
            return
        
        self.step_counter += 1
        
        trajectory_entry = {
            "type": "action",
            "step": self.step_counter,
            "timestamp": datetime.now().isoformat(),
            "tool": action.tool,
            "tool_input": action.tool_input,
            "log": action.log,
            "session_id": self.current_session_id
        }
        
        self.trajectories.append(trajectory_entry)
        
        if self.enable_tool_tracking:
            tool_call = {
                "tool_name": action.tool,
                "input": action.tool_input,
                "timestamp": datetime.now().isoformat(),
                "step": self.step_counter
            }
            self.tool_calls.append(tool_call)
        
        self.logger.debug(f"🔧 Agent动作: {action.tool} - 步骤 {self.step_counter}")
    
    def on_agent_finish(self, finish: AgentFinish, **kwargs: Any) -> None:
        """Agent完成执行时调用"""
        if not self.enable_trajectory:
            return
        
        trajectory_entry = {
            "type": "finish",
            "step": self.step_counter + 1,
            "timestamp": datetime.now().isoformat(),
            "return_values": finish.return_values,
            "log": finish.log,
            "session_id": self.current_session_id
        }
        
        self.trajectories.append(trajectory_entry)
        self.logger.info(f"✅ Agent执行完成 - 总步骤: {self.step_counter + 1}")
    
    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs: Any) -> None:
        """工具开始执行时调用"""
        if not self.enable_tool_tracking:
            return
        
        tool_name = serialized.get("name", "unknown")
        
        self.logger.debug(f"🔧 工具开始: {tool_name}")
    
    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        """工具执行完成时调用"""
        if not self.enable_tool_tracking:
            return
        
        # 更新最新的工具调用记录
        if self.tool_calls:
            self.tool_calls[-1]["output"] = output
            self.tool_calls[-1]["end_timestamp"] = datetime.now().isoformat()
        
        # 更新轨迹中的工具输出
        if self.trajectories and self.trajectories[-1]["type"] == "action":
            self.trajectories[-1]["output"] = output
            self.trajectories[-1]["end_timestamp"] = datetime.now().isoformat()
        
        self.logger.debug("🔧 工具执行完成")
    
    def on_tool_error(self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any) -> None:
        """工具执行出错时调用"""
        if not self.enable_tool_tracking:
            return
        
        error_info = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.now().isoformat()
        }
        
        # 更新工具调用记录
        if self.tool_calls:
            self.tool_calls[-1]["error"] = error_info
        
        # 更新轨迹记录
        if self.trajectories and self.trajectories[-1]["type"] == "action":
            self.trajectories[-1]["error"] = error_info
        
        self.logger.error(f"❌ 工具执行出错: {error}")
    
    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any) -> None:
        """LLM开始调用时调用"""
        if not self.enable_llm_tracking:
            return
        
        llm_call = {
            "model": serialized.get("id", ["unknown"])[-1],
            "prompts": prompts,
            "start_timestamp": datetime.now().isoformat(),
            "step": self.step_counter
        }
        
        self.llm_calls.append(llm_call)
        self.logger.debug(f"🤖 LLM调用开始: {llm_call['model']}")
    
    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """LLM调用完成时调用"""
        if not self.enable_llm_tracking or not self.llm_calls:
            return
        
        # 更新最新的LLM调用记录
        llm_call = self.llm_calls[-1]
        llm_call["end_timestamp"] = datetime.now().isoformat()
        llm_call["response"] = {
            "generations": [[g.text for g in gen] for gen in response.generations],
            "llm_output": response.llm_output
        }
        
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            llm_call["usage"] = {
                "input_tokens": getattr(response.usage_metadata, 'input_tokens', 0),
                "output_tokens": getattr(response.usage_metadata, 'output_tokens', 0),
                "total_tokens": getattr(response.usage_metadata, 'total_tokens', 0)
            }
        
        self.logger.debug("🤖 LLM调用完成")
    
    def on_llm_error(self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any) -> None:
        """LLM调用出错时调用"""
        if not self.enable_llm_tracking or not self.llm_calls:
            return
        
        self.llm_calls[-1]["error"] = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.now().isoformat()
        }
        
        self.logger.error(f"❌ LLM调用出错: {error}")
    
    # ========== 轨迹数据访问方法 ==========
    def get_trajectories(self) -> List[Dict[str, Any]]:
        """获取所有轨迹数据"""
        return self.trajectories.copy()
    
    def get_tool_calls(self) -> List[Dict[str, Any]]:
        """获取所有工具调用记录"""
        return self.tool_calls.copy()
    
    def get_llm_calls(self) -> List[Dict[str, Any]]:
        """获取所有LLM调用记录"""
        return self.llm_calls.copy()
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """获取执行摘要"""
        return {
            "session_id": self.current_session_id,
            "total_steps": len(self.trajectories),
            "tool_calls": len(self.tool_calls),
            "llm_calls": len(self.llm_calls),
            "errors": len([t for t in self.trajectories if "error" in t]),
            "start_time": self.trajectories[0]["timestamp"] if self.trajectories else None,
            "end_time": self.trajectories[-1]["timestamp"] if self.trajectories else None
        }
    
    def get_training_examples(self) -> List[Dict[str, Any]]:
        """从轨迹中提取训练样例"""
        examples = []
        current_example = {}
        
        for trajectory in self.trajectories:
            if trajectory["type"] == "action":
                tool_name = trajectory["tool"]
                tool_output = trajectory.get("output", {})
                
                # 根据工具类型更新当前样例
                if tool_name == "question_generation":
                    current_example["question"] = self._extract_question(tool_output)
                elif tool_name == "sql_generation":
                    current_example["sql"] = self._extract_sql(tool_output)
                    
                    # 如果有问题和SQL，创建训练样例
                    if "question" in current_example and "sql" in current_example:
                        example = TrainingExample(
                            question=current_example["question"],
                            sql=current_example["sql"],
                            scenario=current_example.get("scenario", {}),
                            operations=current_example.get("operations", []),
                            tables=current_example.get("tables", []),
                            validation=current_example.get("validation", {}),
                            quality_score=current_example.get("quality_score", 0.0)
                        )
                        
                        examples.append(example.to_training_format())
                        current_example = {}  # 重置
        
        return examples
    
    # ========== 轨迹持久化方法 ==========
    def save_trajectories(self, filename: Optional[str] = None) -> str:
        """保存轨迹到文件"""
        if not filename:
            filename = f"trajectory_{self.current_session_id}.json"
        
        filepath = self.output_directory / filename
        
        trajectory_data = {
            "session_id": self.current_session_id,
            "summary": self.get_execution_summary(),
            "trajectories": self.trajectories,
            "tool_calls": self.tool_calls,
            "llm_calls": self.llm_calls
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(trajectory_data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"💾 轨迹已保存: {filepath}")
        return str(filepath)
    
    def save_training_examples(self, filename: Optional[str] = None) -> str:
        """保存提取的训练样例"""
        if not filename:
            filename = f"training_examples_{self.current_session_id}.jsonl"
        
        filepath = self.output_directory / filename
        examples = self.get_training_examples()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            for example in examples:
                f.write(json.dumps(example, ensure_ascii=False) + '\n')
        
        self.logger.info(f"📚 训练样例已保存: {filepath} ({len(examples)} 条)")
        return str(filepath)
    
    def clear_trajectories(self) -> None:
        """清空轨迹数据"""
        self.trajectories = []
        self.tool_calls = []
        self.llm_calls = []
        self.step_counter = 0
        self.current_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        self.logger.info(f"🧹 轨迹数据已清空 - 新会话ID: {self.current_session_id}")
    
    # ========== 内部辅助方法 ==========
    def _extract_question(self, tool_output: Any) -> str:
        """从工具输出中提取问题"""
        if isinstance(tool_output, dict):
            return tool_output.get("question", "")
        return str(tool_output)
    
    def _extract_sql(self, tool_output: Any) -> str:
        """从工具输出中提取SQL"""
        if isinstance(tool_output, dict):
            return tool_output.get("sql", "")
        return str(tool_output)


class TrajectoryAnalyzer:
    """轨迹分析器 - 分析和统计轨迹数据
    
    职责：
    - 分析轨迹执行模式
    - 统计工具使用频率
    - 识别常见错误模式
    - 生成性能报告
    """
    
    def __init__(self, trajectories: List[Dict[str, Any]]):
        """
        初始化分析器
        
        Args:
            trajectories: 轨迹数据列表
        """
        self.trajectories = trajectories
        self.logger = logging.getLogger(__name__)
    
    def analyze_tool_usage(self) -> Dict[str, Any]:
        """分析工具使用情况"""
        tool_counts = {}
        tool_errors = {}
        
        for trajectory in self.trajectories:
            if trajectory["type"] == "action":
                tool_name = trajectory["tool"]
                tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
                
                if "error" in trajectory:
                    tool_errors[tool_name] = tool_errors.get(tool_name, 0) + 1
        
        return {
            "tool_usage_counts": tool_counts,
            "tool_error_counts": tool_errors,
            "most_used_tools": sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)[:5],
            "error_rates": {tool: tool_errors.get(tool, 0) / count 
                          for tool, count in tool_counts.items()}
        }
    
    def analyze_execution_patterns(self) -> Dict[str, Any]:
        """分析执行模式"""
        total_steps = len([t for t in self.trajectories if t["type"] == "action"])
        error_steps = len([t for t in self.trajectories if "error" in t])
        
        # 分析工具序列
        tool_sequence = [t["tool"] for t in self.trajectories if t["type"] == "action"]
        
        return {
            "total_action_steps": total_steps,
            "error_steps": error_steps,
            "success_rate": (total_steps - error_steps) / total_steps if total_steps > 0 else 0,
            "tool_sequence": tool_sequence,
            "unique_tools_used": len(set(tool_sequence)),
            "average_retries": self._calculate_average_retries()
        }
    
    def _calculate_average_retries(self) -> float:
        """计算平均重试次数"""
        tool_counts = {}
        
        for trajectory in self.trajectories:
            if trajectory["type"] == "action":
                tool_name = trajectory["tool"]
                tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
        
        if not tool_counts:
            return 0.0
        
        retry_counts = [count - 1 for count in tool_counts.values() if count > 1]
        return sum(retry_counts) / len(tool_counts) if tool_counts else 0.0


# ========== 便利函数 ==========
def create_callback_handler(trajectory_dir: str = "./trajectories", 
                           enable_all: bool = True) -> SemanticSQLCallbackHandler:
    """
    创建回调处理器的便利函数
    
    Args:
        trajectory_dir: 轨迹输出目录
        enable_all: 是否启用所有跟踪功能
        
    Returns:
        配置好的回调处理器
    """
    return SemanticSQLCallbackHandler(
        enable_trajectory=enable_all,
        enable_llm_tracking=enable_all,
        enable_tool_tracking=enable_all,
        output_directory=trajectory_dir
    )