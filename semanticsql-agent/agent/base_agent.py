"""
BaseAgent - trae_agent风格的智能体基础类
实现ReAct (Reasoning + Acting) 模式
"""

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from datetime import datetime
from dataclasses import dataclass

import openai
from config.trae_config import TraeConfig


class AgentStepType(Enum):
    """智能体步骤类型"""
    OBSERVATION = "observation"
    THOUGHT = "thought" 
    ACTION = "action"
    REFLECTION = "reflection"


@dataclass
class AgentStep:
    """智能体执行步骤"""
    step_type: AgentStepType
    content: str
    timestamp: datetime
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[Any] = None
    error: Optional[str] = None


@dataclass 
class AgentExecution:
    """智能体执行记录"""
    task: str
    steps: List[AgentStep]
    final_result: Optional[Any] = None
    success: bool = True
    total_steps: int = 0
    execution_time: float = 0.0
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task": self.task,
            "steps": [
                {
                    "step_type": step.step_type.value,
                    "content": step.content,
                    "timestamp": step.timestamp.isoformat(),
                    "tool_name": step.tool_name,
                    "tool_input": step.tool_input,
                    "tool_output": step.tool_output,
                    "error": step.error
                } 
                for step in self.steps
            ],
            "final_result": self.final_result,
            "success": self.success,
            "total_steps": self.total_steps,
            "execution_time": self.execution_time,
            "error": self.error
        }


class BaseAgent(ABC):
    """智能体基础类 - 实现ReAct模式"""
    
    def __init__(self, config: TraeConfig):
        """初始化智能体"""
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 初始化LLM客户端
        self.llm_client = openai.OpenAI(
            api_key=config.llm.api_key,
            base_url=config.llm.base_url
        )
        
        self.llm_config = {
            'model': config.llm.model,
            'temperature': config.llm.temperature,
            'max_tokens': config.llm.max_tokens
        }
        
        # 工具映射
        self.tools: Dict[str, Any] = {}
        self.tool_descriptions: Dict[str, str] = {}
        
        # 当前执行状态
        self.current_execution: Optional[AgentExecution] = None
        self.max_steps = getattr(config.agent, 'max_steps', 10)
        self.enable_reflection = getattr(config.agent, 'enable_reflection', True)
        self.enable_thinking = getattr(config.agent, 'enable_thinking', True)
        
        # 初始化工具
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
    
    def new_task(self, task: str) -> AgentExecution:
        """开始新任务"""
        self.logger.info(f"开始新任务: {task}")
        
        # 创建执行记录
        self.current_execution = AgentExecution(
            task=task,
            steps=[],
            total_steps=0
        )
        
        start_time = datetime.now()
        
        try:
            # 执行ReAct循环
            result = self._execute_react_loop(task)
            self.current_execution.final_result = result
            self.current_execution.success = True
            
        except Exception as e:
            self.logger.error(f"任务执行失败: {e}")
            self.current_execution.success = False
            self.current_execution.error = str(e)
            
        finally:
            # 计算执行时间
            end_time = datetime.now()
            self.current_execution.execution_time = (end_time - start_time).total_seconds()
            self.current_execution.total_steps = len(self.current_execution.steps)
            
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
                
                self._add_step(
                    AgentStepType.ACTION,
                    f"使用工具: {action}",
                    tool_name=action,
                    tool_input=action_input,
                    error=error_msg
                )
                
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
                action_input = {"input": input_match.group(1).strip()}
        
        return thought, action, action_input
    
    def _execute_action(self, action: str, action_input: Optional[Dict]) -> Any:
        """执行指定的行动/工具"""
        
        if action not in self.tools:
            raise ValueError(f"未知工具: {action}")
        
        tool = self.tools[action]
        
        # 执行工具
        if hasattr(tool, 'execute'):
            if action_input:
                return tool.execute(**action_input)
            else:
                return tool.execute()
        else:
            # 如果工具是函数
            if action_input:
                return tool(**action_input)
            else:
                return tool()
    
    def _add_step(self, step_type: AgentStepType, content: str, **kwargs):
        """添加执行步骤"""
        step = AgentStep(
            step_type=step_type,
            content=content,
            timestamp=datetime.now(),
            **kwargs
        )
        
        if self.current_execution:
            self.current_execution.steps.append(step)
            
        # 日志记录
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
            # 对字典类型，保留更多信息，特别是success和关键数据
            formatted = json.dumps(output, ensure_ascii=False, indent=2)
            if len(formatted) > 2000:  # 增加到2000字符
                # 如果太长，保留关键信息
                summary = {
                    "success": output.get("success"),
                    "message": output.get("message", ""),
                    "error": output.get("error"),
                }
                # 添加数据摘要
                if "schemas" in output:
                    summary["schemas_count"] = len(output["schemas"])
                if "results" in output:
                    summary["results_count"] = len(output.get("results", []))
                if "data" in output:
                    summary["data_sample"] = output.get("data", [])[:2]  # 只显示前2条
                
                return json.dumps(summary, ensure_ascii=False, indent=2) + "\n[输出已简化，完整信息已保存]"
            return formatted
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
            "execution_time": self.current_execution.execution_time
        }