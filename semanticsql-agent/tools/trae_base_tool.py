"""
trae_agent风格的工具基类
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ToolParameter:
    """工具参数定义"""
    name: str
    type: str  # "string", "integer", "number", "boolean", "object", "array"
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[str]] = None


class TraeBaseTool:
    """trae_agent风格的工具基类"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.logger = logging.getLogger(f"tools.{name}")
    
    @property
    def parameters(self) -> List[ToolParameter]:
        """定义工具参数"""
        return []
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """执行工具"""
        raise NotImplementedError("子类必须实现execute方法")
    
    def format_result(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """格式化成功结果"""
        return {
            "success": True,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
    
    def format_error(self, error: str) -> Dict[str, Any]:
        """格式化错误结果"""
        return {
            "success": False,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_schema(self) -> Dict[str, Any]:
        """获取工具的OpenAI格式schema"""
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


# 向后兼容
BaseTool = TraeBaseTool