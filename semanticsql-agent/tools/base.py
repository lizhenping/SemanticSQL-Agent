"""工具基类（支持 tool calling）"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging
import time

logger = logging.getLogger(__name__)


@dataclass
class ToolParameter:
    """工具参数定义"""
    name: str
    type: str  # "string", "integer", "number", "boolean", "object", "array"
    description: str
    required: bool = True
    enum: Optional[List[str]] = None


@dataclass
class ToolResult:
    """工具执行结果"""
    output: str
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    execution_time: float = 0.0


class Tool(ABC):
    """工具基类（支持 tool calling）"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    @property
    @abstractmethod
    def parameters(self) -> List[ToolParameter]:
        """定义工具参数
        
        Returns:
            参数列表
        """
        pass
    
    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """执行工具
        
        Returns:
            包含结果的字典
        """
        pass
    
    def get_schema(self) -> Dict[str, Any]:
        """获取工具的 OpenAI 格式 schema"""
        properties = {}
        required = []
        
        for param in self.parameters:
            param_schema = {
                "type": param.type,
                "description": param.description
            }
            if param.enum:
                param_schema["enum"] = param.enum
                
            properties[param.name] = param_schema
            
            if param.required:
                required.append(param.name)
        
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }
    
    def run(self, **kwargs) -> ToolResult:
        """运行工具并包装结果"""
        start_time = time.time()
        
        try:
            logger.info(f"执行工具: {self.name}")
            logger.debug(f"参数: {kwargs}")
            
            # 执行工具
            result = self.execute(**kwargs)
            
            # 处理结果
            if isinstance(result, dict):
                output = self._format_dict_output(result)
                metadata = result
            else:
                output = str(result)
                metadata = {"result": result}
            
            execution_time = time.time() - start_time
            logger.info(f"工具 {self.name} 执行成功，耗时: {execution_time:.2f}秒")
            
            return ToolResult(
                output=output,
                metadata=metadata,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"工具 {self.name} 执行失败: {str(e)}", exc_info=True)
            return ToolResult(
                output="",
                error=str(e),
                execution_time=execution_time
            )
    
    def _format_dict_output(self, data: Dict[str, Any]) -> str:
        """格式化字典输出"""
        lines = []
        for key, value in data.items():
            if value is None:
                continue
            if isinstance(value, (list, dict)) and value:
                lines.append(f"{key}: {len(value)} items")
            else:
                lines.append(f"{key}: {value}")
        return "\n".join(lines)