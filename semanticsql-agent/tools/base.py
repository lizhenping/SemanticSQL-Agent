"""工具基类

参考 TRAEAgent 的工具设计，提供标准化的工具接口。
"""

from abc import ABC, abstractmethod
from typing import Any, Type, Optional, Dict, List, Union
from dataclasses import dataclass
import logging
import time
import asyncio
import json

from langchain.tools import BaseTool
from langchain_core.tools import ToolException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# 工具相关的类型定义（与 agent_basics.py 兼容）
ToolCallArguments = Dict[str, Union[str, int, float, Dict[str, Any], List[Any], None]]


@dataclass
class ToolExecResult:
    """工具执行的中间结果"""
    output: Optional[str] = None
    error: Optional[str] = None
    error_code: int = 0
    execution_time: float = 0.0
    metadata: Optional[Dict[str, Any]] = None


class ToolParameter(BaseModel):
    """工具参数定义"""
    name: str
    type: Union[str, List[str]]
    description: str
    enum: Optional[List[str]] = None
    items: Optional[Dict[str, Any]] = None
    required: bool = True


class BaseSemanticSQLTool(BaseTool, ABC):
    """SemanticSQL 工具基类
    
    参考 TRAEAgent 的工具设计，提供：
    1. 标准化的执行接口
    2. 自动的错误处理
    3. 执行时间统计
    4. 结构化的输出
    """
    
    # 工具元数据
    name: str = Field(..., description="工具名称")
    description: str = Field(..., description="工具描述")
    
    # 共享资源（可选）
    db: Optional[Any] = Field(default=None, exclude=True)
    llm: Optional[Any] = Field(default=None, exclude=True)
    prompt_manager: Optional[Any] = Field(default=None, exclude=True)
    
    # 模型提供商（用于工具特定的优化）
    model_provider: Optional[str] = Field(default=None, exclude=True)
    
    class Config:
        """Pydantic 配置"""
        arbitrary_types_allowed = True
    
    def __init__(self, **data):
        """初始化工具"""
        super().__init__(**data)
        self._init_tool()
    
    def _init_tool(self) -> None:
        """初始化工具（子类可重写）"""
        pass
    
    def get_parameters(self) -> List[ToolParameter]:
        """获取工具参数定义
        
        子类应该重写此方法以提供参数定义。
        
        Returns:
            参数列表
        """
        return []
    
    def _run(self, *args, **kwargs) -> str:
        """执行工具（同步）- LangChain 接口
        
        Returns:
            工具执行结果的字符串表示
        """
        try:
            # 记录开始
            start_time = time.time()
            logger.info(f"执行工具: {self.name}")
            logger.debug(f"输入参数: {kwargs}")
            
            # 验证参数
            self._validate_args(**kwargs)
            
            # 执行工具
            exec_result = self.execute(**kwargs)
            
            # 计算执行时间
            execution_time = time.time() - start_time
            
            # 包装结果
            if isinstance(exec_result, ToolExecResult):
                exec_result.execution_time = execution_time
                result = exec_result
            else:
                # 如果返回的不是 ToolExecResult，包装它
                result = ToolExecResult(
                    output=str(exec_result),
                    execution_time=execution_time
                )
            
            if result.error:
                logger.error(f"工具 {self.name} 执行出错: {result.error}")
                raise ToolException(result.error)
            
            logger.info(f"工具 {self.name} 执行成功，耗时: {execution_time:.2f}秒")
            
            # 格式化输出
            return self._format_result(result)
            
        except ToolException:
            # 直接传递工具异常
            raise
        except Exception as e:
            logger.error(f"工具 {self.name} 执行失败: {str(e)}", exc_info=True)
            raise ToolException(f"工具执行失败: {str(e)}")
    
    async def _arun(self, *args, **kwargs) -> str:
        """异步执行 - LangChain 接口
        
        默认实现：在线程池中运行同步方法。
        子类可以重写以提供真正的异步实现。
        """
        return await asyncio.get_event_loop().run_in_executor(
            None, self._run, *args, **kwargs
        )
    
    def _validate_args(self, **kwargs) -> None:
        """验证输入参数
        
        子类可以重写此方法以添加参数验证。
        
        Args:
            **kwargs: 输入参数
            
        Raises:
            ToolException: 参数验证失败
        """
        # 获取参数定义
        parameters = self.get_parameters()
        
        # 检查必需参数
        for param in parameters:
            if param.required and param.name not in kwargs:
                raise ToolException(f"缺少必需参数: {param.name}")
    
    @abstractmethod
    def execute(self, **kwargs) -> Union[ToolExecResult, Any]:
        """执行工具的具体逻辑
        
        子类必须实现此方法。
        
        Args:
            **kwargs: 工具参数
            
        Returns:
            ToolExecResult 或任意结果（会被自动包装）
        """
        pass
    
    def _format_result(self, result: ToolExecResult) -> str:
        """格式化工具执行结果
        
        Args:
            result: 工具执行结果
            
        Returns:
            格式化的字符串
        """
        if result.output:
            return self._format_output(result.output)
        else:
            return "执行完成（无输出）"
    
    def _format_output(self, output: Any) -> str:
        """格式化输出内容
        
        Args:
            output: 输出内容
            
        Returns:
            格式化的字符串
        """
        if isinstance(output, str):
            return output
        elif isinstance(output, dict):
            return self._format_dict(output)
        elif isinstance(output, list):
            return self._format_list(output)
        elif hasattr(output, 'dict'):
            # Pydantic 模型
            return self._format_dict(output.dict())
        elif hasattr(output, '__dict__'):
            # 普通对象
            return self._format_dict(output.__dict__)
        else:
            return str(output)
    
    def _format_dict(self, d: Dict[str, Any], indent: int = 0) -> str:
        """格式化字典输出"""
        lines = []
        prefix = "  " * indent
        
        for key, value in d.items():
            if value is None:
                continue  # 跳过 None 值
            
            if isinstance(value, dict):
                lines.append(f"{prefix}{key}:")
                lines.append(self._format_dict(value, indent + 1))
            elif isinstance(value, list):
                if len(value) == 0:
                    lines.append(f"{prefix}{key}: []")
                elif len(value) <= 3:
                    formatted_items = [self._format_item(item) for item in value]
                    lines.append(f"{prefix}{key}: [{', '.join(formatted_items)}]")
                else:
                    lines.append(f"{prefix}{key}: [")
                    for i, item in enumerate(value[:2]):
                        lines.append(f"{prefix}  - {self._format_item(item)}")
                    lines.append(f"{prefix}  ... 还有 {len(value) - 2} 项")
                    lines.append(f"{prefix}]")
            else:
                lines.append(f"{prefix}{key}: {self._format_item(value)}")
        
        return "\n".join(lines)
    
    def _format_list(self, lst: List[Any]) -> str:
        """格式化列表输出"""
        if not lst:
            return "[]"
        
        lines = []
        if len(lst) <= 5:
            for item in lst:
                lines.append(f"- {self._format_item(item)}")
        else:
            for item in lst[:3]:
                lines.append(f"- {self._format_item(item)}")
            lines.append(f"... 还有 {len(lst) - 3} 项")
        
        return "\n".join(lines)
    
    def _format_item(self, item: Any) -> str:
        """格式化单个项目"""
        if isinstance(item, (str, int, float, bool)):
            return str(item)
        elif isinstance(item, dict):
            # 简化字典显示
            return f"{{{', '.join(f'{k}: {v}' for k, v in list(item.items())[:2])}...}}"
        elif isinstance(item, list):
            return f"[{len(item)} items]"
        else:
            return str(item)[:50] + "..." if len(str(item)) > 50 else str(item)


# 向后兼容的类型定义
ToolCall = ToolCallArguments  # 简化的别名
ToolResult = ToolExecResult   # 简化的别名