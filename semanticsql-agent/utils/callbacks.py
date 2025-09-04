"""
Trajectory recording callbacks for agent execution
Based on LangChain BaseCallbackHandler
"""

import logging
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from uuid import UUID

from langchain.callbacks.base import BaseCallbackHandler
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.outputs import LLMResult

from models.agent import AgentExecution, AgentStep, AgentStepType
from utils.trajectory import TrajectoryRecorder


class TrajectoryCallbackHandler(BaseCallbackHandler):
    """LangChain callback handler for recording execution trajectories"""
    
    def __init__(self, trajectory_recorder: Optional[TrajectoryRecorder] = None):
        super().__init__()
        self.recorder = trajectory_recorder
        self.logger = logging.getLogger(__name__)
        self.trajectories = []
        self.current_execution = None
        self.current_step = None
        # 初始化memory引用
        object.__setattr__(self, 'memory', None)
    
    def on_agent_action(
        self,
        action: AgentAction,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any
    ) -> Any:
        """记录Agent动作"""
        self.logger.debug(f"Agent action: {action.tool} with input: {action.tool_input}")
        
        # 确保tool_input是字典格式，避免Pydantic验证错误
        tool_input_dict = action.tool_input
        if isinstance(action.tool_input, str):
            try:
                import json
                tool_input_dict = json.loads(action.tool_input)
            except:
                tool_input_dict = {"input": action.tool_input}
        
        step = AgentStep(
            step_type=AgentStepType.ACTION,
            content=f"Calling tool: {action.tool}",
            tool_name=action.tool,
            tool_input=tool_input_dict,
            timestamp=datetime.now()
        )
        
        self.trajectories.append({
            "type": "action",
            "tool": action.tool,
            "input": action.tool_input,
            "timestamp": datetime.now(),
            "run_id": str(run_id)
        })
        
        if self.recorder and self.current_execution:
            self.current_execution.steps.append(step)
    
    def on_agent_finish(
        self,
        finish: AgentFinish,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any
    ) -> Any:
        """记录Agent完成"""
        self.logger.info(f"Agent finished with output: {finish.return_values}")
        
        # 打印工具调用历史
        if hasattr(self, 'tool_call_history') and self.tool_call_history:
            self.logger.info("\n📊 Tool Call History:")
            self.logger.info("=" * 80)
            for i, record in enumerate(self.tool_call_history, 1):
                self.logger.info(f"{i}. Tool: {record['tool']}")
                self.logger.info(f"   Time: {record['timestamp']}")
                self.logger.info(f"   Status: {record['status']}")
                self.logger.info(f"   Input: {record['input'][:100]}...")
                if 'output_preview' in record:
                    self.logger.info(f"   Output: {record['output_preview']}...")
                self.logger.info("-" * 40)
        
        self.trajectories.append({
            "type": "finish",
            "output": finish.return_values,
            "timestamp": datetime.now(),
            "run_id": str(run_id)
        })
    
    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any
    ) -> Any:
        """工具开始执行"""
        tool_name = serialized.get("name", "unknown")
        self.logger.info(f"🔧 Tool '{tool_name}' started with input: {input_str}")
        
        # 记录到工具调用历史
        if not hasattr(self, 'tool_call_history'):
            self.tool_call_history = []
        
        self.tool_call_history.append({
            "tool": tool_name,
            "input": input_str,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "started"
        })
        
        if self.current_execution:
            self.current_step = AgentStep(
                step_type=AgentStepType.ACTION,
                content=f"Executing tool: {tool_name}",
                tool_name=tool_name,
                tool_input={"input": input_str},
                timestamp=datetime.now()
            )
    
    def on_tool_end(
        self,
        output: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any
    ) -> Any:
        """工具执行结束"""
        self.logger.info(f"✅ Tool finished successfully")
        
        # 更新工具调用历史
        if hasattr(self, 'tool_call_history') and self.tool_call_history:
            # 找到最后一个 started 状态的记录
            for record in reversed(self.tool_call_history):
                if record.get("status") == "started":
                    record["status"] = "completed"
                    record["output_preview"] = output[:100] if isinstance(output, str) else str(output)[:100]
                    break
        
        if self.current_step:
            # 解析工具输出 - 处理JSON字符串格式
            parsed_output = output
            if isinstance(output, str):
                try:
                    import json
                    parsed_output = json.loads(output)
                    self.logger.debug(f"Successfully parsed JSON output for {self.current_step.tool_name}")
                except (json.JSONDecodeError, ValueError):
                    # 如果不是JSON格式，保持原样
                    parsed_output = output
                    self.logger.debug(f"Output is not JSON format for {self.current_step.tool_name}")
            
            self.current_step.tool_output = parsed_output
            self.current_step.duration_ms = int(
                (datetime.now() - self.current_step.timestamp).total_seconds() * 1000
            )
            
            if self.current_execution:
                self.current_execution.steps.append(self.current_step)
            
            # 保存到轨迹（包含工具名称）
            if self.current_step.tool_name:
                self.trajectories.append({
                    "type": "tool_end",
                    "tool_name": self.current_step.tool_name,
                    "input": self.current_step.tool_input,
                    "output": parsed_output,
                    "timestamp": datetime.now(),
                    "run_id": str(run_id)
                })
                
                # 如果是分析工具，自动保存结果到记忆
                if hasattr(self, 'memory') and self.memory and self.current_step.tool_name in [
                    'schema_extraction', 'domain_analysis', 'field_classification',
                    'column_meaning_analysis', 'table_meaning_analysis', 'er_analysis'
                ]:
                    try:
                        if isinstance(parsed_output, dict):
                            # 根据工具类型保存到对应的记忆位置
                            analysis_type_mapping = {
                                'schema_extraction': 'schema_info',
                                'domain_analysis': 'domain_info', 
                                'field_classification': 'field_classification',
                                'column_meaning_analysis': 'column_meanings',
                                'table_meaning_analysis': 'table_meanings',
                                'er_analysis': 'er_relations'
                            }
                            
                            analysis_type = analysis_type_mapping.get(self.current_step.tool_name)
                            if analysis_type and hasattr(self.memory, 'update_analysis'):
                                self.memory.update_analysis(analysis_type, parsed_output)
                                self.logger.info(f"Saved {self.current_step.tool_name} result to memory as {analysis_type}")
                            else:
                                # 兜底：使用标准LangChain save_context
                                self.memory.save_context(
                                    {"tool_name": self.current_step.tool_name},
                                    parsed_output
                                )
                    except Exception as e:
                        self.logger.warning(f"Failed to save tool output to memory: {e}")
            
            self.current_step = None
    
    def on_tool_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any
    ) -> Any:
        """工具执行出错"""
        self.logger.error(f"Tool error: {error}")
        
        if self.current_step:
            self.current_step.error = str(error)
            
            if self.current_execution:
                self.current_execution.steps.append(self.current_step)
                self.current_execution.status = "failed"
                self.current_execution.error = str(error)
            
            self.current_step = None
    
    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any
    ) -> Any:
        """LLM开始生成"""
        self.logger.debug(f"LLM started with {len(prompts)} prompts")
    
    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any
    ) -> Any:
        """LLM生成结束"""
        from utils.thinking_parser import ThinkingOutputParser
        
        # 使用 ThinkingOutputParser 处理输出
        parser = ThinkingOutputParser()
        
        if response.generations:
            for generation_list in response.generations:
                for generation in generation_list:
                    if hasattr(generation, 'text') and generation.text:
                        # 解析输出
                        parsed = parser.parse(generation.text)
                        
                        # 记录思考过程
                        if parsed['has_thinking']:
                            self.logger.debug(f"LLM thinking: {parsed['thinking'][:200]}...")
                        
                        # 更新生成的文本为清理后的答案
                        generation.text = parsed['answer']
        
        self.logger.debug(f"LLM finished with {len(response.generations)} generations")
    
    def on_llm_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any
    ) -> Any:
        """LLM生成出错"""
        self.logger.error(f"LLM error: {error}")
    
    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any
    ) -> Any:
        """Chain开始执行"""
        # 添加None检查
        if serialized is not None:
            chain_name = serialized.get('name', 'unknown')
        else:
            chain_name = 'unknown'
        self.logger.debug(f"Chain started: {chain_name}")
    
    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any
    ) -> Any:
        """Chain执行结束"""
        # 添加None检查
        if outputs is not None:
            self.logger.debug(f"Chain finished with outputs: {outputs}")
        else:
            self.logger.debug("Chain finished with no outputs")
    
    def on_chain_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any
    ) -> Any:
        """Chain执行出错"""
        self.logger.error(f"Chain error: {error}")
    
    def set_execution(self, execution: AgentExecution):
        """设置当前执行"""
        self.current_execution = execution
    
    def get_trajectories(self) -> List[Dict[str, Any]]:
        """获取所有轨迹"""
        return self.trajectories
    
    def clear_trajectories(self):
        """清空轨迹"""
        self.trajectories = []