"""工具基类"""

from langchain.tools import BaseTool
from pydantic import Field
from typing import Any, Type, Optional
from abc import abstractmethod
import logging
import time

logger = logging.getLogger(__name__)


class BaseSemanticSQLTool(BaseTool):
    """SemanticSQL 工具基类"""
    
    # 共享资源
    db: Any = Field(default=None, exclude=True)
    llm: Any = Field(default=None, exclude=True)
    
    def _run(self, *args, **kwargs) -> str:
        """执行工具（同步）"""
        start_time = time.time()
        tool_name = self.name
        
        try:
            logger.info(f"执行工具: {tool_name}")
            logger.debug(f"输入参数: {kwargs}")
            
            # 执行具体逻辑
            result = self.execute(**kwargs)
            
            # 记录执行时间
            execution_time = time.time() - start_time
            logger.info(f"工具 {tool_name} 执行成功，耗时: {execution_time:.2f}秒")
            
            # 格式化输出
            return self._format_output(result)
            
        except Exception as e:
            logger.error(f"工具 {tool_name} 执行失败: {str(e)}", exc_info=True)
            raise e  # 直接抛出异常，不做降级处理
    
    async def _arun(self, *args, **kwargs) -> str:
        """异步执行（不实现）"""
        return self._run(*args, **kwargs)
    
    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """具体执行逻辑（子类实现）"""
        pass
    
    def _format_output(self, result: Any) -> str:
        """格式化输出结果"""
        if isinstance(result, str):
            return result
        elif isinstance(result, dict):
            return self._format_dict(result)
        elif isinstance(result, list):
            return self._format_list(result)
        else:
            return str(result)
    
    def _format_dict(self, d: Dict[str, Any], indent: int = 0) -> str:
        """格式化字典输出"""
        lines = []
        prefix = "  " * indent
        
        for key, value in d.items():
            if isinstance(value, dict):
                lines.append(f"{prefix}{key}:")
                lines.append(self._format_dict(value, indent + 1))
            elif isinstance(value, list):
                if len(value) == 0:
                    lines.append(f"{prefix}{key}: []")
                elif len(value) <= 3:
                    lines.append(f"{prefix}{key}: {value}")
                else:
                    lines.append(f"{prefix}{key}: [{value[0]}, {value[1]}, ... ({len(value)} items)]")
            else:
                lines.append(f"{prefix}{key}: {value}")
        
        return "\n".join(lines)
    
    def _format_list(self, lst: List[Any]) -> str:
        """格式化列表输出"""
        if not lst:
            return "[]"
        elif len(lst) <= 5:
            return "\n".join(f"- {item}" for item in lst)
        else:
            items = [f"- {item}" for item in lst[:3]]
            items.append(f"... 还有 {len(lst) - 3} 项")
            return "\n".join(items)