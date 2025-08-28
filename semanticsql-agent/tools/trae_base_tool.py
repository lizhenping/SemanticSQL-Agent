"""
trae_agent风格的工具系统基类
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ToolParameter:
    """工具参数定义"""
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[str]] = None
    
    def to_schema(self) -> Dict[str, Any]:
        """转换为JSON schema格式"""
        schema = {
            "type": self.type,
            "description": self.description
        }
        
        if self.enum:
            schema["enum"] = self.enum
        
        if self.default is not None:
            schema["default"] = self.default
        
        return schema


class TraeBaseTool(ABC):
    """trae_agent风格的基础工具类"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.logger = logging.getLogger(f"tools.{name}")
    
    @property
    @abstractmethod
    def parameters(self) -> List[ToolParameter]:
        """定义工具参数"""
        pass
    
    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """执行工具逻辑"""
        pass
    
    def get_schema(self) -> Dict[str, Any]:
        """获取OpenAI函数调用schema"""
        properties = {}
        required = []
        
        for param in self.parameters:
            properties[param.name] = param.to_schema()
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
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """验证参数"""
        try:
            # 检查必需参数
            for param in self.parameters:
                if param.required and param.name not in parameters:
                    return False, f"缺少必需参数: {param.name}"
            
            # 检查参数类型
            for param_name, param_value in parameters.items():
                param_def = next((p for p in self.parameters if p.name == param_name), None)
                if not param_def:
                    return False, f"未知参数: {param_name}"
                
                # 类型检查
                if param_def.type == "string" and not isinstance(param_value, str):
                    return False, f"参数 {param_name} 必须是字符串"
                elif param_def.type == "integer" and not isinstance(param_value, int):
                    return False, f"参数 {param_name} 必须是整数"
                elif param_def.type == "number" and not isinstance(param_value, (int, float)):
                    return False, f"参数 {param_name} 必须是数字"
                elif param_def.type == "boolean" and not isinstance(param_value, bool):
                    return False, f"参数 {param_name} 必须是布尔值"
                elif param_def.type == "array" and not isinstance(param_value, list):
                    return False, f"参数 {param_name} 必须是数组"
                elif param_def.type == "object" and not isinstance(param_value, dict):
                    return False, f"参数 {param_name} 必须是对象"
                
                # 枚举值检查
                if param_def.enum and param_value not in param_def.enum:
                    return False, f"参数 {param_name} 必须是以下值之一: {param_def.enum}"
            
            return True, None
            
        except Exception as e:
            return False, str(e)
    
    def format_result(self, result: Any) -> Dict[str, Any]:
        """格式化结果"""
        return {
            "success": True,
            "data": result,
            "tool": self.name,
            "timestamp": self._get_timestamp()
        }
    
    def format_error(self, error: str) -> Dict[str, Any]:
        """格式化错误"""
        return {
            "success": False,
            "error": error,
            "tool": self.name,
            "timestamp": self._get_timestamp()
        }
    
    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()


class ToolRegistry:
    """工具注册器"""
    
    def __init__(self):
        self.tools: Dict[str, TraeBaseTool] = {}
        self.logger = logging.getLogger("tools.registry")
    
    def register(self, tool: TraeBaseTool) -> None:
        """注册工具"""
        if tool.name in self.tools:
            self.logger.warning(f"工具 {tool.name} 已存在，将被覆盖")
        
        self.tools[tool.name] = tool
        self.logger.info(f"已注册工具: {tool.name}")
    
    def get(self, name: str) -> Optional[TraeBaseTool]:
        """获取工具"""
        return self.tools.get(name)
    
    def list_tools(self) -> List[str]:
        """列出所有工具"""
        return list(self.tools.keys())
    
    def get_schemas(self) -> List[Dict[str, Any]]:
        """获取所有工具的schema"""
        return [tool.get_schema() for tool in self.tools.values()]
    
    def create_tool(self, name: str, **kwargs) -> Optional[TraeBaseTool]:
        """根据配置创建工具实例"""
        if name not in self.tools:
            return None
        
        # 这里可以根据需要创建工具的新实例
        # 实际实现需要根据具体工具类
        return self.tools[name]


# 全局工具注册器
_tool_registry = ToolRegistry()

def register_tool(tool: TraeBaseTool) -> None:
    """全局注册工具"""
    _tool_registry.register(tool)

def get_tool(name: str) -> Optional[TraeBaseTool]:
    """全局获取工具"""
    return _tool_registry.get(name)

def list_tools() -> List[str]:
    """全局列出工具"""
    return _tool_registry.list_tools()

def get_all_schemas() -> List[Dict[str, Any]]:
    """全局获取所有工具schema"""
    return _tool_registry.get_schemas()