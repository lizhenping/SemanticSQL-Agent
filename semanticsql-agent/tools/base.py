"""工具基类（简化版，参考 TRAEAgent）"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
import logging
import time

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """工具执行结果"""
    output: str
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class Tool(ABC):
    """简化的工具基类"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """执行工具
        
        Returns:
            包含结果的字典
        """
        pass
    
    def run(self, **kwargs) -> ToolResult:
        """运行工具并包装结果"""
        start_time = time.time()
        
        try:
            logger.info(f"执行工具: {self.name}")
            
            # 执行工具
            result = self.execute(**kwargs)
            
            # 处理结果
            if isinstance(result, dict):
                output = self._format_dict_output(result)
            else:
                output = str(result)
            
            execution_time = time.time() - start_time
            logger.info(f"工具 {self.name} 执行成功，耗时: {execution_time:.2f}秒")
            
            return ToolResult(
                output=output,
                metadata={"execution_time": execution_time}
            )
            
        except Exception as e:
            logger.error(f"工具 {self.name} 执行失败: {str(e)}")
            return ToolResult(
                output="",
                error=str(e)
            )
    
    def _format_dict_output(self, data: Dict[str, Any]) -> str:
        """简单的字典格式化"""
        lines = []
        for key, value in data.items():
            if value is None:
                continue
            if isinstance(value, (list, dict)) and value:
                lines.append(f"{key}: {len(value)} items")
            else:
                lines.append(f"{key}: {value}")
        return "\n".join(lines)


class SemanticSQLTool(Tool):
    """SQL 工具基类，添加数据库和 LLM 支持"""
    
    def __init__(self, name: str, description: str, db=None, llm=None):
        super().__init__(name, description)
        self.db = db
        self.llm = llm