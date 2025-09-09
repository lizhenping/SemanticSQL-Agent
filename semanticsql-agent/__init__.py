"""SemanticSQL-Agent: 简化的 NL2SQL 智能体

基于 TRAEAgent 设计理念，使用模块化的 CLI 和 LLM 客户端。
"""

__version__ = "0.3.0"
__author__ = "lizhenping18@mails.ucas.ac.cn"

# 简化导入，只保留必要的组件
try:
    from config.settings import Settings
    from models.schemas import SQLQueryResult
    
    # DatabaseConfig 已废弃，但保留兼容性
    from utils.database_config import DatabaseConfig
    
    __all__ = [
        "Settings",
        "DatabaseConfig", 
        "SQLQueryResult"
    ]
except ImportError:
    # 在测试环境中可能会出现导入错误，这是正常的
    __all__ = []