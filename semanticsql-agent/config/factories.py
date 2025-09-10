"""组件管理器 - 按需创建SemanticSQL Agent组件
遵循KISS原则，简单直接的组件创建
"""

import logging
from typing import Optional
from langchain_openai import ChatOpenAI

from config.settings import Settings, get_settings
from utils.memory import Neo4jMemoryManager
from utils.database import DatabaseManager

logger = logging.getLogger(__name__)


class ComponentManager:
    """组件管理器 - 按需创建组件"""
    
    @staticmethod
    def create_llm(settings: Optional[Settings] = None) -> ChatOpenAI:
        """创建LLM实例 - 必需组件
        
        Args:
            settings: 配置实例，默认使用全局配置
            
        Returns:
            ChatOpenAI实例
        """
        if settings is None:
            settings = get_settings()
            
        logger.info(f"Creating LLM: {settings.llm_model}")
        
        llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            timeout=settings.llm_timeout,
            max_retries=settings.llm_max_retries
        )
        return llm


    @staticmethod 
    def create_database_manager(settings: Optional[Settings] = None) -> Optional[DatabaseManager]:
        """创建数据库管理器 - 可选组件
        
        Args:
            settings: 配置实例，默认使用全局配置
            
        Returns:
            DatabaseManager实例，失败返回None
        """
        if settings is None:
            settings = get_settings()
            
        # 检查是否配置了数据库
        if not settings.db_host or settings.db_host == "none":
            logger.info("Database not configured, skipping")
            return None
            
        logger.info(f"Creating database connection: {settings.db_host}:{settings.db_port}")
        
        try:
            db_manager = DatabaseManager(settings=settings)
            db_manager.initialize()  # 尝试初始化，失败会抛出异常
            return db_manager
        except Exception as e:
            logger.warning(f"Database connection failed: {e}")
            return None


    @staticmethod
    def create_memory_manager(settings: Optional[Settings] = None) -> Optional[Neo4jMemoryManager]:
        """创建Neo4j记忆管理器 - 可选组件
        
        Args:
            settings: 配置实例，默认使用全局配置
            
        Returns:
            Neo4jMemoryManager实例，失败返回None
        """
        if settings is None:
            settings = get_settings()
            
        # 检查是否配置了Neo4j
        if not settings.neo4j_uri or settings.neo4j_uri == "none":
            logger.info("Neo4j not configured, skipping")
            return None
            
        logger.info(f"Creating Neo4j connection: {settings.neo4j_uri}")
        
        try:
            memory_manager = Neo4jMemoryManager(settings=settings)
            return memory_manager
        except Exception as e:
            logger.warning(f"Neo4j connection failed: {e}")
            return None


