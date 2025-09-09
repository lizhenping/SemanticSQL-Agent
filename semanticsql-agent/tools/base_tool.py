"""
极简工具基类 - SemanticSQL Agent工具系统核心
基于架构设计的完全重构：只有2个核心方法的极简设计
"""

from typing import List, Dict, Any, Optional
import logging
from abc import abstractmethod

from langchain.tools import BaseTool
from pydantic import Field

from models.schemas import SemanticTriple, TripleCollection, create_triple
from utils.memory import Neo4jMemoryManager
from models.exceptions import (
    ToolInitializationError,
    ToolExecutionError, 
    ToolDependencyError,
    raise_tool_error,
    raise_dependency_error
)


class BaseSemanticSQLTool(BaseTool):
    """SemanticSQL工具极简基类 - 只有2个核心方法
    
    设计原则：
    - 极简原则：只提供2个核心方法，去除所有复杂抽象
    - 完全自主：工具在_run()中完全控制执行逻辑、存储时机、返回格式
    - 记忆分片：每个工具通过source_tool管理自己的记忆片段
    - 依赖查询：通过get_memory_by_source_tool()实现工具间依赖
    
    核心方法：
    1. get_memory_by_source_tool() - 唯一的记忆查询方法
    2. add_analysis_triple() - 唯一的三元组添加方法
    
    子类职责：
    - 只需实现_run(input_text: str) -> str方法
    - 在_run()中完全自主处理所有业务逻辑
    - 自主决定何时调用记忆查询和三元组添加
    """
    
    # 工具实例级别的记忆管理器（可选注入）
    memory_manager: Optional[Neo4jMemoryManager] = Field(default=None, exclude=True)
    
    def __init__(self, memory_manager: Optional[Neo4jMemoryManager] = None, **kwargs):
        """
        初始化极简工具
        
        Args:
            memory_manager: Neo4j记忆管理器实例（可选）
            **kwargs: 其他BaseTool参数
        """
        super().__init__(**kwargs)
        # 手动设置私有属性，避免Pydantic验证问题
        object.__setattr__(self, 'memory_manager', memory_manager)
        object.__setattr__(self, '_generated_triples', [])
        object.__setattr__(self, 'logger', logging.getLogger(self.__class__.__name__))
    
    # ========== 核心方法1：记忆查询 ==========
    def get_memory_by_source_tool(self, source_tool: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        获取指定工具生成的记忆三元组 - 唯一的记忆查询方法
        
        这是工具间协作的核心机制：
        - 工具通过此方法查询其他工具的分析结果
        - 基于查询到的记忆进行自己的分析处理
        - 实现工具间的智能依赖关系
        
        Args:
            source_tool: 来源工具名称
            limit: 返回数量限制
            
        Returns:
            三元组字典列表，格式：
            [
                {
                    "subject": "主体",
                    "predicate": "关系",
                    "object": "客体", 
                    "confidence": 0.95,
                    "source_tool": "工具名"
                },
                ...
            ]
        """
        if not self.memory_manager:
            from config.settings import get_settings
            settings = get_settings()
            if settings.fail_fast:
                raise_dependency_error(
                    self.name,
                    "memory_manager",
                    "记忆管理器未配置，请在Agent初始化时提供memory_manager"
                )
            else:
                self.logger.warning(f"⚠️ {self.name}: 记忆管理器未配置，无法查询记忆")
                return []
        
        try:
            results = self.memory_manager.query_by_source_tool(source_tool, limit)
            self.logger.debug(f"🔍 {self.name}: 从 {source_tool} 查询到 {len(results)} 条记忆")
            return results
            
        except Exception as e:
            self.logger.error(f"❌ {self.name}: 查询 {source_tool} 记忆失败: {e}")
            return []
    
    # ========== 核心方法2：三元组添加 ==========
    def add_analysis_triple(self, 
                           subject: str,
                           predicate: str, 
                           object: str,
                           subject_type: str = "Entity",
                           object_type: str = "Entity",
                           confidence: Optional[float] = None) -> None:
        """
        添加分析三元组到当前工具记忆 - 唯一的三元组添加方法
        
        工具通过此方法将分析结果以三元组形式添加到记忆：
        - 三元组会自动标记source_tool为当前工具名称
        - 支持后续工具通过get_memory_by_source_tool()查询
        - 实现记忆的结构化存储和工具间协作
        
        Args:
            subject: 主体实体
            predicate: 关系谓词
            object: 客体实体
            subject_type: 主体类型（默认Entity）
            object_type: 客体类型（默认Entity）
            confidence: 置信度（可选）
        """
        try:
            triple = create_triple(
                subject=subject,
                predicate=predicate,
                object=object,
                source_tool=self.name,
                subject_type=subject_type,
                object_type=object_type,
                confidence=confidence
            )
            
            self._generated_triples.append(triple)
            
            self.logger.debug(f"➕ {self.name}: 添加三元组 ({subject}, {predicate}, {object})")
            
        except Exception as e:
            self.logger.error(f"❌ {self.name}: 添加三元组失败: {e}")
    
    # ========== 子类必须实现的方法 ==========
    @abstractmethod
    def _run(self, input_text: str) -> str:
        """
        工具执行入口 - 子类必须实现的唯一方法
        
        工具的所有业务逻辑都在此方法中实现：
        1. 清空上次执行的三元组缓存
        2. 通过get_memory_by_source_tool()查询依赖工具的记忆
        3. 基于查询到的记忆执行具体的分析/生成/验证逻辑
        4. 通过add_analysis_triple()添加分析结果三元组
        5. 可选择调用_persist_triples()持久化到Neo4j
        6. 返回完全自定义的结果字符串（传给ReAct Observation）
        
        Args:
            input_text: ReAct Agent传入的Action Input文本
            
        Returns:
            工具自定义的执行结果字符串，直接返回给ReAct Observation
        """
        raise NotImplementedError(
            f"工具 {self.__class__.__name__} 必须实现 _run() 方法"
        )
    
    # ========== 内部辅助方法 ==========
    def _clear_generated_triples(self) -> None:
        """清空当前执行生成的三元组 - 工具开始执行时调用"""
        object.__setattr__(self, '_generated_triples', [])
        self.logger.debug(f"🧹 {self.name}: 清空三元组缓存")
    
    def _persist_triples(self) -> bool:
        """
        将生成的三元组持久化到Neo4j - 可选调用
        
        工具可以在_run()方法中选择性调用此方法：
        - 如果需要其他工具查询本工具的结果，则调用
        - 如果是临时处理工具，可以不调用
        
        Returns:
            持久化是否成功
        """
        if not self._generated_triples:
            self.logger.debug(f"📝 {self.name}: 没有三元组需要持久化")
            return True

        # 在fail-fast模式下，强制要求可用的Neo4j连接
        from config.settings import get_settings
        settings = get_settings()
        if settings.fail_fast:
            self._require_neo4j_connection()
        else:
            if not self.memory_manager:
                self.logger.warning(f"⚠️ {self.name}: 记忆管理器未配置，无法持久化")
                return False
        
        try:
            success = self.memory_manager.store_triples(self._generated_triples, self.name)
            if success:
                self.logger.info(f"💾 {self.name}: 成功持久化 {len(self._generated_triples)} 个三元组")
            return success
            
        except Exception as e:
            self.logger.error(f"❌ {self.name}: 持久化三元组失败: {e}")
            return False
    
    def _get_generated_triples(self) -> List[SemanticTriple]:
        """获取当前执行生成的三元组列表"""
        return self._generated_triples.copy()
    
    def _create_triple_collection(self, summary: str = "") -> TripleCollection:
        """创建三元组集合，用于结构化返回结果"""
        return TripleCollection(
            triples=self._generated_triples.copy(),
            source_tool=self.name,
            summary=summary or f"{self.name} 执行结果"
        )

    # ========== 统一依赖校验：Neo4j连接 ==========
    def _require_neo4j_connection(self) -> None:
        """在fail-fast模式下强制校验Neo4j连接，避免绕过图存储。

        Raises:
            ToolDependencyError: 当记忆管理器缺失或连接不可用时抛出
        """
        if not self.memory_manager:
            raise_tool_error(self.name, "Neo4j记忆管理器未注入，初始化阶段应该验证连接")
        if not hasattr(self.memory_manager, 'neo4j_graph') or self.memory_manager.neo4j_graph is None:
            raise_tool_error(self.name, "Neo4j连接失败，请检查配置并在启动时解决连接问题")
    
    # ========== 工具状态检查方法 ==========
    def _check_dependencies(self, required_tools: List[str]) -> bool:
        """
        检查工具依赖是否满足
        
        Args:
            required_tools: 依赖的工具列表
            
        Returns:
            依赖是否都满足
            
        Raises:
            ToolDependencyError: 如果有依赖缺失
        """
        missing_tools = []
        
        for tool_name in required_tools:
            memory = self.get_memory_by_source_tool(tool_name, 1)
            if not memory:
                missing_tools.append(tool_name)
        
        if missing_tools:
            raise_dependency_error(
                self.name,
                missing_tools[0],  # 报告第一个缺失的工具
                "分析结果"
            )
        
        return True
    
    def _validate_input(self, input_text: str) -> bool:
        """
        验证输入参数
        
        Args:
            input_text: 输入文本
            
        Returns:
            输入是否有效
            
        Raises:
            ToolExecutionError: 如果输入无效
        """
        if not input_text or not input_text.strip():
            raise_tool_error(self.name, "输入文本不能为空")
        
        return True
    
    def _log_execution_start(self, input_text: str) -> None:
        """记录工具开始执行"""
        self.logger.info(f"🔧 {self.name}: 开始执行 - 输入: {input_text[:100]}...")
    
    def _log_execution_end(self, result_summary: str) -> None:
        """记录工具执行完成"""
        triple_count = len(self._generated_triples)
        self.logger.info(f"✅ {self.name}: 执行完成 - 生成 {triple_count} 个三元组 - {result_summary}")
    
    # ========== 便利方法 ==========
    def has_memory_manager(self) -> bool:
        """检查是否配置了记忆管理器"""
        return self.memory_manager is not None
    
    def get_tool_info(self) -> Dict[str, Any]:
        """获取工具信息"""
        return {
            "name": self.name,
            "description": self.description,
            "has_memory_manager": self.has_memory_manager(),
            "generated_triples_count": len(self._generated_triples)
        }


# ========== 便利函数 ==========
def create_tool_with_memory(tool_class, 
                           memory_manager: Neo4jMemoryManager,
                           **tool_kwargs) -> BaseSemanticSQLTool:
    """
    创建带记忆管理器的工具实例
    
    Args:
        tool_class: 工具类
        memory_manager: 记忆管理器
        **tool_kwargs: 工具构造参数
        
    Returns:
        配置好的工具实例
    """
    try:
        tool = tool_class(memory_manager=memory_manager, **tool_kwargs)
        logging.getLogger(__name__).info(f"✅ 创建工具 {tool_class.__name__} 成功")
        return tool
        
    except Exception as e:
        logging.getLogger(__name__).error(f"❌ 创建工具 {tool_class.__name__} 失败: {e}")
        raise ToolInitializationError(tool_class.__name__, str(e))


def batch_create_tools(tool_configs: List[Dict[str, Any]], 
                      memory_manager: Neo4jMemoryManager) -> List[BaseSemanticSQLTool]:
    """
    批量创建工具实例
    
    Args:
        tool_configs: 工具配置列表，格式：[{"class": ToolClass, "kwargs": {...}}, ...]
        memory_manager: 记忆管理器
        
    Returns:
        工具实例列表
    """
    tools = []
    
    for config in tool_configs:
        tool_class = config["class"]
        tool_kwargs = config.get("kwargs", {})
        
        try:
            tool = create_tool_with_memory(tool_class, memory_manager, **tool_kwargs)
            tools.append(tool)
        except Exception as e:
            from config.settings import get_settings
            settings = get_settings()
            if settings.fail_fast:
                logging.getLogger(__name__).error(f"❌ 工具创建失败: {tool_class.__name__}: {e}")
                raise ToolInitializationError(tool_class.__name__, str(e))
            else:
                logging.getLogger(__name__).warning(f"⚠️ 跳过工具 {tool_class.__name__}: {e}")
    
    logging.getLogger(__name__).info(f"📦 批量创建完成: {len(tools)} 个工具")
    return tools
