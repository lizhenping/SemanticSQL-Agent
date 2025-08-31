"""
BaseAgent - ReAct pattern implementation
Based on the design specification - implements ReAct (Reasoning + Acting) pattern
"""

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

import openai
from config.settings import Settings
from config.database import DatabaseConfig
from models.schemas import AgentExecution, AgentStep, AgentStepType
from agent.callbacks import ExecutionCallback
from utils.trajectory import TrajectoryRecorder




class BaseAgent(ABC):
    """Base agent class implementing ReAct pattern"""
    
    def __init__(self, settings: Settings, db_config: DatabaseConfig):
        """Initialize agent"""
        self.settings = settings
        self.db_config = db_config
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Initialize LLM client
        self.llm_client = openai.OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url
        )
        
        self.llm_config = {
            'model': settings.llm_model,
            'temperature': settings.llm_temperature,
            'max_tokens': settings.llm_max_tokens
        }
        
        # Tool mapping
        self.tools: Dict[str, Any] = {}
        self.tool_descriptions: Dict[str, str] = {}
        
        # Current execution state
        self.current_execution: Optional[AgentExecution] = None
        self.max_steps = settings.max_steps
        self.enable_reflection = settings.enable_reflection
        self.enable_thinking = settings.enable_thinking
        
        # Callbacks for execution tracking
        self.callbacks: List[ExecutionCallback] = []
        
        # Trajectory recorder
        if settings.trajectory_enabled:
            self.trajectory_recorder = TrajectoryRecorder(
                output_dir=settings.trajectory_directory,
                max_trajectories=settings.trajectory_max_count
            )
        else:
            self.trajectory_recorder = None
        
        # Initialize tools
        self._initialize_tools()
        
    @abstractmethod
    def _initialize_tools(self):
        """初始化智能体工具 - 子类需要实现"""
        pass
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """获取系统提示词 - 子类需要实现"""
        pass
    
    def register_tool(self, name: str, tool_instance, description: str):
        """注册工具"""
        self.tools[name] = tool_instance
        self.tool_descriptions[name] = description
        self.logger.debug(f"注册工具: {name}")
    
    def add_callback(self, callback: ExecutionCallback):
        """Add execution callback"""
        self.callbacks.append(callback)
    
    def new_task(self, task: str) -> AgentExecution:
        """Start new task"""
        self.logger.info(f"Starting new task: {task}")
        
        # Create execution record
        self.current_execution = AgentExecution(task=task)
        
        # Notify callbacks
        for callback in self.callbacks:
            callback.on_execution_start(self.current_execution)
        
        try:
            # Execute ReAct loop
            result = self._execute_react_loop(task)
            self.current_execution.complete(result)
            
        except Exception as e:
            self.logger.error(f"Task execution failed: {e}")
            self.current_execution.complete(error=str(e))
            
            # Notify callbacks of error
            for callback in self.callbacks:
                callback.on_error(self.current_execution, e)
        
        finally:
            # Notify callbacks of completion
            for callback in self.callbacks:
                callback.on_execution_complete(self.current_execution)
            
            # Save trajectory if enabled
            if self.trajectory_recorder:
                self.trajectory_recorder.save_execution(self.current_execution)
        
        return self.current_execution
    
    def call_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        调用指定工具
        
        Args:
            tool_name: 工具名称
            **kwargs: 工具参数
            
        Returns:
            工具执行结果
        """
        if tool_name not in self.tools:
            return {
                "success": False,
                "error": f"工具 '{tool_name}' 不存在"
            }
        
        tool = self.tools[tool_name]
        
        try:
            # 执行工具
            if hasattr(tool, 'execute'):
                result = tool.execute(**kwargs)
            elif hasattr(tool, 'run'):
                result = tool.run(**kwargs)
            else:
                # 如果工具是函数
                result = tool(**kwargs)
            
            # 确保返回格式统一
            if isinstance(result, dict):
                return result
            else:
                return {
                    "success": True,
                    "data": result
                }
                
        except Exception as e:
            self.logger.error(f"工具 '{tool_name}' 执行失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _execute_react_loop(self, task: str) -> Any:
        """执行ReAct推理循环"""
        
        # 初始观察
        self._add_step(
            AgentStepType.OBSERVATION,
            f"用户任务: {task}"
        )
        
        # 开始ReAct循环
        for step_count in range(self.max_steps):
            # 生成思考和行动
            response = self._generate_next_action()
            
            # 解析响应
            thought, action, action_input = self._parse_response(response)
            
            # 添加思考步骤
            if thought and self.enable_thinking:
                self._add_step(AgentStepType.THOUGHT, thought)
            
            # 如果没有行动，说明任务完成
            if not action or action.lower() in ['finish', 'complete', 'done']:
                self.logger.info("智能体认为任务已完成")
                break
                
            # 执行行动
            try:
                tool_output = self._execute_action(action, action_input)
                
                # 添加行动步骤
                self._add_step(
                    AgentStepType.ACTION,
                    f"使用工具: {action}",
                    tool_name=action,
                    tool_input=action_input,
                    tool_output=tool_output
                )
                
                # 添加观察步骤
                self._add_step(
                    AgentStepType.OBSERVATION,
                    f"工具执行结果: {self._format_tool_output(tool_output)}"
                )
                
                # 反思（如果启用）
                if self.enable_reflection:
                    reflection = self._reflect_on_progress()
                    if reflection:
                        self._add_step(AgentStepType.REFLECTION, reflection)
                        
            except Exception as e:
                error_msg = f"工具执行失败: {e}"
                self.logger.error(error_msg)
                
                # 只添加观察步骤，不重复添加ACTION步骤
                self._add_step(
                    AgentStepType.OBSERVATION,
                    f"工具执行失败: {error_msg}"
                )
        
        # 生成最终结果
        return self._generate_final_result()
    
    def _generate_next_action(self) -> str:
        """生成下一个行动"""
        
        # 构建提示词
        system_prompt = self.get_system_prompt()
        conversation_history = self._build_conversation_history()
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": conversation_history}
        ]
        
        # 调用LLM
        response = self.llm_client.chat.completions.create(
            messages=messages,
            **self.llm_config
        )
        
        return response.choices[0].message.content.strip()
    
    def _parse_response(self, response: str) -> Tuple[Optional[str], Optional[str], Optional[Dict]]:
        """解析LLM响应，提取思考、行动和输入"""
        
        thought = None
        action = None
        action_input = None
        
        # 解析思考
        thought_match = re.search(r'(?:Thought|思考)[:：]\s*(.+?)(?=\n(?:Action|行动)|$)', response, re.DOTALL | re.IGNORECASE)
        if thought_match:
            thought = thought_match.group(1).strip()
        
        # 解析行动
        action_match = re.search(r'(?:Action|行动)[:：]\s*(\w+)', response, re.IGNORECASE)
        if action_match:
            action = action_match.group(1).strip()
        
        # 解析行动输入
        input_match = re.search(r'(?:Action Input|行动输入)[:：]\s*(.+?)(?=\n|$)', response, re.DOTALL | re.IGNORECASE)
        if input_match:
            try:
                action_input = json.loads(input_match.group(1).strip())
            except:
                # 智能回退：根据工具类型选择合适的参数名
                input_text = input_match.group(1).strip()
                
                # 根据不同的工具使用不同的默认参数名
                if action and action.lower() in ['sequential_thinking', 'think', 'thinking']:
                    action_input = {
                        "context": {},
                        "problem": input_text
                    }
                elif action and 'domain' in action.lower():
                    action_input = {
                        "schema_info": {}  # 会自动从内存注入
                    }
                elif action and 'field' in action.lower() or action and 'classify' in action.lower():
                    action_input = {
                        "table_info": {}  # 会自动从内存注入
                    }
                elif action and 'question' in action.lower():
                    action_input = {
                        "scenario": input_text
                    }
                elif action and 'sql' in action.lower():
                    action_input = {
                        "question": input_text
                    }
                else:
                    # 通用回退
                    action_input = {"query": input_text}
        
        return thought, action, action_input
    
    def _execute_action(self, action: str, action_input: Optional[Dict]) -> Any:
        """执行指定的行动/工具"""
        
        if action not in self.tools:
            raise ValueError(f"未知工具: {action}")
        
        tool = self.tools[action]
        
        # 执行工具
        try:
            if hasattr(tool, 'execute'):
                if action_input:
                    result = tool.execute(**action_input)
                else:
                    result = tool.execute()
            elif hasattr(tool, 'run'):
                if action_input:
                    result = tool.run(**action_input)
                else:
                    result = tool.run()
            else:
                # 如果工具是函数
                if action_input:
                    result = tool(**action_input)
                else:
                    result = tool()
            
            # 添加详细调试日志
            self.logger.debug(f"Tool {action} result type: {type(result)}")
            if hasattr(result, '__dict__'):
                self.logger.debug(f"Tool {action} result attributes: {list(result.__dict__.keys())}")
            
            # 确保返回可序列化的结果
            try:
                serialized = self._serialize_for_storage(result)
                return serialized
            except Exception as serialize_error:
                # 使用DEBUG级别记录序列化错误，减少日志噪音
                if "slice" in str(serialize_error).lower():
                    self.logger.debug(f"工具结果包含slice对象: {serialize_error}")
                    # 只在DEBUG模式下进行深度检查
                    if self.logger.isEnabledFor(logging.DEBUG):
                        self._debug_object_for_slices(result, "result")
                else:
                    self.logger.warning(f"序列化工具输出失败: {serialize_error}")
                    self.logger.debug(f"原始结果类型: {type(result)}")
                
                # 返回简化但保留成功状态的版本
                if isinstance(result, dict) and "success" in result:
                    return {
                        "success": result.get("success", False),
                        "message": "结果已简化（包含不可序列化对象）",
                        "error": result.get("error")
                    }
                else:
                    return {"success": False, "error": f"序列化失败: {serialize_error}"}
            
        except Exception as e:
            self.logger.error(f"工具 '{action}' 执行失败: {e}")
            raise
    
    def _add_step(self, step_type: AgentStepType, content: str, **kwargs):
        """Add execution step"""
        # Debug: check all kwargs for slice objects
        for key, value in kwargs.items():
            if isinstance(value, slice):
                self.logger.error(f"Found slice in kwargs[{key}]: {value}")
            elif isinstance(value, dict):
                for k, v in value.items():
                    if isinstance(k, slice):
                        self.logger.error(f"Found slice key in kwargs[{key}][{k}]: {k}")
                    if isinstance(v, slice):
                        self.logger.error(f"Found slice value in kwargs[{key}][{k}]: {v}")
        
        # Serialize tool_output if it contains complex objects
        if 'tool_output' in kwargs and kwargs['tool_output'] is not None:
            try:
                self.logger.debug(f"Serializing tool_output of type: {type(kwargs['tool_output'])}")
                kwargs['tool_output'] = self._serialize_for_storage(kwargs['tool_output'])
            except Exception as e:
                self.logger.error(f"序列化tool_output失败: {e}")
                # Debug the original object for slices
                self._debug_object_for_slices(kwargs['tool_output'], "tool_output")
                kwargs['tool_output'] = str(kwargs['tool_output'])
        
        # Serialize tool_input as well
        if 'tool_input' in kwargs and kwargs['tool_input'] is not None:
            try:
                kwargs['tool_input'] = self._serialize_for_storage(kwargs['tool_input'])
            except Exception as e:
                self.logger.error(f"序列化tool_input失败: {e}")
                kwargs['tool_input'] = str(kwargs['tool_input'])
        
        try:
            step = AgentStep(
                step_type=step_type,
                content=content,
                timestamp=datetime.now(),
                **kwargs
            )
        except Exception as e:
            self.logger.error(f"创建AgentStep失败: {e}")
            self.logger.error(f"Error type: {type(e)}")
            self.logger.error(f"kwargs keys: {list(kwargs.keys())}")
            for key, value in kwargs.items():
                self.logger.error(f"  {key}: {type(value)} = {str(value)[:100]}")
            
            # Check if the error is about slice objects
            if "unhashable type: 'slice'" in str(e):
                self.logger.error("SLICE ERROR DETECTED - debugging kwargs:")
                self._debug_object_for_slices(kwargs, "kwargs")
            
            # 创建简化版本
            step = AgentStep(
                step_type=step_type,
                content=content,
                timestamp=datetime.now(),
                tool_name=kwargs.get('tool_name'),
                error=str(e)
            )
        
        if self.current_execution:
            self.current_execution.add_step(step)
            
            # Notify callbacks
            for callback in self.callbacks:
                callback.on_step_complete(self.current_execution, step)
            
        # Log step
        self.logger.debug(f"{step_type.value}: {content}")
    
    def _build_conversation_history(self) -> str:
        """构建对话历史"""
        if not self.current_execution or not self.current_execution.steps:
            return f"任务: {self.current_execution.task if self.current_execution else '未知任务'}"
        
        history = []
        for step in self.current_execution.steps:
            if step.step_type == AgentStepType.OBSERVATION:
                history.append(f"Observation: {step.content}")
            elif step.step_type == AgentStepType.THOUGHT:
                history.append(f"Thought: {step.content}")
            elif step.step_type == AgentStepType.ACTION:
                history.append(f"Action: {step.tool_name}")
                if step.tool_input:
                    history.append(f"Action Input: {json.dumps(step.tool_input, ensure_ascii=False)}")
                if step.tool_output:
                    history.append(f"Observation: {self._format_tool_output(step.tool_output)}")
                elif step.error:
                    history.append(f"Observation: ERROR - {step.error}")
        
        return "\n".join(history) + "\n\nThought:"
    
    def _format_tool_output(self, output: Any) -> str:
        """格式化工具输出"""
        if isinstance(output, dict):
            try:
                # 先确保数据可以被序列化（处理slice等不可序列化对象）
                clean_output = self._serialize_for_storage(output)
                
                # 对字典类型，保留更多信息，特别是success和关键数据
                formatted = json.dumps(clean_output, ensure_ascii=False, indent=2)
                if len(formatted) > 2000:  # 增加到2000字符
                    # 如果太长，保留关键信息
                    summary = {
                        "success": clean_output.get("success"),
                        "message": clean_output.get("message", ""),
                        "error": clean_output.get("error"),
                    }
                    # 添加数据摘要
                    if "schemas" in clean_output:
                        summary["schemas_count"] = len(clean_output["schemas"])
                    if "results" in clean_output:
                        summary["results_count"] = len(clean_output.get("results", []))
                    if "data" in clean_output:
                        summary["data_sample"] = clean_output.get("data", [])[:2]  # 只显示前2条
                    
                    return json.dumps(summary, ensure_ascii=False, indent=2) + "\n[输出已简化，完整信息已保存]"
                return formatted
            except Exception as e:
                # 使用DEBUG级别记录序列化错误，减少日志噪音
                if "slice" in str(e).lower():
                    self.logger.debug(f"工具输出包含slice对象，使用简化格式: {e}")
                else:
                    self.logger.warning(f"格式化工具输出失败: {e}")
                
                # 返回简化但有用的输出
                if isinstance(output, dict):
                    # 尝试提取关键信息
                    simplified = {
                        "success": output.get("success", False),
                        "message": "输出已简化（包含不可序列化对象）",
                        "data_type": type(output.get("data", None)).__name__ if "data" in output else None
                    }
                    try:
                        return json.dumps(simplified, ensure_ascii=False)
                    except:
                        return str(simplified)
                else:
                    return f"[{type(output).__name__}] {str(output)[:500]}"
        elif isinstance(output, (list, tuple)):
            return str(output)[:1000]
        else:
            return str(output)[:1000]
    
    def _reflect_on_progress(self) -> Optional[str]:
        """反思进度 - 子类可以重写"""
        if len(self.current_execution.steps) > 3:
            return "让我评估一下当前进度，确保朝着正确方向前进..."
        return None
    
    def _generate_final_result(self) -> Any:
        """生成最终结果 - 子类可以重写"""
        return {
            "task": self.current_execution.task,
            "completed": True,
            "steps": len(self.current_execution.steps),
            "execution_time": self.current_execution.get_duration()
        }
    
    def _debug_object_for_slices(self, obj: Any, path: str = ""):
        """Debug helper to find slice objects in complex data structures"""
        try:
            if isinstance(obj, slice):
                self.logger.error(f"Found slice at {path}: {obj}")
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(k, slice):
                        self.logger.error(f"Found slice key at {path}: {k}")
                    self._debug_object_for_slices(v, f"{path}.{k}")
            elif isinstance(obj, (list, tuple)):
                for i, item in enumerate(obj):
                    self._debug_object_for_slices(item, f"{path}[{i}]")
            elif hasattr(obj, '__dict__'):
                for attr_name, attr_value in obj.__dict__.items():
                    self._debug_object_for_slices(attr_value, f"{path}.{attr_name}")
        except Exception as e:
            self.logger.error(f"Debug slice check failed at {path}: {e}")

    def _serialize_for_storage(self, obj: Any) -> Any:
        """Serialize objects for storage/logging"""
        if obj is None:
            return None
        
        try:
            # Handle special types that can't be serialized
            if isinstance(obj, slice):
                return str(obj)
                
            # If it's a Pydantic model, use model_dump with datetime serialization
            if hasattr(obj, 'model_dump'):
                return obj.model_dump(mode='json')
            # If it's a dict, recursively serialize nested objects
            elif isinstance(obj, dict):
                serialized_dict = {}
                for k, v in obj.items():
                    # 处理不可哈希的键
                    if isinstance(k, slice):
                        key = f"slice_{k.start}_{k.stop}_{k.step}"
                    elif hasattr(k, '__hash__') and k.__hash__ is not None:
                        try:
                            # Test if the key is actually hashable
                            hash(k)
                            key = str(k)
                        except TypeError:
                            key = str(type(k).__name__) + "_" + str(id(k))
                    else:
                        key = str(type(k).__name__) + "_" + str(id(k))
                    serialized_dict[key] = self._serialize_for_storage(v)
                return serialized_dict
            # If it's a list, recursively serialize elements
            elif isinstance(obj, list):
                return [self._serialize_for_storage(item) for item in obj]
            # If it's a tuple, convert to list
            elif isinstance(obj, tuple):
                return [self._serialize_for_storage(item) for item in obj]
            # Test if it's already JSON serializable
            else:
                import json
                json.dumps(obj, default=str)
                return obj
        except (TypeError, ValueError, AttributeError) as e:
            # If it can't be serialized, convert to string
            self.logger.error(f"Serialization fallback for {type(obj)}: {e}")
            self.logger.error(f"Object content: {str(obj)[:200]}")
            if isinstance(obj, dict):
                for k, v in obj.items():
                    self.logger.error(f"  Key {k} (type {type(k)}): {type(v)}")
            return str(obj)