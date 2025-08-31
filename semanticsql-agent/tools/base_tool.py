"""
工具基类 - 所有工具的基础类
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import json
import logging
from datetime import datetime

from models.exceptions import ToolExecutionError


@dataclass
class ToolParameter:
    """工具参数定义"""
    name: str
    type: str  # "string", "integer", "number", "boolean", "object", "array"
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[str]] = None


class BaseTool(ABC):
    """工具基类 - 符合架构规范"""
    
    def __init__(self, config: Any = None):
        """
        初始化工具
        
        Args:
            config: 配置对象
        """
        self.config = config
        self.logger = logging.getLogger(f"tools.{self.name}")
        self._execution_count = 0
        self._error_count = 0
        self._total_duration_ms = 0
    
    @property
    @abstractmethod
    def name(self) -> str:
        """工具唯一标识，用于注册和调用"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """工具功能描述，用于LLM理解"""
        pass
    
    @property
    def category(self) -> str:
        """工具类别：analysis/generation/validation/reflection"""
        return "general"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        """定义工具参数"""
        return []
    
    @abstractmethod
    def _execute(self, **kwargs) -> Any:
        """
        实际执行逻辑，子类必须实现
        
        Returns:
            执行结果数据
        """
        pass
    
    def run(self, **kwargs) -> Dict[str, Any]:
        """
        工具执行接口 - 标准化返回格式
        
        Returns:
            {
                "success": bool,      # 执行是否成功
                "data": Any,         # 成功时的返回数据
                "error": str,        # 失败时的错误信息
                "metadata": dict     # 可选的元数据
            }
        """
        start_time = datetime.now()
        self._execution_count += 1
        
        try:
            # 验证参数
            self._validate_parameters(kwargs)
            
            # 执行工具
            self.logger.debug(f"Executing {self.name} with params: {kwargs}")
            result = self._execute(**kwargs)
            
            # 计算执行时间
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            self._total_duration_ms += duration_ms
            
            # 返回成功结果
            return {
                "success": True,
                "data": result,
                "error": None,
                "metadata": {
                    "tool_name": self.name,
                    "duration_ms": duration_ms,
                    "timestamp": datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            # 记录错误
            self._error_count += 1
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            self.logger.error(f"Tool {self.name} execution failed: {str(e)}")
            
            # 返回错误结果
            return {
                "success": False,
                "data": None,
                "error": str(e),
                "metadata": {
                    "tool_name": self.name,
                    "duration_ms": duration_ms,
                    "timestamp": datetime.now().isoformat(),
                    "error_type": type(e).__name__
                }
            }
    
    def _validate_parameters(self, kwargs: Dict[str, Any]):
        """验证参数"""
        # 检查必需参数
        for param in self.parameters:
            if param.required and param.name not in kwargs:
                if param.default is not None:
                    kwargs[param.name] = param.default
                else:
                    raise ValueError(f"Missing required parameter: {param.name}")
            
            # 检查枚举值
            if param.enum and param.name in kwargs:
                if kwargs[param.name] not in param.enum:
                    raise ValueError(
                        f"Invalid value for {param.name}: {kwargs[param.name]}. "
                        f"Must be one of {param.enum}"
                    )
    
    def get_schema(self) -> Dict[str, Any]:
        """获取工具的OpenAI Function Calling格式schema"""
        properties = {}
        required = []
        
        for param in self.parameters:
            param_schema = {
                "type": param.type,
                "description": param.description
            }
            if param.enum:
                param_schema["enum"] = param.enum
            if param.default is not None:
                param_schema["default"] = param.default
                
            properties[param.name] = param_schema
            
            if param.required:
                required.append(param.name)
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取工具执行统计"""
        return {
            "name": self.name,
            "category": self.category,
            "execution_count": self._execution_count,
            "error_count": self._error_count,
            "success_rate": (
                (self._execution_count - self._error_count) / self._execution_count 
                if self._execution_count > 0 else 0
            ),
            "avg_duration_ms": (
                self._total_duration_ms / self._execution_count
                if self._execution_count > 0 else 0
            )
        }
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行工具的公共接口 - run方法的别名
        
        Returns:
            {
                "success": bool,
                "data": Any,
                "error": Optional[str],
                "metadata": Optional[Dict]
            }
        """
        return self.run(**kwargs)
    
    def reset_stats(self):
        """重置统计信息"""
        self._execution_count = 0
        self._error_count = 0
        self._total_duration_ms = 0
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"{self.name} ({self.category}): {self.description}"
    
    def __repr__(self) -> str:
        """详细表示"""
        return f"<{self.__class__.__name__} name='{self.name}' category='{self.category}'>"