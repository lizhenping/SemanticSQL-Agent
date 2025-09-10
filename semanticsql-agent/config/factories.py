"""
统一配置工厂 - SemanticSQL Agent核心配置管理
实现fail-fast原则，所有组件创建时强制验证连接
"""

import logging
from typing import Optional, Dict, Any
from langchain_openai import ChatOpenAI

from config.settings import Settings, get_settings
from utils.memory import Neo4jMemoryManager
from utils.database import DatabaseManager
from models.exceptions import (
    AgentInitializationError, 
    DatabaseConnectionError,
    MemoryConnectionError
)

logger = logging.getLogger(__name__)


class LLMFactory:
    """LLM工厂 - 基于统一配置创建和验证LLM实例"""
    
    @staticmethod
    def create_llm(settings: Optional[Settings] = None) -> ChatOpenAI:
        """创建LLM实例并进行健康检查
        
        Args:
            settings: 配置实例，默认使用全局配置
            
        Returns:
            验证通过的ChatOpenAI实例
            
        Raises:
            AgentInitializationError: LLM创建或验证失败
        """
        if settings is None:
            settings = get_settings()
            
        logger.info(f"🔧 创建LLM: {settings.llm_model}")
        
        # 验证必需配置 - 遵循fail_fast策略
        if settings.fail_fast:
            if not settings.llm_model:
                raise AgentInitializationError("LLM", "模型名称未配置")
            if not settings.llm_base_url:
                raise AgentInitializationError("LLM", "API Base URL未配置") 
            if not settings.llm_api_key:
                raise AgentInitializationError("LLM", "API Key未配置")
            
        try:
            # 创建LLM实例
            llm = ChatOpenAI(
                model=settings.llm_model,
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
                timeout=settings.llm_timeout,
                max_retries=settings.llm_max_retries
            )
            
            # 健康检查 - 简单的模型调用
            logger.info("🔍 执行LLM健康检查...")
            test_response = llm.invoke("ping")
            
            if not test_response or not test_response.content:
                raise AgentInitializationError("LLM", "健康检查失败：无响应内容")
                
            logger.info("✅ LLM健康检查通过")
            return llm
            
        except Exception as e:
            error_msg = f"LLM创建失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            raise AgentInitializationError("LLM", error_msg)


class DatabaseFactory:
    """数据库工厂 - 基于统一配置创建和验证数据库连接"""
    
    @staticmethod 
    def create_database_manager(settings: Optional[Settings] = None) -> DatabaseManager:
        """创建数据库管理器并验证连接
        
        Args:
            settings: 配置实例，默认使用全局配置
            
        Returns:
            验证通过的DatabaseManager实例
            
        Raises:
            AgentInitializationError: 数据库连接失败
        """
        if settings is None:
            settings = get_settings()
            
        logger.info(f"🔧 创建数据库连接: {settings.db_host}:{settings.db_port}")
        
        # 验证必需配置 - 遵循fail_fast策略
        if settings.fail_fast:
            required_fields = [
                ('db_host', settings.db_host),
                ('db_database', settings.db_database), 
                ('db_username', settings.db_username),
                ('db_password', settings.db_password)
            ]
            
            missing_fields = [name for name, value in required_fields if not value]
            if missing_fields:
                raise AgentInitializationError(
                    "Database", 
                    f"缺少必需配置: {', '.join(missing_fields)}"
                )
            
            # 验证主机格式 - 不能包含协议前缀
            if settings.db_host.startswith(('http://', 'https://', 'ftp://', 'mysql://')):
                raise AgentInitializationError(
                    "Database",
                    f"无效的主机格式: '{settings.db_host}' - 数据库主机不应包含协议前缀，请使用纯主机名或IP"
                )
            
            # 验证端口范围
            if not (1 <= settings.db_port <= 65535):
                raise AgentInitializationError(
                    "Database",
                    f"无效的端口号: {settings.db_port} - 端口范围应为1-65535"
                )
        
        try:
            # 创建数据库管理器 - 使用统一Settings配置
            db_manager = DatabaseManager(settings=settings)
            
            # 强制初始化和健康检查
            logger.info("🔍 执行数据库健康检查...")
            if not db_manager.initialize():
                raise AgentInitializationError("Database", "数据库初始化失败")
                
            logger.info("✅ 数据库健康检查通过")
            return db_manager
            
        except Exception as e:
            error_msg = f"数据库连接失败: {str(e)}"
            config_info = f"配置信息: {settings.db_type}://{settings.db_host}:{settings.db_port}/{settings.db_database}"
            
            logger.error(f"❌ {error_msg}")
            logger.error(f"📊 {config_info}")
            
            # 提供详细的错误分析
            if "invalid literal for int" in str(e):
                enhanced_msg = f"{error_msg} - 可能的原因: 环境变量包含空字符串或非数字值"
            elif "protocol" in str(e).lower() or "invalid" in str(e).lower():
                enhanced_msg = f"{error_msg} - 可能的原因: 主机格式不正确，请检查是否包含协议前缀"
            else:
                enhanced_msg = error_msg
                
            raise AgentInitializationError("Database", f"{enhanced_msg} | {config_info}")


