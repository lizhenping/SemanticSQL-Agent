"""SemanticSQL-Agent: 简化的 NL2SQL 智能体

基于 TRAEAgent 设计理念，使用模块化的 CLI 和 LLM 客户端。
"""

__version__ = "0.3.0"
__author__ = "lizhenping18@mails.ucas.ac.cn"

# 核心组件导入
try:
    from config.settings import Settings
    from models.schemas import SQLQueryResult
    
    __all__ = [
        "Settings",
        "SQLQueryResult"
    ]
except ImportError:
    # 在测试环境中可能会出现导入错误，这是正常的
    __all__ = []