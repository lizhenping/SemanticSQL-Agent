"""管道模式基础类

本模块定义了Pipeline设计模式的基础类：
- PipelineStep: 管道步骤的抽象基类
- Pipeline: 管道的基类，用于组织和执行一系列步骤
- PipelineContext: 管道上下文，用于在步骤间传递数据

设计模式：
- 使用泛型支持类型安全的上下文传递
- 支持步骤的验证和错误处理
- 提供灵活的步骤组合能力
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, TypeVar, Generic
import logging
from dataclasses import dataclass, field


logger = logging.getLogger(__name__)

# 上下文类型变量，用于泛型支持
T = TypeVar('T')


@dataclass
class PipelineContext:
    """管道上下文
    
    用于在管道步骤之间传递数据的通用容器。
    可以存储任意数据，支持动态属性访问。
    """
    # 预定义的常用属性
    database_name: str = ""
    schema: Any = None
    domain_knowledge: Any = None
    field_classifications: Dict[str, Any] = field(default_factory=dict)
    column_descriptions: Dict[str, Any] = field(default_factory=dict)
    table_descriptions: Dict[str, Any] = field(default_factory=dict)
    er_relations: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 用于存储动态属性
    _extra: Dict[str, Any] = field(default_factory=dict)
    
    def __setattr__(self, name: str, value: Any):
        """支持动态属性设置"""
        if name.startswith('_') or name in self.__dataclass_fields__:
            super().__setattr__(name, value)
        else:
            if '_extra' not in self.__dict__:
                super().__setattr__('_extra', {})
            self._extra[name] = value
    
    def __getattr__(self, name: str):
        """支持动态属性访问"""
        if name in self._extra:
            return self._extra[name]
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
    
    def get(self, key: str, default: Any = None) -> Any:
        """字典风格的安全访问"""
        if hasattr(self, key):
            return getattr(self, key)
        return self._extra.get(key, default)
    
    def update(self, **kwargs):
        """批量更新属性"""
        for key, value in kwargs.items():
            setattr(self, key, value)


class PipelineStep(ABC, Generic[T]):
    """管道步骤抽象基类
    
    每个具体的管道步骤都应该继承此类并实现execute方法。
    支持泛型，确保类型安全的上下文传递。
    
    属性:
        name: 步骤名称，用于日志和调试
    """
    
    def __init__(self, name: str = None):
        """初始化管道步骤
        
        参数:
            name: 步骤名称，如果不提供则使用类名
        """
        self.name = name or self.__class__.__name__
    
    @abstractmethod
    def execute(self, context: T) -> T:
        """执行管道步骤
        
        这是每个步骤必须实现的核心方法。
        
        参数:
            context: 管道上下文，包含步骤执行所需的所有数据
            
        返回:
            更新后的上下文
            
        异常:
            可能抛出各种业务异常，由Pipeline统一处理
        """
        pass
    
    def validate_input(self, context: T) -> bool:
        """验证输入上下文
        
        在执行步骤前验证上下文是否满足要求。
        子类可以重写此方法实现具体的验证逻辑。
        
        参数:
            context: 待验证的上下文
            
        返回:
            True表示验证通过，False表示验证失败
        """
        return True


class Pipeline(Generic[T]):
    """管道基类
    
    管道是一系列步骤的有序集合，按顺序执行每个步骤。
    支持泛型，确保整个管道使用一致的上下文类型。
    
    属性:
        name: 管道名称
        steps: 管道步骤列表
    """
    
    def __init__(self, name: str = None, steps: List[PipelineStep[T]] = None):
        """初始化管道
        
        参数:
            name: 管道名称，用于日志和标识
            steps: 初始步骤列表
        """
        self.name = name or self.__class__.__name__
        self.steps: List[PipelineStep[T]] = steps or []
    
    def add_step(self, step: PipelineStep[T]) -> 'Pipeline[T]':
        """添加步骤到管道
        
        支持链式调用，方便构建管道。
        
        参数:
            step: 要添加的管道步骤
            
        返回:
            当前管道实例，支持链式调用
        """
        self.steps.append(step)
        logger.debug(f"向管道 '{self.name}' 添加步骤 '{step.name}'")
        return self
    
    def run(self, initial_context: T) -> T:
        """运行管道（类型安全版本）
        
        按顺序执行所有步骤，每个步骤的输出作为下一个步骤的输入。
        
        参数:
            initial_context: 初始上下文
            
        返回:
            经过所有步骤处理后的最终上下文
            
        异常:
            ValueError: 当步骤输入验证失败时
            其他异常: 步骤执行过程中的业务异常
        """
        logger.info(f"开始执行管道 '{self.name}'，共 {len(self.steps)} 个步骤")
        
        context = initial_context
        
        for i, step in enumerate(self.steps, 1):
            logger.debug(f"执行步骤 {i}/{len(self.steps)}: '{step.name}'")
            
            # 验证输入
            if not step.validate_input(context):
                raise ValueError(f"步骤 '{step.name}' 的输入验证失败")
            
            try:
                # 执行步骤
                context = step.execute(context)
                logger.debug(f"步骤 '{step.name}' 执行完成")
            except Exception as e:
                logger.error(f"步骤 '{step.name}' 执行失败: {str(e)}")
                raise
        
        logger.info(f"管道 '{self.name}' 执行完成")
        return context
    
    def execute(self, initial_context: Any) -> Any:
        """执行管道（兼容字典上下文的遗留方法）
        
        为了向后兼容，保留此方法支持字典类型的上下文。
        
        参数:
            initial_context: 初始上下文字典
            
        返回:
            处理后的上下文字典
        """
        # 如果是字典，转换为PipelineContext
        if isinstance(initial_context, dict):
            context = PipelineContext(**initial_context)
            result = self.run(context)
            # 如果需要，可以转回字典
            if hasattr(result, '__dict__'):
                return {k: v for k, v in result.__dict__.items() if not k.startswith('_')}
            return result
        else:
            # 直接调用run方法
            return self.run(initial_context)
    
    def get_step_names(self) -> List[str]:
        """获取所有步骤的名称列表
        
        用于调试和日志记录。
        
        返回:
            步骤名称列表
        """
        return [step.name for step in self.steps]