class MemoryFactory:
    """记忆管理工厂 - 基于统一配置创建和验证Neo4j连接"""
    
    @staticmethod
    def create_memory_manager(settings: Optional[Settings] = None) -> Neo4jMemoryManager:
        """创建Neo4j记忆管理器并验证连接
        
        Args:
            settings: 配置实例，默认使用全局配置
            
        Returns:
            验证通过的Neo4jMemoryManager实例
            
        Raises:
            AgentInitializationError: Neo4j连接失败
        """
        if settings is None:
            settings = get_settings()
            
        logger.info(f"🔧 创建Neo4j连接: {settings.neo4j_uri}")
        
        # 验证必需配置 - 遵循fail_fast策略
        if settings.fail_fast:
            if not settings.neo4j_uri:
                raise AgentInitializationError("Neo4j", "连接URI未配置")
            if not settings.neo4j_user:
                raise AgentInitializationError("Neo4j", "用户名未配置")
            if not settings.neo4j_password:
                raise AgentInitializationError("Neo4j", "密码未配置")
            
        try:
            # 创建Neo4j记忆管理器 - 使用统一Settings配置
            memory_manager = Neo4jMemoryManager(
                settings=settings,
                use_fallback=not settings.fail_fast  # fail_fast=True时不允许降级
            )
            
            # 验证Neo4j连接
            if not memory_manager.neo4j_graph:
                raise AgentInitializationError("Neo4j", "连接创建失败")
                
            # 健康检查 - 执行简单查询
            logger.info("🔍 执行Neo4j健康检查...")
            test_result = memory_manager.neo4j_graph.query("RETURN 1 as test")
            
            if not test_result or not isinstance(test_result, list):
                raise AgentInitializationError("Neo4j", "健康检查失败：查询无结果")
                
            logger.info("✅ Neo4j健康检查通过")
            return memory_manager
            
        except Exception as e:
            error_msg = f"Neo4j连接失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            raise AgentInitializationError("Neo4j", error_msg)


class ComponentFactory:
    """组件工厂 - 统一创建和管理所有核心组件"""
    
    @staticmethod
    def create_all_components(settings: Optional[Settings] = None) -> Dict[str, Any]:
        """创建所有核心组件并进行全面健康检查
        
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
        
        components = {}
        
        try:
            # 1. 创建LLM
            components["llm"] = LLMFactory.create_llm(settings)
            
            # 2. 创建数据库管理器  
            components["database_manager"] = DatabaseFactory.create_database_manager(settings)
            
            # 3. 创建记忆管理器
            components["memory_manager"] = MemoryFactory.create_memory_manager(settings)
            
            logger.info("🎉 所有核心组件创建成功")
            return components
            
        except Exception as e:
            logger.error(f"❌ 组件创建失败: {e}")
            raise


# 便利函数
def create_llm() -> ChatOpenAI:
    """便利函数：创建LLM实例"""
    return LLMFactory.create_llm()


def create_database_manager() -> DatabaseManager:
    """便利函数：创建数据库管理器"""
    return DatabaseFactory.create_database_manager()


def create_memory_manager() -> Neo4jMemoryManager:
    """便利函数：创建记忆管理器"""
    return MemoryFactory.create_memory_manager()