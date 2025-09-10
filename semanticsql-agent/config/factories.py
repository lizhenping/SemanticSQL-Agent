"""简化的组件管理器 - SemanticSQL Agent核心组件创建
移除过度工程化的工厂模式，采用简单直接的组件创建方式
"""

import logging
from typing import Optional, Dict, Any
from langchain_openai import ChatOpenAI

from config.settings import Settings, get_settings
from utils.memory import Neo4jMemoryManager
from utils.database import DatabaseManager
from models.exceptions import AgentInitializationError

logger = logging.getLogger(__name__)


class ComponentManager:
    """统一的组件管理器 - 简化的组件创建和管理"""
    
    @staticmethod
    def create_llm(settings: Optional[Settings] = None) -> ChatOpenAI:
        """创建LLM实例
        
        Args:
            settings: 配置实例，默认使用全局配置
            
        Returns:
            ChatOpenAI实例
            
        Raises:
            AgentInitializationError: LLM创建失败
        """
        if settings is None:
            settings = get_settings()
            
        logger.info(f"🔧 创建LLM: {settings.llm_model}")
        
        try:
            llm = ChatOpenAI(
                model=settings.llm_model,
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
                timeout=settings.llm_timeout,
                max_retries=settings.llm_max_retries
            )
            logger.info("✅ LLM创建成功")
            return llm
            
        except Exception as e:
            error_msg = f"LLM创建失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            raise AgentInitializationError("LLM", error_msg)


    @staticmethod 
    def create_database_manager(settings: Optional[Settings] = None) -> DatabaseManager:
        """创建数据库管理器
        
        Args:
            settings: 配置实例，默认使用全局配置
            
        Returns:
            DatabaseManager实例
            
        Raises:
            AgentInitializationError: 数据库连接失败
        """
        if settings is None:
            settings = get_settings()
            
        logger.info(f"🔧 创建数据库连接: {settings.db_host}:{settings.db_port}")
        
        try:
            db_manager = DatabaseManager(settings=settings)
            
            # 简单的连接检查
            if not db_manager.initialize():
                raise AgentInitializationError("Database", "数据库初始化失败")
                
            logger.info("✅ 数据库连接成功")
            return db_manager
            
        except Exception as e:
            error_msg = f"数据库连接失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            raise AgentInitializationError("Database", error_msg)


    @staticmethod
    def create_memory_manager(settings: Optional[Settings] = None) -> Neo4jMemoryManager:
        """创建Neo4j记忆管理器
        
        Args:
            settings: 配置实例，默认使用全局配置
            
        Returns:
            Neo4jMemoryManager实例
            
        Raises:
            AgentInitializationError: Neo4j连接失败
        """
        if settings is None:
            settings = get_settings()
            
        logger.info(f"🔧 创建Neo4j连接: {settings.neo4j_uri}")
        
        try:
            memory_manager = Neo4jMemoryManager(settings=settings)
            
            # 简单的连接检查
            if not memory_manager.neo4j_graph:
                raise AgentInitializationError("Neo4j", "连接创建失败")
                
            logger.info("✅ Neo4j连接成功")
            return memory_manager
            
        except Exception as e:
            error_msg = f"Neo4j连接失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            raise AgentInitializationError("Neo4j", error_msg)


    @staticmethod
    def create_all_components(settings: Optional[Settings] = None) -> Dict[str, Any]:
        """创建所有核心组件 - 简化版本
        
        Args:
            settings: 配置实例，默认使用全局配置
            
        Returns:
            包含所有组件的字典: {"llm": ..., "database_manager": ..., "memory_manager": ...}
            
        Raises:
            AgentInitializationError: 任一组件创建失败
        """
        if settings is None:
            settings = get_settings()
            
        logger.info("🚀 开始创建所有核心组件...")
        
        try:
            components = {
                "llm": ComponentManager.create_llm(settings),
                "database_manager": ComponentManager.create_database_manager(settings),
                "memory_manager": ComponentManager.create_memory_manager(settings)
            }
            
            logger.info("🎉 所有核心组件创建成功")
            return components
            
        except Exception as e:
            logger.error(f"❌ 组件创建失败: {e}")
            raise AgentInitializationError("ComponentCreation", str(e))


# 便利函数
def create_llm() -> ChatOpenAI:
    """便利函数：创建LLM实例"""
    return ComponentManager.create_llm()


def create_database_manager() -> DatabaseManager:
    """便利函数：创建数据库管理器"""
    return ComponentManager.create_database_manager()


def create_memory_manager() -> Neo4jMemoryManager:
    """便利函数：创建记忆管理器"""
    return ComponentManager.create_memory_manager()


def create_all_components(settings: Optional[Settings] = None) -> Dict[str, Any]:
    """便利函数：创建所有组件"""
    return ComponentManager.create_all_components(settings)