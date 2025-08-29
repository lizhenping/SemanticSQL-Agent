"""
trae_agent风格的配置系统
"""

from .trae_config import TraeConfig, DEFAULT_CONFIG_TEMPLATE, DatabaseConfig, DatabaseType

__all__ = [
    "TraeConfig",
    "DatabaseConfig", 
    "DatabaseType",
    "DEFAULT_CONFIG_TEMPLATE"
]