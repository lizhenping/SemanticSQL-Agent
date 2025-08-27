"""分析工具基类

基于 nl2sql_pipeline 的管道模式，将管道封装为 LangChain 工具。
"""

from tools.base import BaseSemanticSQLTool
from typing import Dict, Any, List, Optional, Type
from abc import abstractmethod
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class PipelineStep:
    """管道步骤基类（简化版）"""
    
    def __init__(self, name: str = None):
        self.name = name or self.__class__.__name__
    
    @abstractmethod
    def execute(self, context: Any) -> Any:
        """执行步骤
        
        Args:
            context: 步骤上下文
            
        Returns:
            更新后的上下文
        """
        pass
    
    def validate(self, context: Any) -> bool:
        """验证步骤输入
        
        Args:
            context: 步骤上下文
            
        Returns:
            是否有效
        """
        return True


class Pipeline:
    """管道类（简化版）"""
    
    def __init__(self, name: str, steps: List[PipelineStep]):
        self.name = name
        self.steps = steps
    
    def execute(self, context: Any) -> Any:
        """执行管道
        
        Args:
            context: 初始上下文
            
        Returns:
            最终上下文
        """
        logger.info(f"开始执行管道: {self.name}")
        
        for i, step in enumerate(self.steps):
            logger.info(f"执行步骤 {i+1}/{len(self.steps)}: {step.name}")
            
            # 验证输入
            if not step.validate(context):
                raise ValueError(f"步骤 {step.name} 输入验证失败")
            
            # 执行步骤
            try:
                context = step.execute(context)
            except Exception as e:
                logger.error(f"步骤 {step.name} 执行失败: {e}")
                raise
        
        logger.info(f"管道 {self.name} 执行完成")
        return context


@dataclass
class BaseAnalysisContext:
    """分析上下文基类"""
    database_name: str
    database_service: Optional[Any] = None
    llm_service: Optional[Any] = None
    
    # 用于存储额外数据
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseAnalysisTool(BaseSemanticSQLTool):
    """分析工具基类
    
    将 nl2sql_pipeline 的管道模式封装为 LangChain 工具。
    """
    
    @abstractmethod
    def create_pipeline(self) -> Pipeline:
        """创建管道
        
        Returns:
            配置好的管道实例
        """
        pass
    
    @abstractmethod
    def create_context(self, **kwargs) -> BaseAnalysisContext:
        """创建上下文
        
        Args:
            **kwargs: 工具输入参数
            
        Returns:
            初始化的上下文
        """
        pass
    
    @abstractmethod
    def format_result(self, context: BaseAnalysisContext) -> Dict[str, Any]:
        """格式化结果
        
        Args:
            context: 执行完成的上下文
            
        Returns:
            格式化的结果
        """
        pass
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """执行分析工具
        
        标准的执行流程：
        1. 创建上下文
        2. 创建管道
        3. 执行管道
        4. 格式化结果
        """
        # 创建上下文
        context = self.create_context(**kwargs)
        
        # 注入服务
        context.database_service = self.db
        context.llm_service = self.llm
        
        # 创建并执行管道
        pipeline = self.create_pipeline()
        context = pipeline.execute(context)
        
        # 格式化结果
        return self.format_result(context)